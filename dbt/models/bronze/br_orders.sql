-- Bronze: 1:1 passthrough of raw orders + provenance metadata (already
-- stamped at ingestion). Materialized as view — zero storage, always fresh.
SELECT * FROM {{ source('olist_raw', 'olist_orders') }}
