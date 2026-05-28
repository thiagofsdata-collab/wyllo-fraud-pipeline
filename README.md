# Wyllo Return Fraud Pipeline

> End-to-end data engineering pipeline that turns raw e-commerce transactional
> data into a point-in-time feature store for return fraud and policy abuse
> detection. 

## Intro

Return fraud costs e-commerce ~$100B/year. **2% of customers cause 20% of
fraudulent returns** (NRF). The hard part isn't blocking — it's
**segmenting behaviour** so legitimate occasional-returners stay
unblocked. This pipeline produces the feature store that makes that
segmentation possible.

**As a Data Engineer:** We don't train the model. We deliver the
table where the decision becomes obvious.

```
                                         ┌───────────────────────────────────┐
Olist CSVs → S3 → Bronze → Silver → Gold │ fct_customer_return_risk_features │
                                         │ PK: (customer, snapshot_date)     │
                                         └─────────┬─────────────────────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                       Data Scientist      Fraud Analyst        Pipeline Health
                       (trains models)    (writes rules)        (Streamlit + Plotly)
```

## Status


🟢 Layer 0 — Schema mapping, repo skeleton, design docs

🟡 Layer 1 — Ingestion (S3 + Glue + Athena) — in progress

⚪ Layer 2 — dbt Bronze / Silver / Gold

⚪ Layer 3 — Dagster orchestration

⚪ Layer 4 — Streamlit pipeline health dashboard

⚪ Layer 5 — DataOps NL catalog utility

⚪ Layer 6 — Docker + CI


## Design documents (read these first)

- [`docs/SCHEMA_FRAUD_MAPPING.md`](docs/SCHEMA_FRAUD_MAPPING.md) — how
  Olist columns map to fraud-prevention features, with proxy logic and
  out-of-scope rationale.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design,
  layer responsibilities, tool-choice trade-offs, and the production
  migration path (Kinesis dashed box explained).

## Quick start — current state

```bash
# 1. Install Python deps (Python 3.11 or 3.12)
make install

# 2. Download the Olist dataset from Kaggle into data/raw/
make download-data

# 3. (next layer) Build Bronze/Silver/Gold
make dbt-run
```

The full one-command Docker setup ships with Layer 6.


## Tech choices in one line each

- **AWS S3 + Glue + Athena** — standard data lake; S3 as storage contract
- **DuckDB** — analytical engine, portable SQL (same models would run in
  Snowflake/BigQuery)
- **dbt** — SQL-as-code with tests, lineage, docs
- **Dagster** — asset-centric orchestrator that maps cleanly to dbt
- **Streamlit + Plotly** — pipeline health dashboard, not fraud dashboard
- **LangChain + FAISS** — small DataOps utility for catalog NL search
- **GitHub Actions** — CI runs dbt tests + pytest on every PR

Full rationale: see `docs/ARCHITECTURE.md`.

## Repository layout

```
wyllo-fraud-pipeline/
├── ingestion/          # boto3 + Glue Crawler + Athena
│   ├── s3/
│   ├── glue/
│   └── athena/
├── dbt/                # the heart — models + tests + seeds + macros
│   ├── models/
│   │   ├── bronze/     # 1:1 raw + metadata
│   │   ├── silver/     # cleaned, typed, deduped
│   │   └── gold/       # fct_customer_return_risk_features
│   ├── seeds/          # risk thresholds, category priors (CSV in git)
│   ├── tests/          # custom singular tests
│   └── macros/         # haversine, generate_snapshots
├── orchestration/      # Dagster
├── scoring/            # ONE notebook: handoff to Data Science
├── ai_dataops/         # small utility: NL search over dbt catalog
├── streamlit/          # pipeline health dashboard
├── tests/              # pytest
├── docs/
│   ├── SCHEMA_FRAUD_MAPPING.md
│   ├── ARCHITECTURE.md
│   └── diagrams/       # Excalidraw exports
├── .github/workflows/
└── pyproject.toml
```

## What this pipeline does NOT do (by design)

| Out of scope                        | Why                                                              |
|-------------------------------------|------------------------------------------------------------------|
| ML model training                   | Data Scientist's job. Pipeline produces the input.               |
| Rule engine business logic          | Fraud Analyst's job. Pipeline exposes features they query.       |
| Real-time pre-checkout scoring      | Sub-second latency need; this is the batch feature store.        |
| Cross-merchant identity resolution  | Wyllo's moat — requires data we don't have.                      |
| Device / IP fingerprint features    | Olist has none; simulation would be theater.                     |

These limits are interview discussion points, not failures.
