"""
Jobs — named, reusable pipeline runs.

A job in Dagster is a selection of assets that should be materialized
together. The same assets can participate in multiple jobs (e.g., a
full-refresh job and an incremental job over the same models).
"""

from dagster import AssetSelection, define_asset_job

# The full pipeline: ingestion + all dbt models + all dbt tests.
# AssetSelection.all() picks up every asset registered in definitions.py.
full_pipeline_job = define_asset_job(
    name="full_pipeline",
    selection=AssetSelection.all(),
    description=(
        "End-to-end refresh: re-ingest the raw CSVs, rebuild Bronze/Silver/Gold "
        "via dbt, and run all data-quality tests."
    ),
    tags={"owner": "data_engineering", "tier": "production"},
)

# Gold-only refresh: useful when ingestion hasn't changed but you want to
# rebuild the feature store (e.g. seed updates).
gold_only_job = define_asset_job(
    name="refresh_gold",
    selection=AssetSelection.groups("gold"),
    description="Rebuild Gold layer only — useful after seed or feature changes.",
    tags={"owner": "data_engineering", "tier": "production"},
)
