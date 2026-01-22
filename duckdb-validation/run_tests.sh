#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${root_dir}"

cargo build -p tpchgen-cli --release

target/release/tpchgen-cli --scale-factor 1 --tables orders,lineitem --format=parquet --output-dir sf1
target/release/tpchgen-cli --scale-factor 10 --tables orders,lineitem --format=parquet --output-dir sf10

duckdb -c ".read duckdb-validation/check_ordering.sql"
duckdb -c ".read duckdb-validation/tpch_q12.sql"

duckdb -c "SELECT l_shipmode, SUM(CASE WHEN o_orderpriority IN ('1-URGENT', '2-HIGH') THEN 1 ELSE 0 END) AS high_line_count, SUM(CASE WHEN o_orderpriority NOT IN ('1-URGENT', '2-HIGH') THEN 1 ELSE 0 END) AS low_line_count FROM read_parquet('sf10/lineitem.parquet') AS lineitem JOIN read_parquet('sf10/orders.parquet') AS orders ON l_orderkey = o_orderkey WHERE l_shipmode IN ('MAIL', 'SHIP') AND l_commitdate < l_receiptdate AND l_shipdate < l_commitdate AND l_receiptdate >= DATE '1994-01-01' AND l_receiptdate < DATE '1995-01-01' GROUP BY l_shipmode ORDER BY l_shipmode;"
