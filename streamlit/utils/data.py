"""
Cached DuckDB queries used across Streamlit pages.

Streamlit reruns the script top-to-bottom on every interaction. Wrapping
queries in @st.cache_data prevents hitting DuckDB on every slider move
or page navigation — they re-run only when the underlying file mtime or
TTL changes.
"""
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "warehouse" / "wyllo.duckdb"
DBT_TARGET_DIR = PROJECT_ROOT / "dbt" / "target"


def _connect():
    """Open a read-only DuckDB connection to avoid lock contention with dbt runs."""
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(ttl=60)
def query(sql: str) -> pd.DataFrame:
    """Run an arbitrary SELECT and return a DataFrame."""
    con = _connect()
    try:
        return con.execute(sql).df()
    finally:
        con.close()


@st.cache_data(ttl=60)
def get_schemas() -> list[str]:
    """List all schemas present in the warehouse."""
    df = query(
        "SELECT DISTINCT table_schema FROM information_schema.tables ORDER BY 1"
    )
    return df["table_schema"].tolist()


@st.cache_data(ttl=60)
def get_layer_row_counts() -> pd.DataFrame:
    """Row counts per Medallion layer object (tables AND views). Bronze is
    materialized as views in dbt, so we need to query both catalogs.
    """
    # tables (Silver, Gold, Seeds) — duckdb_tables() exposes row counts directly
    tables = query(
        """
        SELECT
            schema_name      AS layer,
            table_name,
            estimated_size   AS row_count
        FROM duckdb_tables()
        WHERE schema_name IN ('main_bronze', 'main_silver', 'main_gold', 'main_seeds')
        """
    )
    # views (Bronze) — counts need an explicit COUNT(*) per view
    bronze_views = query(
        """
        SELECT view_name
        FROM duckdb_views()
        WHERE schema_name = 'main_bronze'
        """
    )
    rows = []
    for v in bronze_views["view_name"]:
        n = query(f"SELECT COUNT(*) AS c FROM main_bronze.{v}").iloc[0]["c"]
        rows.append({"layer": "main_bronze", "table_name": v, "row_count": int(n)})
    bronze_df = pd.DataFrame(rows)
    out = pd.concat([tables, bronze_df], ignore_index=True)
    return out.sort_values(["layer", "table_name"]).reset_index(drop=True)


@st.cache_data(ttl=60)
def get_feature_store_top_risky(limit: int = 50) -> pd.DataFrame:
    """Top N customers by cancel rate and low-review rate from latest snapshot."""
    return query(
        f"""
        WITH latest AS (
            SELECT MAX(snapshot_date) AS d
            FROM main_gold.fct_customer_return_risk_features
        )
        SELECT
            customer_unique_id,
            customer_state,
            total_orders_lifetime,
            orders_last_30d,
            ROUND(cancel_rate_lifetime, 3)            AS cancel_rate,
            cancel_post_approval_count_30d            AS cancel_30d,
            ROUND(avg_review_score, 2)                AS avg_review,
            ROUND(low_review_on_delivered_rate, 3)    AS low_review_rate,
            ROUND(avg_customer_seller_distance_km, 0) AS avg_dist_km,
            distinct_shipping_states_30d              AS states_30d
        FROM main_gold.fct_customer_return_risk_features f, latest l
        WHERE f.snapshot_date = l.d
          AND total_orders_lifetime >= 2
        ORDER BY (cancel_rate_lifetime + low_review_on_delivered_rate) DESC,
                 total_orders_lifetime DESC
        LIMIT {int(limit)}
        """
    )


@st.cache_data(ttl=60)
def get_feature_store_summary() -> dict:
    """High-level KPIs of the feature store."""
    df = query(
        """
        SELECT
            COUNT(*)                                   AS total_rows,
            COUNT(DISTINCT customer_unique_id)         AS unique_customers,
            COUNT(DISTINCT snapshot_date)              AS snapshots,
            MIN(snapshot_date)                         AS first_snapshot,
            MAX(snapshot_date)                         AS last_snapshot,
            ROUND(AVG(cancel_rate_lifetime), 4)        AS avg_cancel_rate,
            ROUND(AVG(low_review_on_delivered_rate), 4) AS avg_low_review_rate
        FROM main_gold.fct_customer_return_risk_features
        """
    )
    return df.iloc[0].to_dict() if not df.empty else {}


@st.cache_data(ttl=60)
def get_orders_overview() -> dict:
    """KPIs of the silver orders table — the data spine."""
    df = query(
        """
        SELECT
            COUNT(*)                                            AS total_orders,
            COUNT(DISTINCT customer_unique_id)                  AS unique_customers,
            SUM(CASE WHEN is_cancelled_post_approval THEN 1 ELSE 0 END)
                                                                AS cancel_post_approval,
            ROUND(
                100.0 * SUM(CASE WHEN is_cancelled_post_approval THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0)
            , 2)                                                AS pct_cancel_post_approval,
            MIN(order_purchase_ts)                              AS first_order_ts,
            MAX(order_purchase_ts)                              AS last_order_ts
        FROM main_silver.stg_orders
        """
    )
    return df.iloc[0].to_dict() if not df.empty else {}


@st.cache_data(ttl=60)
def get_risk_distribution() -> pd.DataFrame:
    """Distribution of cancel_rate across customers — for histogram."""
    return query(
        """
        SELECT cancel_rate_lifetime, low_review_on_delivered_rate, total_orders_lifetime
        FROM main_gold.fct_customer_return_risk_features
        WHERE snapshot_date = (
            SELECT MAX(snapshot_date) FROM main_gold.fct_customer_return_risk_features
        )
        AND total_orders_lifetime >= 1
        """
    )


@st.cache_data(ttl=300)
def get_dbt_test_results() -> pd.DataFrame:
    """
    Parse dbt's run_results.json from the last `dbt test` invocation.
    Returns one row per test with status and execution time.
    """
    import json

    run_results_path = DBT_TARGET_DIR / "run_results.json"
    if not run_results_path.exists():
        return pd.DataFrame(
            columns=["test_name", "status", "execution_time", "message"]
        )

    with open(run_results_path) as f:
        data = json.load(f)

    rows = []
    for r in data.get("results", []):
        unique_id = r.get("unique_id", "")
        if not unique_id.startswith("test."):
            continue
        rows.append(
            {
                "test_name": unique_id.split(".")[-1],
                "status": r.get("status", "unknown"),
                "execution_time": round(r.get("execution_time", 0.0), 3),
                "message": (r.get("message") or "")[:200],
            }
        )
    return pd.DataFrame(rows)


def db_exists() -> bool:
    """True iff the DuckDB file is present — the dashboard's hard prerequisite."""
    return DB_PATH.exists()


def manifest_exists() -> bool:
    return (DBT_TARGET_DIR / "manifest.json").exists()
