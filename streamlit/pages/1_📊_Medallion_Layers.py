"""Medallion layers — row counts and per-layer health."""
import sys
from pathlib import Path

# Make sibling utils/ importable when run via `streamlit run pages/...`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
from utils.data import db_exists, get_layer_row_counts
from utils.styles import LAYER_COLORS

import streamlit as st

st.set_page_config(page_title="Medallion Layers", page_icon="📊", layout="wide")
st.title("📊 Medallion Layers")
st.caption("Row counts and structure of each layer in the pipeline.")

if not db_exists():
    st.error("Warehouse not found. See the Overview page for setup.")
    st.stop()

df = get_layer_row_counts()
if df.empty:
    st.warning("No tables found yet — run `dbt seed && dbt run` first.")
    st.stop()

# ------ KPIs per layer
layers_order = ["main_bronze", "main_silver", "main_gold", "main_seeds"]
cols = st.columns(len(layers_order))
for col, layer in zip(cols, layers_order, strict=True):
    sub = df[df["layer"] == layer]
    n_tables = len(sub)
    max_rows = int(sub["row_count"].max()) if not sub.empty else 0
    col.metric(
        layer.replace("main_", "").capitalize(),
        f"{n_tables} table{'s' if n_tables != 1 else ''}",
        delta=f"max {max_rows:,} rows" if max_rows else None,
        delta_color="off",
    )

# ------ Horizontal bar chart: rows per table grouped by layer
df_plot = df.copy()
df_plot["layer_label"] = df_plot["layer"].str.replace("main_", "").str.capitalize()
fig = px.bar(
    df_plot,
    x="row_count",
    y="table_name",
    color="layer",
    color_discrete_map=LAYER_COLORS,
    orientation="h",
    title="Row counts by table",
    labels={"row_count": "Rows", "table_name": "", "layer": "Layer"},
)
fig.update_layout(height=600, showlegend=True)
st.plotly_chart(fig, use_container_width=True)

# ------ Raw table
with st.expander("📋 Raw table listing"):
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Layer contract reminder")
st.markdown(
    """
    | Layer | Materialization | Contract |
    |---|---|---|
    | **Bronze** | `view` | 1:1 with source CSVs + provenance metadata. Zero transformation. |
    | **Silver** | `table` | Cleaned, typed, deduplicated. Test gate to Gold. |
    | **Gold** | `table` | Feature store + analytical surfaces. Consumed by DS/analysts/dashboards. |
    | **Seeds** | `table` | Version-controlled reference data (thresholds, priors). |
    """
)
