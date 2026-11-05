# SOP: Onboarding a new surveillance source

**Purpose:** add a new public dataset to the harmonized indicator model in a way
that is traceable, tested and reviewable.
**Applies to:** public, aggregate, de-identified data only. Do not onboard
record-level data, PHI, or licensed/commercial data.
**Time:** about 2–4 hours for a Socrata dataset with a familiar layout.

Think of it like adding a new lab instrument to a reference lab: you register
it, check its output format, map its codes to the lab's standard codes, run
controls, and document it before its results go into the shared report.

---

## 0. Eligibility checklist

- [ ] Published by a public agency on an open portal (for example data.cdc.gov).
- [ ] Aggregate estimates only (no record-level rows), with a stated license or public-domain status.
- [ ] Reports at least one indicator that maps to an existing or new harmonized `indicator_id`.
- [ ] Has, or documents the absence of, confidence intervals and suppression rules.

## 1. Discover and verify

1. Search the Socrata catalog. Do not guess dataset ids:
   ```bash
   curl -s "https://api.us.socrata.com/api/catalog/v1?domains=data.cdc.gov&only=dataset&q=<term>" \
     | python -m json.tool | less
   ```
2. Read the metadata (`https://data.cdc.gov/api/views/<id>.json`): name,
   attribution, license, `rowsUpdatedAt`, and column list.
3. Fetch a few rows and profile the values you will filter on:
   ```bash
   curl -sG "https://data.cdc.gov/resource/<id>.json" --data-urlencode '$limit=5'
   curl -sG "https://data.cdc.gov/resource/<id>.json" \
     --data-urlencode '$query=SELECT questionid, count(*) GROUP BY questionid'
   ```
4. Write down: indicator codes, measure types, stratifier columns, geography
   codes, suppression footnotes, and whether national/median rows exist.

## 2. Register the source

Add an entry to `sources.yml`:

```yaml
  - key: <short_snake_case>          # becomes data/raw/<key>/ and the dbt source name
    domain: diabetes|vision|kidney   # which ingest module owns it
    name: <exact dataset title>
    system: <publishing system>
    dataset_id: <4x4 id>
    url: https://data.cdc.gov/d/<id>
    api_endpoint: https://data.cdc.gov/resource/<id>.json
    publisher: <as published>
    license: <as published, or null>
    access_date: YYYY-MM-DD
    where: "<SoQL filter that keeps only the indicators you need>"
    verified_rows_total: <count(*) of the full dataset>
    notes: >-
      <layout quirks you found in step 1>
```

Then:

```bash
python -m scripts.sync_source_seed     # regenerate seed_source_registry.csv
python -m ingest.verify_sources        # metadata + 3 rows + filtered count
```

If the domain is new, add `ingest/<domain>.py` (copy an existing module) and
register it in `ingest/__main__.py`.

## 3. Ingest

```bash
.venv/bin/python -m ingest --domain <domain>   # pulls to data/raw/<key>/
.venv/bin/python -m ingest.snapshot            # promotes to data/sample/ (5 MB guard)
```

Check the log for the row-count assertion and the manifest entry in
`data/raw/_manifest.json`. If the snapshot guard trips, tighten `where`.

## 4. Staging model (rename, cast, clean only)

Create `transform/models/staging/stg_<system>__<dataset>.sql`:

```sql
with src as (select * from {{ latest_snapshot('<key>') }})
select
    '<key>'                         as source_key,
    _dataset_id                     as dataset_id,
    {{ clean_text('locationabbr') }} as location_abbr,
    try_cast(year as integer)       as year,
    try_cast(data_value as double)  as estimate,
    -- ... every column you need, renamed to snake_case, typed
    _loaded_at                      as loaded_at
from src
```

Rules: no joins, no filtering of real estimates, no recoding. Document the model
and add basic tests in `models/staging/_staging.yml`, and add the table to
`_sources.yml`.

## 5. Intermediate model (common shape)

Create `transform/models/intermediate/int_<system>__estimates.sql` that outputs
exactly the columns used by `int_estimates__unioned`:

`source_key, dataset_id, source_indicator_code, source_indicator_text,
source_measure, location_abbr, year, raw_strat_category, raw_strat_value,
n_strat_dims, estimate, ci_low, ci_high, standard_error, footnote, data_status,
data_source_raw, loaded_at`

* `source_measure`: the label you will crosswalk (combine columns if the source
  splits it, as USDSS does with `unit | age basis`).
* `raw_strat_category` / `raw_strat_value`: one stratifier per row; set
  `n_strat_dims` to the number of non-total stratifiers so cross-classified
  cells can be excluded.
* `data_status`: map the source's suppression footnotes to `reported`,
  `suppressed` or `not_available`. Quote the footnote text in a comment.

Add the model to the `parts` list in `int_estimates__unioned.sql`.

## 6. Crosswalk entries

Run the build once. The custom `unmapped_crosswalk_values` tests will fail and
list every value that needs a mapping:

```bash
make dbt-test
```

Add rows to:

| Seed | Add |
|---|---|
| `seed_indicator_crosswalk.csv` | `source_key, source_indicator_code, source_measure → indicator_id, measure_type, unit, include` (use `include=false` with a note for rows you deliberately exclude, e.g. counts) |
| `seed_indicator_catalog.csv` | only for a new harmonized indicator: definition, condition, primary source, pilot measure |
| `seed_stratification_crosswalk.csv` | each `raw_strat_category, raw_strat_value → strat_category, strat_value` |
| `seed_stratification_catalog.csv` | only for a new harmonized value (label, sort order, age bounds, comparability note) |
| `seed_data_source_crosswalk.csv` | each `data_source_raw → data_source` (BRFSS, USRDS, ...) |
| `seed_geography.csv` | only if the source uses a geography not yet listed |

Never map two different definitions onto one harmonized value just to make a
test pass. If a source band or group is not equivalent (for example VEHSS
"Asian" versus BRFSS "Asian, non-Hispanic"), give it its own value and a
comparability note.

## 7. Tests and checks

```bash
make test        # ruff + dbt build (all data tests) + pytest
make analysis    # regenerates the gap & overlap report
```

All error-severity tests must pass. Review:

- [ ] `unmapped_*` tests pass (crosswalks complete).
- [ ] Percent range and CI-bracket tests pass. If the source publishes impossible
      values, handle them visibly (flag + keep the published value), as done for
      negative VEHSS lower limits.
- [ ] The overlap section of `analysis/output/gap_report.md` shows sensible agreement
      if the new source duplicates an existing indicator.
- [ ] `fct_indicator_estimates` row count for the new source matches expectations
      (`analysis/output/gap_report.md` §1).

## 8. Documentation

- [ ] `sources.yml` entry complete (access date, license, notes).
- [ ] Model and column descriptions in the dbt YAML; run `make docs` to refresh
      `docs/data_dictionary.md`.
- [ ] Add the source's caveats to `docs/limitations.md`.
- [ ] Add a citation line to the README "Data sources" section.

## 9. Review and merge

Open a PR containing the registry entry, models, seeds, refreshed snapshot and
regenerated reports. CI runs ruff, dbt build and pytest on the committed
snapshot. A reviewer checks crosswalk choices against the source's documentation
before merging. After merge, the Pages workflow republishes the site and the
weekly refresh workflow keeps the new source current.
