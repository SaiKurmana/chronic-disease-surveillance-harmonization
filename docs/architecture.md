# Architecture

The lab is a small, file-based lakehouse: Python pulls public data into a raw
parquet zone, dbt (on DuckDB) harmonizes it into one indicator model, and two
lightweight front ends serve the result. No cloud warehouse, no servers to run.

```mermaid
flowchart TB
  subgraph S["Public sources (data.cdc.gov)"]
    direction LR
    A["USDSS state indicators<br/>b559-sbez"]
    B["VEHSS · BRFSS<br/>vkwg-yswv"]
    C["BRFSS Prevalence<br/>dttw-5yxu"]
    D["Chronic Disease Indicators<br/>hksd-2xuw"]
  end
  subgraph I["Ingest · Python"]
    direction LR
    I1["ingest/diabetes.py"]
    I2["ingest/vision.py"]
    I3["ingest/kidney.py"]
  end
  R[("data/raw · timestamped parquet<br/>+ _manifest.json")]
  SN[("data/sample · committed<br/>offline snapshot")]
  subgraph T["Transform · dbt + DuckDB"]
    direction LR
    ST["staging<br/>rename · cast · clean"]
    IN["intermediate<br/>common long shape"]
    SE["seeds<br/>crosswalks · FIPS · registry"]
    M["marts<br/>fct_indicator_estimates<br/>dim_* · pilot profile"]
    TE{{"dbt tests"}}
  end
  MA[("data/mart · committed parquet")]
  subgraph V["Serve"]
    direction LR
    AN["analysis/<br/>gap report · pilot"]
    APP["Streamlit app"]
    SITE["Static site<br/>GitHub Pages"]
  end
  A --> I1
  B --> I2
  C --> I3
  D --> I3
  I1 & I2 & I3 --> R --> SN --> ST --> IN --> M
  SE --> M
  M --> TE
  M --> MA --> AN & APP
  AN --> SITE
  TE --> SITE
```

## Layers

| Layer | Where | What it does | Key guarantees |
|---|---|---|---|
| Registry | `sources.yml` | One entry per dataset: id, URL, publisher, license, filter, access date | Single source of truth; `seed_source_registry.csv` is generated from it and a test fails on drift |
| Ingest | `ingest/` | Paged SODA pulls ordered by `:id`; per-domain modules | Retries with exponential backoff (429/5xx), no retry on other 4xx; row-count check against `count(*)`; idempotent (skips when upstream `rowsUpdatedAt` and filter are unchanged); stable schema even for all-null columns |
| Raw zone | `data/raw/<key>/<key>__<UTC>.parquet` | Immutable snapshots with `_loaded_at`, `_dataset_id`, `_source_rows_updated_at` | Last 3 snapshots kept; dbt reads only the latest |
| Offline snapshot | `data/sample/` | Verbatim copy of the latest real pull, committed | < 5 MB guard; lets CI, the app and the site build with no network |
| Staging | `transform/models/staging` | Rename, type-cast, trim/collapse whitespace | No business logic |
| Intermediate | `transform/models/intermediate` | Reshape four layouts into one long shape; derive measure basis and data status | Crosswalk completeness tested here |
| Seeds | `transform/seeds` | Indicator, stratification and data-source crosswalks; indicator catalog; state FIPS | Mappings are data, reviewed in PRs |
| Marts | `transform/models/marts` | `fct_indicator_estimates`, `dim_indicator`, `dim_geography`, `dim_stratification`, `dim_source`, `mart_pilot_state_profile` | Provenance on every row; tested keys, ranges and relationships |
| Serve | `app/`, `site_builder/`, `analysis/` | Dashboard, static site, reports | Read committed marts only |

## The harmonized model

```mermaid
erDiagram
  fct_indicator_estimates }o--|| dim_indicator : indicator_id
  fct_indicator_estimates }o--|| dim_geography : geo_fips
  fct_indicator_estimates }o--|| dim_stratification : "strat_category + strat_value"
  fct_indicator_estimates }o--|| dim_source : source_key
  fct_indicator_estimates {
    string estimate_id PK
    string source_system
    string condition
    string indicator_id FK
    string measure_type
    string unit
    string geo_level
    string geo_fips FK
    int year
    string strat_category FK
    string strat_value FK
    double estimate
    double ci_low
    double ci_high
    string data_source
    bool suppressed_flag
  }
```

Grain: one row per **source × indicator × measure type × geography × year × stratum**.
The same harmonized indicator can appear from more than one source (for example
diagnosed diabetes from USDSS and from CDI). `dim_indicator.primary_source_key`
names the source used for headline comparisons; `is_primary_source` marks those
rows, and the others stay available for overlap checks.

## Quality gates

`dbt build` runs every model and test in dependency order; a failing test stops
downstream models from building.

* **Keys and grain**: `estimate_id` unique and not null, plus a composite grain check.
* **Domains**: accepted values for condition, measure type, unit, geo level,
  stratification category and data source.
* **Ranges**: percentages within 0–100; rates non-negative; years in range.
* **Statistical sanity**: `ci_low <= estimate <= ci_high` (0.05 tolerance for
  independently rounded published values).
* **Referential integrity**: every fact row joins to each dimension, including the
  two-column stratification key.
* **Crosswalk completeness** (custom `unmapped_crosswalk_values` test): every
  source indicator/measure, stratifier, location and data-source label seen in
  the data must be mapped. A new upstream value fails the build with the exact
  combination to add.
* **Cross-source agreement** (warn only): flags cells where two sources disagree
  by more than 1 percentage point.

## CI/CD

| Workflow | Trigger | Steps |
|---|---|---|
| `ci.yml` | pull request, push to non-main branches | ruff, `dbt build` on the committed snapshot, pytest |
| `pages.yml` | push to `main`, manual | `make site` then `actions/deploy-pages` |
| `data-refresh.yml` | weekly (Mondays 09:17 UTC), manual | `make ingest` (live pull), `make transform`, regenerate reports, open a PR with the refreshed snapshot |

The refresh workflow never pushes to `main` directly: new data arrives as a pull
request, so the dbt tests and a human review gate every upstream change.
