"""Feature store explorer — the deliverable of this pipeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
from utils.data import (
    db_exists,
    get_feature_store_summary,
    get_feature_store_top_risky,
    get_risk_distribution,
)

import streamlit as st

st.set_page_config(page_title="Feature Store", page_icon="⭐", layout="wide")
st.title("⭐ Feature Store")
st.caption(
    "`gold.fct_customer_return_risk_features` — the deliverable of this "
    "pipeline. One row per (customer, snapshot_date)."
)

if not db_exists():
    st.error("Warehouse not found. See the Overview page for setup.")
    st.stop()

# ------- Summary
kpi = get_feature_store_summary()
if not kpi or not kpi.get("total_rows"):
    st.warning("Feature store is empty — run `dbt run` to materialize Gold.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total rows", f"{int(kpi['total_rows']):,}")
c2.metric("Unique customers", f"{int(kpi['unique_customers']):,}")
c3.metric("Monthly snapshots", f"{int(kpi['snapshots'])}")
c4.metric(
    "Avg cancel rate",
    f"{(kpi['avg_cancel_rate'] or 0) * 100:.2f}%",
    help="Across all customer x snapshot rows.",
)

st.divider()

# ------- Distribution of risk proxies
st.subheader("Risk-proxy distribution (latest snapshot)")
dist = get_risk_distribution()

col_left, col_right = st.columns(2)
with col_left:
    fig = px.histogram(
        dist,
        x="cancel_rate_lifetime",
        nbins=30,
        title="Cancel-rate distribution (chargeback proxy)",
        labels={"cancel_rate_lifetime": "Cancel rate (post-approval)"},
    )
    fig.update_layout(height=320, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    fig = px.histogram(
        dist,
        x="low_review_on_delivered_rate",
        nbins=30,
        title="Low-review rate distribution (INR proxy)",
        labels={"low_review_on_delivered_rate": "Low review on delivered orders"},
    )
    fig.update_layout(height=320, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ------- Top risky customers
st.subheader("Top customers by composite risk (latest snapshot)")
st.caption(
    "Sorted by (cancel_rate + low_review_rate). These are the customers a "
    "downstream model or rule engine would flag first. **Filter:** ≥2 orders "
    "to avoid noisy one-off rows."
)

limit = st.slider("Show top N", min_value=10, max_value=200, value=50, step=10)
df_top = get_feature_store_top_risky(limit=limit)
st.dataframe(
    df_top,
    use_container_width=True,
    hide_index=True,
    column_config={
        "cancel_rate": st.column_config.ProgressColumn(
            "cancel_rate", min_value=0.0, max_value=1.0, format="%.2f"
        ),
        "low_review_rate": st.column_config.ProgressColumn(
            "low_review_rate", min_value=0.0, max_value=1.0, format="%.2f"
        ),
    },
)

st.divider()
st.markdown(
    """
    > **Note on what this is and isn't.**
    > This page **previews the feature store** — it lets you eyeball what
    > the downstream model/rule engine would consume. It is not a fraud
    > investigation UI. Per-customer decisions, manual reviews, and
    > approve/block actions would live in a separate downstream system
    > built on top of these features.
    """
)
