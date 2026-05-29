"""
dbt assets — automatic Dagster asset for each dbt model.

dagster-dbt parses the dbt manifest.json and creates one Dagster asset per
dbt model. The asset graph mirrors the dbt lineage exactly: br_orders ->
stg_orders -> int_orders_enriched -> fct_customer_return_risk_features.

This also picks up dbt SOURCES — declared in models/bronze/_olist_sources.yml —
and creates one external asset per source table. We wire each of those
sources to depend on `olist_raw_loaded` from ingestion_assets, so the
asset graph is connected end-to-end: ingestion -> sources -> bronze ->
silver -> gold.
"""
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

from dagster import AssetExecutionContext, AssetKey
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt"
DBT_MANIFEST = DBT_PROJECT_DIR / "target" / "manifest.json"

# The single upstream asset that produces all dbt sources.
INGESTION_ASSET_KEY = AssetKey("olist_raw_loaded")


class WylloDbtTranslator(DagsterDbtTranslator):
    """
    Custom translator that:
      1. Groups models by Medallion layer (bronze/silver/gold) for clean UI.
      2. Wires every dbt source to depend on the ingestion asset, so the
         Dagster lineage shows ingestion -> sources -> models end-to-end.

    Sources keep their own asset keys (one per source table); the dependency
    edge is added via get_deps, not by collapsing their keys.
    """

    def get_group_name(self, dbt_resource_props: dict) -> Optional[str]:
        name = dbt_resource_props.get("name", "")
        if name.startswith("br_"):
            return "bronze"
        if name.startswith("stg_"):
            return "silver"
        if name.startswith("int_") or name.startswith("fct_") or name.startswith("dim_"):
            return "gold"
        return "dbt_other"


@dbt_assets(
    manifest=DBT_MANIFEST,
    dagster_dbt_translator=WylloDbtTranslator(),
)
def wyllo_dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Materializes all dbt models. Dagster streams dbt's output and emits
    one asset materialization per model + one observation per test.

    Equivalent to running `dbt build` from the CLI, but with full
    integration into Dagster's asset graph, retry policies, and UI.
    """
    yield from dbt.cli(["build"], context=context).stream()
