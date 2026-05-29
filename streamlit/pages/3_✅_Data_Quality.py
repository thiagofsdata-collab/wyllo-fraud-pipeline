"""Data quality — last dbt test run results, parsed from run_results.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from utils.data import get_dbt_test_results, manifest_exists  # noqa: E402
from utils.styles import COLORS  # noqa: E402

st.set_page_config(page_title="Data Quality", page_icon="✅", layout="wide")
st.title("✅ Data Quality")
st.caption(
    "Last `dbt test` results, parsed from `dbt/target/run_results.json`. "
    "Run `dbt test` to refresh this page."
)

if not manifest_exists():
    st.error(
        "`dbt/target/manifest.json` not found. Run from the project root:\n\n"
        "```\ncd dbt && dbt parse && dbt test\n```"
    )
    st.stop()

df = get_dbt_test_results()
if df.empty:
    st.warning("No tests recorded yet. Run `dbt test`.")
    st.stop()

# ------- Counts per status
status_counts = df.groupby("status").size().reset_index(name="count")

# Three KPI cards
total = len(df)
passing = int(df[df["status"] == "pass"].shape[0])
failing = int(df[df["status"].isin(["fail", "error"])].shape[0])
warning = int(df[df["status"] == "warn"].shape[0])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total tests", f"{total}")
c2.metric("Passing", f"{passing}", delta=f"{100 * passing // max(total, 1)}%")
c3.metric("Warnings", f"{warning}")
c4.metric(
    "Failures",
    f"{failing}",
    delta=None if failing == 0 else "needs attention",
    delta_color="inverse" if failing > 0 else "off",
)

st.divider()

# ------- Pie / bar of statuses
fig = px.pie(
    status_counts,
    values="count",
    names="status",
    title="Tests by status",
    color="status",
    color_discrete_map={
        "pass": COLORS["good"],
        "warn": COLORS["warn"],
        "fail": COLORS["bad"],
        "error": COLORS["bad"],
    },
    hole=0.5,
)
fig.update_layout(height=350)
st.plotly_chart(fig, use_container_width=True)

# ------- Filterable test table
st.subheader("All tests")
status_filter = st.multiselect(
    "Status",
    options=sorted(df["status"].unique().tolist()),
    default=sorted(df["status"].unique().tolist()),
)
filtered = df[df["status"].isin(status_filter)].sort_values(
    by=["status", "execution_time"], ascending=[True, False]
)
st.dataframe(filtered, use_container_width=True, hide_index=True)

# ------- Slowest tests
st.subheader("Slowest 10 tests")
slowest = df.nlargest(10, "execution_time")[
    ["test_name", "status", "execution_time"]
]
st.dataframe(slowest, use_container_width=True, hide_index=True)

st.divider()
st.markdown(
    """
    **Why surface dbt tests in a dashboard?**

    Tests are not just CI gates — they are *runtime contracts*. If a Silver
    uniqueness test starts warning, that's a signal something upstream
    changed (a vendor schema shift, a duplicate ingestion). Surfacing the
    pass-rate over time lets the data team treat data quality as an
    operational metric, not a build-time check.

    In production, these results would be pushed to Elementary or Monte
    Carlo for historical tracking and alerting.
    """
)
