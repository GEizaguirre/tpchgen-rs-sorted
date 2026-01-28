#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
import os
import random
import re
import time
import math
import json
import uuid
import threading
from queue import Queue, Empty
from typing import Callable, List, Dict

# import boto3

# ============================================================
# Configuration
# ============================================================

S3_BUCKET = "your-bucket-name"
S3_PREFIX = "events/"

UPLOAD_INTERVAL_MS = 200
MAX_QUEUE_SIZE = 5_000

MIN_WORKERS = 1
MAX_WORKERS = 16

TARGET_QUEUE_LATENCY_SEC = 2.0
DEFAULT_DURATION = 300

class S3Uploader:
    def __init__(self, bucket: str, log_file: str):
        # self.s3 = boto3.client("s3")
        self.bucket = bucket
        self.log_file = log_file

    def upload_file(self, file_path: str) -> None:
        # key = f"{S3_PREFIX}{os.path.basename(file_path)}"
        # self.s3.upload_file(file_path, self.bucket, key)
        with open(self.log_file, "a") as f:
            f.write(f"{time.time()}, {file_path}\n")

def upload_worker(
        queue: Queue,
        uploader: S3Uploader,
        stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        try:
            file_path = queue.get(timeout=0.5)
        except Empty:
            continue

        try:
            uploader.upload_file(file_path)
        except Exception as e:
            print(f"[worker] upload failed: {e}")
        finally:
            queue.task_done()

def scale_workers(
        queue: Queue,
        workers: list,
        uploader: S3Uploader,
        stop_event: threading.Event,
) -> None:
    backlog = queue.qsize()
    worker_count = max(len(workers), 1)

    # Approximate "seconds worth of work" waiting
    estimated_latency = backlog / worker_count

    if (
            estimated_latency > TARGET_QUEUE_LATENCY_SEC
            and len(workers) < MAX_WORKERS
    ):
        t = threading.Thread(
            target=upload_worker,
            args=(queue, uploader, stop_event),
            daemon=True,
        )
        t.start()
        workers.append(t)
        print(f"[scaler] spawned worker (total={len(workers)})")

    elif (
            estimated_latency < TARGET_QUEUE_LATENCY_SEC / 2
            and len(workers) > MIN_WORKERS
    ):
        # Cooperative downscale: signal and let a worker exit naturally
        stop_event.set()
        workers.pop()
        stop_event.clear()
        print(f"[scaler] removed worker (total={len(workers)})")

def run_multi_table_generation(
    folders: List[str],
    log_file: str,
    duration: int,
) -> None:
    queue = Queue(maxsize=MAX_QUEUE_SIZE)
    stop_event = threading.Event()
    uploader = S3Uploader(S3_BUCKET, log_file)

    def extract_number(filename):
        match = re.search(r'\.(\d+)\.', filename)
        return int(match.group(1)) if match else 0

    tables_data = []
    
    # Different patterns for each table
    # pattern: (period, phase_offset, depth)
    patterns = [
        (duration / 2.0, 0, 0.3),
        (duration / 3.0, math.pi / 2, 0.2),
        (duration / 4.0, math.pi, 0.4),
    ]

    for i, folder in enumerate(folders):
        files = [
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        ]
        files.sort(key=lambda x: extract_number(os.path.basename(x)))
        
        if not files:
            print(f"No files found in {folder}")
            continue
            
        period, phase, depth = patterns[i % len(patterns)]
        omega = 2 * math.pi / period
        
        # Helper to calculate integral of (1 + depth * sin(omega*t + phase))
        # W(t) = t - (depth/omega) * (cos(omega*t + phase) - cos(phase))
        def weight_integral(t, o=omega, ph=phase, d=depth):
            return t - (d / o) * (math.cos(o * t + ph) - math.cos(ph))
        
        total_weight = weight_integral(duration)
        
        tables_data.append({
            "name": os.path.basename(folder),
            "files": files,
            "num_files": len(files),
            "sent_count": 0,
            "weight_fn": weight_integral,
            "total_weight": total_weight
        })

    if not tables_data:
        return

    workers = []
    for _ in range(MIN_WORKERS):
        t = threading.Thread(
            target=upload_worker,
            args=(queue, uploader, stop_event),
            daemon=True,
        )
        t.start()
        workers.append(t)

    start_time = time.time()
    
    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                # Catch remaining files
                for table in tables_data:
                    while table["sent_count"] < table["num_files"]:
                        queue.put(table["files"][table["sent_count"]])
                        table["sent_count"] += 1
                break

            for table in tables_data:
                # Target files by time t
                target_count = int(round(table["num_files"] * table["weight_fn"](elapsed) / table["total_weight"]))
                target_count = min(target_count, table["num_files"])
                
                num_to_send = target_count - table["sent_count"]
                for _ in range(num_to_send):
                    queue.put(table["files"][table["sent_count"]])
                    table["sent_count"] += 1

            scale_workers(queue, workers, uploader, stop_event)
            time.sleep(UPLOAD_INTERVAL_MS / 1000.0)

    finally:
        stop_event.set()
        queue.join()
        print("Stopping generator")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Table Data Generator")
    parser.add_argument("--folders", type=str, nargs="+", required=True, help="List of folders (one per table)")
    parser.add_argument("--log-file", type=str, default="upload.log", help="Log file for upload times")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Total execution time in seconds")
    args = parser.parse_args()

    run_multi_table_generation(
        folders=args.folders,
        log_file=args.log_file,
        duration=args.duration
    )