# Chronic Disease Surveillance Harmonization Lab
# Quickstart:  make setup && make transform && make app

PYTHON  ?= python3.11
VENV    ?= .venv
BIN     := $(VENV)/bin
# Which raw zone dbt reads: the committed offline snapshot (default) or a fresh pull.
DATA_DIR ?= data/sample
DBT     := cd transform && CDSH_DATA_DIR=$(abspath $(DATA_DIR)) ../$(BIN)/dbt
DBT_ARGS := --profiles-dir . --project-dir .

.PHONY: help setup ingest snapshot transform test dbt-test pytest lint analysis export docs site app clean

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n",$$1,$$2}'

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements.txt

setup: $(BIN)/python ## create venv and install pinned deps
	cd transform && ../$(BIN)/dbt deps --profiles-dir . --project-dir . >/dev/null 2>&1 || true

ingest: setup ## pull live data from data.cdc.gov into data/raw/ and refresh the offline snapshot
	$(BIN)/python -m ingest
	$(BIN)/python -m ingest.snapshot

snapshot: setup ## promote latest data/raw pull to the committed data/sample snapshot
	$(BIN)/python -m ingest.snapshot

transform: setup ## dbt seed + run + test, then export marts to data/mart
	$(DBT) build $(DBT_ARGS)
	$(BIN)/python -m scripts.export_marts

dbt-test: setup ## dbt build (models + data tests) without exporting
	$(DBT) build $(DBT_ARGS)

pytest: setup
	$(BIN)/pytest -q

lint: setup ## ruff lint
	$(BIN)/ruff check .

test: lint dbt-test pytest ## lint + dbt build/tests + pytest

analysis: transform ## gap & overlap report + pilot findings
	$(BIN)/python -m analysis.gap_report
	$(BIN)/python -m analysis.pilot

docs: setup ## dbt docs + generated data dictionary
	$(DBT) docs generate $(DBT_ARGS)
	$(BIN)/python -m scripts.gen_data_dictionary

site: analysis docs ## build static site into _site/
	$(BIN)/python -m site_builder.build

app: setup ## run the Streamlit dashboard (offline, from data/mart)
	$(BIN)/streamlit run app/streamlit_app.py

clean:
	rm -rf transform/target transform/logs _site data/*.duckdb
