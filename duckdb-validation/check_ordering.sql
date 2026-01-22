-- Checks global date ordering for orders and lineitem in sf1 and sf10.

SELECT
  COUNT(*) AS orders_sf1_out_of_order
FROM (
  SELECT o_orderdate,
         LAG(o_orderdate) OVER (ORDER BY o_orderdate) AS prev_date
  FROM read_parquet('sf1/orders.parquet')
)
WHERE prev_date IS NOT NULL
  AND o_orderdate < prev_date;

SELECT
  COUNT(*) AS lineitem_sf1_out_of_order
FROM (
  SELECT l_shipdate,
         LAG(l_shipdate) OVER (ORDER BY l_shipdate) AS prev_date
  FROM read_parquet('sf1/lineitem.parquet')
)
WHERE prev_date IS NOT NULL
  AND l_shipdate < prev_date;

SELECT
  COUNT(*) AS orders_sf10_out_of_order
FROM (
  SELECT o_orderdate,
         LAG(o_orderdate) OVER (ORDER BY o_orderdate) AS prev_date
  FROM read_parquet('sf10/orders.parquet')
)
WHERE prev_date IS NOT NULL
  AND o_orderdate < prev_date;

SELECT
  COUNT(*) AS lineitem_sf10_out_of_order
FROM (
  SELECT l_shipdate,
         LAG(l_shipdate) OVER (ORDER BY l_shipdate) AS prev_date
  FROM read_parquet('sf10/lineitem.parquet')
)
WHERE prev_date IS NOT NULL
  AND l_shipdate < prev_date;
