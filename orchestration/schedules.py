"""
Schedules — time-based triggers for jobs.

In a real Wyllo deployment, the pipeline would run hourly to keep the
feature store fresh. For this demo we schedule a single daily refresh
at 6 AM merchant-time (America/Sao_Paulo, since the data is BR-based).
"""

from dagster import ScheduleDefinition

from .jobs import full_pipeline_job

daily_refresh_schedule = ScheduleDefinition(
    name="daily_full_refresh_06h_brt",
    job=full_pipeline_job,
    cron_schedule="0 6 * * *",  # every day at 06:00
    execution_timezone="America/Sao_Paulo",
    description=(
        "Daily full refresh of the fraud feature store. Runs at 6 AM "
        "Brazil time — early enough that fraud analysts get fresh data "
        "for their morning review queue."
    ),
)
