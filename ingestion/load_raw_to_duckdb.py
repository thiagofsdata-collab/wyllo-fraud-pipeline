"""
Local ingestion: load the 9 Olist CSVs into DuckDB as raw tables.

This is the LOCAL-FIRST path. It does not require AWS credentials.
The equivalent production path (S3 + Glue + Athena) lives in
ingestion/s3, ingestion/glue, ingestion/athena and is documented there.

What this does:
  1. Reads each CSV from data/raw/
  2. Adds ingestion metadata (_loaded_at, _source_file)
  3. Adds a synthetic merchant_id partition (maps Olist sellers to
     Wyllo-style tenants) so the multi-tenant architecture is demonstrable
  4. Writes partitioned Parquet to data/bronze/ (mimics S3 layout)
  5. Registers the raw tables in a DuckDB database at
     data/warehouse/wyllo.duckdb under schema `raw`

After running this, dbt can read the raw tables via source('olist_raw', ...).

Run from project root:
    python ingestion/load_raw_to_duckdb.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

RAW_DIR = Path("data/raw")
BRONZE_DIR = Path("data/bronze")
WAREHOUSE_DIR = Path("data/warehouse")
DB_PATH = WAREHOUSE_DIR / "wyllo.duckdb"

# Maps each CSV file to its raw table name (matching _olist_sources.yml identifiers)
CSV_TO_TABLE = {
    "olist_customers_dataset.csv": "olist_customers_dataset",
    "olist_geolocation_dataset.csv": "olist_geolocation_dataset",
    "olist_order_items_dataset.csv": "olist_order_items_dataset",
    "olist_order_payments_dataset.csv": "olist_order_payments_dataset",
    "olist_order_reviews_dataset.csv": "olist_order_reviews_dataset",
    "olist_orders_dataset.csv": "olist_orders_dataset",
    "olist_products_dataset.csv": "olist_products_dataset",
    "olist_sellers_dataset.csv": "olist_sellers_dataset",
    "product_category_name_translation.csv": "product_category_name_translation",
}


def verify_raw_files() -> list[str]:
    """Return list of missing CSV files."""
    missing = [f for f in CSV_TO_TABLE if not (RAW_DIR / f).exists()]
    return missing


def load_csvs_to_duckdb(con: duckdb.DuckDBPyConnection) -> None:
    """Load each CSV into the raw schema with ingestion metadata."""
    loaded_at = datetime.now(timezone.utc).isoformat()

    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    for csv_file, table_name in CSV_TO_TABLE.items():
        csv_path = (RAW_DIR / csv_file).as_posix()
        print(f"  Loading {csv_file} -> raw.{table_name}")

        # read_csv_auto handles type inference and the BR-encoded text columns.
        # We add metadata columns at load time (Bronze-style provenance).
        con.execute(
            f"""
            CREATE OR REPLACE TABLE raw.{table_name} AS
            SELECT
                *,
                '{loaded_at}'        AS _loaded_at,
                '{csv_file}'         AS _source_file
            FROM read_csv_auto('{csv_path}', header=true, sample_size=-1);
            """
        )

        row_count = con.execute(
            f"SELECT COUNT(*) FROM raw.{table_name}"
        ).fetchone()[0]
        print(f"    -> {row_count:,} rows")


def write_partitioned_parquet(con: duckdb.DuckDBPyConnection) -> None:
    """
    Write orders as partitioned Parquet to mimic the S3 bronze layout.

    In production, S3 would hold:
        s3://wyllo-bronze/merchant_id=.../event_type=orders/date=.../part.parquet

    Here we replicate that structure locally under data/bronze/ so the
    partitioning strategy is demonstrable and the dbt models could point
    at either local Parquet or S3 with no logic change.

    We derive a synthetic merchant_id from the seller of the first item
    of each order (Olist is a marketplace; we treat sellers as tenants).
    """
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    # Build an orders-with-merchant view: each order's "merchant" is the
    # seller of its first line item. Single-seller orders are unambiguous;
    # multi-seller orders are attributed to the primary (first) seller.
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW orders_with_merchant AS
        WITH first_seller AS (
            SELECT
                order_id,
                seller_id AS merchant_id,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id ORDER BY order_item_id
                ) AS rn
            FROM raw.olist_order_items_dataset
        )
        SELECT
            o.*,
            COALESCE(fs.merchant_id, 'unknown_merchant') AS merchant_id,
            CAST(o.order_purchase_timestamp AS DATE)     AS partition_date
        FROM raw.olist_orders_dataset o
        LEFT JOIN first_seller fs
            ON o.order_id = fs.order_id AND fs.rn = 1;
        """
    )

    out_path = (BRONZE_DIR / "orders").as_posix()
    con.execute(
        f"""
        COPY (SELECT * FROM orders_with_merchant)
        TO '{out_path}'
        (FORMAT PARQUET, PARTITION_BY (merchant_id, partition_date),
         OVERWRITE_OR_IGNORE true);
        """
    )

    n_partitions = sum(1 for _ in BRONZE_DIR.glob("orders/merchant_id=*/**/*.parquet"))
    print(f"  Wrote partitioned Parquet to {out_path}/ ({n_partitions} part files)")


def main() -> int:
    missing = verify_raw_files()
    if missing:
        print(f"ERROR: {len(missing)} CSV(s) missing from {RAW_DIR}/:")
        for f in missing:
            print(f"  - {f}")
        print("\nRun: python ingestion/s3/download_olist.py")
        return 1

    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to DuckDB at {DB_PATH}")
    con = duckdb.connect(str(DB_PATH))

    try:
        print("\n[1/2] Loading CSVs into raw schema...")
        load_csvs_to_duckdb(con)

        print("\n[2/2] Writing partitioned Parquet (S3-style layout)...")
        write_partitioned_parquet(con)

        print("\nDone. Raw tables available in DuckDB schema `raw`.")
        print(f"Database: {DB_PATH}")
        print("\nNext: cd dbt && dbt run")
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
