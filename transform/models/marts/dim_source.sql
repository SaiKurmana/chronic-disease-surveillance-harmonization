-- Provenance for every number: one row per registered source (from sources.yml).
select * from {{ ref('seed_source_registry') }}
