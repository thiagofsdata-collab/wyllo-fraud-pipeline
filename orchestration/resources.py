"""
Shared resources for the Dagster pipeline.

In Dagster, a "resource" is dependency-injectable infrastructure — DuckDB
connection, dbt CLI, S3 client, etc. Assets receive resources via type
annotation, which keeps assets pure (no hardcoded paths) and lets you
swap implementations between dev/staging/prod.
"""

from pathlib import Path

from dagster_dbt import DbtCliResource
from dagster_duckdb import DuckDBResource

# Project paths — anchored to the repo root, not the orchestration package,
# so this works no matter where dagster is launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt"
DUCKDB_PATH = PROJECT_ROOT / "data" / "warehouse" / "wyllo.duckdb"

# DuckDB resource — assets that need to query the warehouse receive this
# and get a managed connection (Dagster handles open/close, threading).
duckdb_resource = DuckDBResource(
    database=str(DUCKDB_PATH),
)

# dbt resource — Dagster's wrapper around the dbt CLI. Calling
# dbt.cli([...]).stream() from an asset gives us structured events
# (model started, model finished, test passed) that Dagster materializes
# as asset events automatically.
dbt_resource = DbtCliResource(
    project_dir=str(DBT_PROJECT_DIR),
    profiles_dir=str(DBT_PROJECT_DIR),
    target="local",
)
