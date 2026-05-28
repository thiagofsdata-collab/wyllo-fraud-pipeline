.PHONY: help install download-data ingest dbt-deps dbt-run dbt-test dagster streamlit test lint format clean

PYTHON := python3
PIP    := $(PYTHON) -m pip

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?##"}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install Python core deps + dev tools
	$(PIP) install -e ".[dev]"
	pre-commit install

install-all:  ## Install everything (orchestration, dashboard, ai)
	$(PIP) install -e ".[all]"
	pre-commit install

download-data:  ## Pull the Olist CSVs from Kaggle into data/raw/
	$(PYTHON) ingestion/s3/download_olist.py

ingest:  ## (next layer) Upload data/raw -> S3 and run Glue crawler
	$(PYTHON) ingestion/s3/upload_to_s3.py
	$(PYTHON) ingestion/glue/run_crawler.py

dbt-deps:  ## Install dbt packages
	cd dbt && dbt deps

dbt-run:  ## Run all dbt models (bronze -> silver -> gold)
	cd dbt && dbt seed && dbt run

dbt-test:  ## Run all dbt tests
	cd dbt && dbt test

dbt-docs:  ## Generate and serve dbt docs locally
	cd dbt && dbt docs generate && dbt docs serve --port 8080

dagster:  ## (next layer) Launch Dagster webserver on :3000
	DAGSTER_HOME=$(PWD)/dagster_home dagster dev -m orchestration

streamlit:  ## (next layer) Launch Streamlit pipeline-health dashboard on :8501
	streamlit run streamlit/app.py

test:  ## Run pytest
	pytest

lint:  ## Run ruff
	ruff check .

format:  ## Auto-format with ruff
	ruff format .
	ruff check --fix .

clean:  ## Remove build artifacts and caches
	rm -rf dbt/target dbt/logs .pytest_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
