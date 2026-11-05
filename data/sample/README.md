# Committed offline snapshot (real public data)

These parquet files are **verbatim, unmodified pulls of public, aggregate,
de-identified data from data.cdc.gov**, filtered with the `where` clauses in
[`sources.yml`](../../sources.yml). They are *not* synthetic and *not* edited.

They exist so that CI, the Streamlit app and the static site can be rebuilt
without network access. `_manifest.json` records, per source, the Socrata
dataset id, the filter, the upstream `rowsUpdatedAt` version and the UTC time
of the pull.

* Refresh locally: `make ingest` (pulls to `data/raw/`, then promotes here)
* Refresh automatically: `.github/workflows/data-refresh.yml` (weekly)
* Size guard: `python -m ingest.snapshot` refuses to promote more than 5 MB.
