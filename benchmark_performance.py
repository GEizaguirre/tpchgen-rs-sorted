#!/usr/bin/env python3
import subprocess
import re
import sys
import os

def run_benchmark(sf, part_size, num_threads=None):
    build_cmd = ["cargo", "build", "-p", "tpchgen-cli", "--release"]
    print(f"Building tpchgen-cli in release mode...")
    subprocess.run(build_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cli_path = "target/release/tpchgen-cli"
    output_dir = f"benchmark_sf{sf}_{part_size}"
    if num_threads:
        output_dir += f"_t{num_threads}"
    
    # Remove existing output dir if any
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)

    cmd = [
        cli_path,
        "--scale-factor", str(sf),
        "--tables", "lineitem,orders,customer",
        "--format", "parquet",
        "--part-size", part_size,
        "--output-dir", output_dir,
        "-v"
    ]

    if num_threads:
        cmd.extend(["--num-threads", str(num_threads)])

    print(f"Running benchmark: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "RUST_LOG": "info"}
    )

    results = []
    current_file = None
    
    writing_re = re.compile(r"Writing table (\w+) .* to (.*) using")
    stats_re = re.compile(r"Created ([\d.]+) (GB|MB|KB|B) in ([\d.]+)(s|ms) \(([\d.]+) GB/sec\)")

    while True:
        line = process.stderr.readline()
        if not line:
            break
        print(line.strip(), file=sys.stderr)
        
        write_match = writing_re.search(line)
        if write_match:
            current_table = write_match.group(1)
            current_file = write_match.group(2)
            
        stats_match = stats_re.search(line)
        if stats_match and current_file:
            size_val = float(stats_match.group(1))
            size_unit = stats_match.group(2)
            duration_val = float(stats_match.group(3))
            duration_unit = stats_match.group(4)
            throughput = float(stats_match.group(5))
            
            # Convert size to GB
            size_gb = size_val
            if size_unit == "MB":
                size_gb /= 1024
            elif size_unit == "KB":
                size_gb /= (1024 * 1024)
            elif size_unit == "B":
                size_gb /= (1024 * 1024 * 1024)
            
            # Convert duration to seconds
            duration_s = duration_val
            if duration_unit == "ms":
                duration_s /= 1000
                
            results.append({
                "table": current_table,
                "file": current_file,
                "size_gb": size_gb,
                "duration_s": duration_s,
                "throughput_gb_s": throughput
            })
            current_file = None

    process.wait()
    
    if process.returncode != 0:
        print(f"Error: Benchmark failed with exit code {process.returncode}")
        return

    print("\n" + "="*80)
    print(f"{'Table':<15} {'File':<25} {'Size (GB)':>10} {'Time (s)':>10} {'GB/s':>10}")
    print("-"*80)
    
    table_stats = {}
    
    for r in results:
        print(f"{r['table']:<15} {r['file']:<25} {r['size_gb']:>10.3f} {r['duration_s']:>10.3f} {r['throughput_gb_s']:>10.3f}")
        
        if r['table'] not in table_stats:
            table_stats[r['table']] = {"time": 0, "size": 0, "files": 0}
        table_stats[r['table']]["time"] += r['duration_s']
        table_stats[r['table']]["size"] += r['size_gb']
        table_stats[r['table']]["files"] += 1

    print("-"*80)
    print("\nSummary per Table:")
    print(f"{'Table':<15} {'Files':>10} {'Avg s/file':>12} {'Total GB/s':>12}")
    print("-"*55)
    for table, stats in table_stats.items():
        avg_s_file = stats["time"] / stats["files"]
        total_gb_s = stats["size"] / stats["time"] if stats["time"] > 0 else 0
        print(f"{table:<15} {stats['files']:>10} {avg_s_file:>12.3f} {total_gb_s:>12.3f}")
    print("="*80)

if __name__ == "__main__":
    sf = 10
    part_size = "500MB"
    num_threads = None
    if len(sys.argv) > 1:
        sf = sys.argv[1]
    if len(sys.argv) > 2:
        part_size = sys.argv[2]
    if len(sys.argv) > 3:
        num_threads = sys.argv[3]
        
    run_benchmark(sf, part_size, num_threads)
