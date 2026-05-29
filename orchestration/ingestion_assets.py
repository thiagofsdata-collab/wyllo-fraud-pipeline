"""
Ingestion assets — load the 9 Olist CSVs into DuckDB's raw schema.

This is implemented as a Dagster MULTI-ASSET: a single Python function
materializes 9 asset keys (one per Olist source table). This is important
because:

  1. Each dbt source declared in models/bronze/_olist_sources.yml becomes
     a Dagster asset key automatically (AssetKey(['olist_raw', '<table>'])).
  2. By emitting materializations for those exact keys here, our ingestion
     function becomes the upstream producer of every dbt source.
  3. The asset graph is now end-to-end connected:
       ingestion (multi-asset) -> dbt sources -> Bronze -> Silver -> Gold

The actual loading logic lives in ingestion/load_raw_to_duckdb.py — this
module just wraps it so it participates in the Dagster asset graph.
"""
import subprocess
import sys
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSpec,
    MaterializeResult,
    MetadataValue,
    multi_asset,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INGESTION_SCRIPT = PROJECT_ROOT / "ingestion" / "load_raw_to_duckdb.py"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# These names must match the dbt source identifiers in _olist_sources.yml.
# Each one becomes an AssetKey(['olist_raw', '<name>']) in Dagster.
OLIST_SOURCES = [
    "olist_customers",
    "olist_geolocation",
    "olist_order_items",
    "olist_order_payments",
    "olist_order_reviews",
    "olist_orders",
    "olist_products",
    "olist_sellers",
    "product_category_translation",
]


@multi_asset(
    specs=[
        AssetSpec(
            key=AssetKey(["olist_raw", name]),
            group_name="ingestion",
            description=f"Raw {name} table loaded from Olist CSV into DuckDB.",
            kinds={"python", "duckdb"},
        )
        for name in OLIST_SOURCES
    ],
)
def olist_raw_loaded(context: AssetExecutionContext):
    """
    Run the ingestion script and emit one materialization per source table.

    On success, all 9 source assets are marked materialized simultaneously
    (they're all produced by a single subprocess call — there's no
    independent per-table refresh in this stage).
    """
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {RAW_DIR}. "
            "Download the Olist dataset first."
        )

    csvs_found = list(RAW_DIR.glob("*.csv"))
    if len(csvs_found) < len(OLIST_SOURCES):
        raise FileNotFoundError(
            f"Expected {len(OLIST_SOURCES)} CSV files in {RAW_DIR}, "
            f"found {len(csvs_found)}. "
            "Run: python ingestion/s3/download_olist.py"
        )

    context.log.info(f"Running ingestion: {INGESTION_SCRIPT}")
    result = subprocess.run(
        [sys.executable, str(INGESTION_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        context.log.info(line)
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            context.log.error(line)
        raise RuntimeError(
            f"Ingestion failed with exit code {result.returncode}."
        )

    # Yield one materialization per source asset.
    common_metadata = {
        "csv_files_loaded": MetadataValue.int(len(csvs_found)),
        "raw_directory": MetadataValue.path(str(RAW_DIR)),
        "stdout_tail": MetadataValue.md(
            "```\n" + "\n".join(result.stdout.splitlines()[-15:]) + "\n```"
        ),
    }
    for name in OLIST_SOURCES:
        yield MaterializeResult(
            asset_key=AssetKey(["olist_raw", name]),
            metadata=common_metadata,
        )
