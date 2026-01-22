# Sorted TPC-H Tables (Parquet)

This branch modifies the Arrow-backed TPC-H generators so that:

- `ORDERS` is generated globally ordered by `o_orderdate` (ascending).
- `LINEITEM` is generated globally ordered by `l_shipdate` (ascending).
- Output remains streaming/progressive (no full-table sort step).

## What changed

- Order dates are now derived from the global order index, producing a monotonic
  date sequence across all parts.
- Lineitem ship dates are derived from the corresponding ordered order date with
  a fixed offset, guaranteeing monotonic `l_shipdate` while keeping row counts
  identical.
- Commit/receipt dates still use bounded randomness relative to the order date.

These changes keep the generators fast and streaming-friendly for large scale
factors. The distributions for dates differ slightly from the original data
generator, but table sizes, keys, and overall schema are unchanged.

## CLI usage (Parquet)

Generate all tables in Parquet format (including sorted `orders` and `lineitem`):

```shell
tpchgen-cli --scale-factor 10 --format=parquet --output-dir sf10
```

Generate only the sorted `orders` and `lineitem` tables:

```shell
tpchgen-cli --scale-factor 10 --tables orders,lineitem --format=parquet --output-dir sf10
```

When using partitions (`--parts`), each part is ordered by date using the
global order index. Concatenating parts in part-number order preserves the
global ordering.
