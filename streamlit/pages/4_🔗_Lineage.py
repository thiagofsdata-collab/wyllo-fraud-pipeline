"""Pipeline lineage — Mermaid diagram of the asset graph."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(page_title="Lineage", page_icon="🔗", layout="wide")
st.title("🔗 Pipeline Lineage")
st.caption("The asset graph from ingestion to the feature store.")

st.markdown(
    """
    > For the **interactive** lineage view, run Dagster locally:
    > ```
    > dagster dev -m orchestration
    > ```
    > and open http://localhost:3000 → Assets → "View global asset lineage".

    The Mermaid below is a static rendering for quick reference.
    """
)

st.subheader("Static lineage (Mermaid)")
st.markdown(
    """
```mermaid
flowchart LR
    subgraph SRC[Sources]
        S1[Olist CSVs<br/>9 files]
    end

    subgraph ING[Ingestion]
        I1[olist_raw_loaded<br/>multi-asset]
    end

    subgraph BRONZE[Bronze — view]
        B1[br_orders]
        B2[br_order_items]
        B3[br_order_payments]
        B4[br_order_reviews]
        B5[br_customers]
        B6[br_sellers]
        B7[br_products]
        B8[br_geolocation]
        B9[br_category_translation]
    end

    subgraph SILVER[Silver — table]
        SL1[stg_orders]
        SL2[stg_order_items]
        SL3[stg_order_payments]
        SL4[stg_order_reviews]
        SL5[stg_customers]
        SL6[stg_geolocation]
    end

    subgraph GOLD[Gold — feature store]
        G1[int_orders_enriched]
        G2[fct_customer_return_risk_features]
    end

    subgraph CONSUMERS[Downstream consumers]
        C1[Data Science<br/>model training]
        C2[Fraud Analysts<br/>rule authoring]
        C3[Pipeline Health<br/>this dashboard]
    end

    S1 --> I1
    I1 --> B1 & B2 & B3 & B4 & B5 & B6 & B7 & B8 & B9
    B1 --> SL1
    B2 --> SL2
    B3 --> SL3
    B4 --> SL4
    B5 --> SL5
    B8 --> SL6
    SL1 & SL2 & SL3 & SL4 & SL5 & SL6 --> G1
    G1 --> G2
    SL1 & SL5 --> G2
    G2 --> C1 & C2 & C3
```
"""
)

st.subheader("Asset groups")
st.markdown(
    """
    | Group | Assets | Materialization | Purpose |
    |---|---|---|---|
    | **ingestion** | 9 | python multi-asset | Land raw CSVs → DuckDB |
    | **bronze** | 9 | dbt view | 1:1 raw + provenance |
    | **silver** | 6 | dbt table | Cleaned, typed, deduplicated |
    | **gold** | 2 | dbt table | Feature store + intermediate |
    | **dbt_other** | 3 | dbt seed | Versioned risk thresholds |
    """
)
