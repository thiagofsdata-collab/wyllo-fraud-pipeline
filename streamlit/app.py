"""
Wyllo Fraud Pipeline — Pipeline Health Dashboard

Entry point. Streamlit auto-discovers files under streamlit/pages/ and
adds them to the sidebar. This page is the landing.

Launch from the project root:
    streamlit run streamlit/app.py

The dashboard is a PIPELINE HEALTH dashboard — modelled on Monte Carlo /
Elementary, not on a fraud-investigation tool. It surfaces:
  - row counts and freshness per Medallion layer
  - the feature store contents
  - dbt test pass/fail results

It is NOT for fraud analysts deciding on individual cases (that would be
a separate downstream product the feature store feeds).
"""
import streamlit as st

from utils.data import (
    db_exists,
    get_feature_store_summary,
    get_orders_overview,
)

st.set_page_config(
    page_title="Wyllo Fraud Pipeline",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛡️ Wyllo Return-Fraud Pipeline")
st.caption(
    "Pipeline health dashboard — end-to-end Data Engineering project over the "
    "Olist Brazilian e-commerce dataset, designed for conversations with the "
    "Wyllo (NoFraud + Yofi) team."
)

if not db_exists():
    st.error(
        "**DuckDB warehouse not found.** "
        "Run the ingestion + dbt steps first:\n\n"
        "```\n"
        "python ingestion/load_raw_to_duckdb.py\n"
        "cd dbt && dbt seed && dbt run\n"
        "```"
    )
    st.stop()

# ----------------------------------------------------------------- KPIs
orders_kpi = get_orders_overview()
fs_kpi = get_feature_store_summary()

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Orders processed",
    f"{int(orders_kpi.get('total_orders', 0) or 0):,}",
    help="Total rows in the Silver layer (stg_orders).",
)
col2.metric(
    "Unique customers",
    f"{int(orders_kpi.get('unique_customers', 0) or 0):,}",
    help="Distinct customer_unique_id values — the stable identity.",
)
col3.metric(
    "Cancel-post-approval %",
    f"{orders_kpi.get('pct_cancel_post_approval', 0) or 0:.2f}%",
    help="Proxy for chargeback rate. Orders cancelled after payment was approved.",
)
col4.metric(
    "Feature store rows",
    f"{int(fs_kpi.get('total_rows', 0) or 0):,}",
    help="Rows in fct_customer_return_risk_features (customer × monthly snapshot).",
)

st.divider()

# --------------------------------------------------------------- panels
left, right = st.columns([2, 1])

with left:
    st.subheader("What this dashboard shows")
    st.markdown(
        """
        - **Medallion Layers** — row counts and per-layer health
        - **Feature Store** — the gold table that powers ML/rules downstream
        - **Data Quality** — last `dbt test` run results
        """
    )

    st.subheader("What it deliberately does NOT show")
    st.markdown(
        """
        - **No model scoring.** That's Data Science's job — the pipeline ends
          at the feature store.
        - **No per-case investigation.** That's a fraud analyst's UI built on
          top of these features.
        - **No real-time view.** This is the batch refresh — pre-checkout
          decisions need a sub-second path that complements this batch store.
        """
    )

with right:
    st.subheader("Feature store coverage")
    if fs_kpi:
        st.write(f"**Unique customers:** {int(fs_kpi.get('unique_customers', 0) or 0):,}")
        st.write(f"**Monthly snapshots:** {int(fs_kpi.get('snapshots', 0) or 0)}")
        first = fs_kpi.get("first_snapshot")
        last = fs_kpi.get("last_snapshot")
        if first and last:
            st.write(f"**Date range:** {first} → {last}")
        st.write(
            f"**Avg cancel rate:** "
            f"{(fs_kpi.get('avg_cancel_rate', 0) or 0) * 100:.2f}%"
        )
        st.write(
            f"**Avg low-review rate:** "
            f"{(fs_kpi.get('avg_low_review_rate', 0) or 0) * 100:.2f}%"
        )

st.divider()
st.caption(
    "Navigate the pages in the sidebar for drill-downs. "
    "All data is read-only from `data/warehouse/wyllo.duckdb`."
)
