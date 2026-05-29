"""
Sensors — event-based triggers.

Schedules run on time; sensors run on events. Here we detect new CSV
files appearing in data/raw/ and automatically trigger the pipeline.
This simulates the production behaviour where a new merchant data dump
would auto-trigger a refresh — no human in the loop.

The sensor polls every 30 seconds. It uses a cursor to remember the
latest file mtime it has seen, so a single new file triggers exactly
one run, not one per sensor tick.
"""

from pathlib import Path

from dagster import (
    DefaultSensorStatus,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)

from .jobs import full_pipeline_job

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


@sensor(
    job=full_pipeline_job,
    minimum_interval_seconds=30,
    default_status=DefaultSensorStatus.STOPPED,  # opt-in — start from UI
    description=(
        "Watches data/raw/ for new or modified CSV files. When detected, "
        "triggers a full pipeline run. Cursor is the max mtime seen, so "
        "we don't re-trigger on the same file."
    ),
)
def new_raw_data_sensor(context: SensorEvaluationContext) -> SensorResult:
    """Trigger full_pipeline when a CSV in data/raw/ is newer than last check."""
    if not RAW_DIR.exists():
        return SensorResult(skip_reason="data/raw/ does not exist yet")

    csvs = list(RAW_DIR.glob("*.csv"))
    if not csvs:
        return SensorResult(skip_reason="No CSV files in data/raw/")

    last_seen_mtime = float(context.cursor) if context.cursor else 0.0
    latest_mtime = max(f.stat().st_mtime for f in csvs)

    if latest_mtime <= last_seen_mtime:
        return SensorResult(skip_reason="No new or modified CSVs")

    return SensorResult(
        run_requests=[
            RunRequest(
                run_key=f"raw_changed_{latest_mtime:.0f}",
                tags={"trigger": "new_raw_data"},
            )
        ],
        cursor=str(latest_mtime),
    )
