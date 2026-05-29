"""
The Dagster Definitions object — the entry point Dagster loads.

This module ties everything together:
  - Assets: ingestion + all dbt models
  - Resources: DuckDB, dbt CLI
  - Jobs: full_pipeline, refresh_gold
  - Schedules: daily 6 AM
  - Sensors: new raw data detector

Launched with:
    dagster dev -m orchestration

The webserver UI starts on http://localhost:3000.
"""

from dagster import Definitions

from .dbt_models import wyllo_dbt_models
from .ingestion_assets import olist_raw_loaded
from .jobs import full_pipeline_job, gold_only_job
from .resources import dbt_resource, duckdb_resource
from .schedules import daily_refresh_schedule
from .sensors import new_raw_data_sensor

defs = Definitions(
    assets=[
        olist_raw_loaded,
        wyllo_dbt_models,
    ],
    resources={
        "duckdb": duckdb_resource,
        "dbt": dbt_resource,
    },
    jobs=[
        full_pipeline_job,
        gold_only_job,
    ],
    schedules=[
        daily_refresh_schedule,
    ],
    sensors=[
        new_raw_data_sensor,
    ],
)
