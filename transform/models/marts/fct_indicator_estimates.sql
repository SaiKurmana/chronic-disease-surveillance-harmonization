-- Harmonized long-format indicator estimates across all source systems.
-- Grain: one row per source x indicator x measure_type x geography x year x stratum.
with u as (
    select * from {{ ref('int_estimates__unioned') }}
    where n_strat_dims <= 1                -- single-stratifier rows only (see gap report)
),
ixw as (
    select * from {{ ref('seed_indicator_crosswalk') }} where include
),
sxw as (
    select * from {{ ref('seed_stratification_crosswalk') }}
),
dsxw as (
    select * from {{ ref('seed_data_source_crosswalk') }}
),
geo as (
    select * from {{ ref('seed_geography') }}
),
ind as (
    select * from {{ ref('seed_indicator_catalog') }}
),
src as (
    select * from {{ ref('seed_source_registry') }}
),
joined as (
    select
        src.source_system,
        u.source_key,
        u.dataset_id,
        ind.condition,
        ixw.indicator_id,
        ind.indicator_name,
        u.source_indicator_code,
        u.source_indicator_text,
        u.source_measure,
        ixw.measure_type,
        ixw.unit,
        geo.geo_level,
        geo.geo_fips,
        geo.geo_name,
        u.location_abbr                       as geo_abbr,
        u.year,
        sxw.strat_category,
        sxw.strat_value,
        u.raw_strat_category,
        u.raw_strat_value,
        u.estimate,
        -- Some sources publish symmetric (Wald) intervals that dip below 0 for rare
        -- outcomes in small strata. Keep the published bound and floor the
        -- harmonized bound at 0 so percent CIs are valid; flag the change.
        case when ixw.unit = 'percent' and u.ci_low < 0 then 0 else u.ci_low end as ci_low,
        u.ci_high,
        u.ci_low                              as ci_low_published,
        coalesce(ixw.unit = 'percent' and u.ci_low < 0, false) as ci_low_floored_flag,
        u.standard_error,
        dsxw.data_source,
        u.data_source_raw,
        u.data_status,
        u.data_status = 'suppressed'          as suppressed_flag,
        u.footnote,
        u.source_key = ind.primary_source_key as is_primary_source,
        src.url                               as source_url,
        u.loaded_at
    from u
    inner join ixw
        on  u.source_key = ixw.source_key
        and u.source_indicator_code = ixw.source_indicator_code
        and u.source_measure = ixw.source_measure
    left join sxw
        on  u.source_key = sxw.source_key
        and u.raw_strat_category = sxw.raw_strat_category
        and u.raw_strat_value = sxw.raw_strat_value
    left join dsxw
        on  u.source_key = dsxw.source_key
        and u.data_source_raw = dsxw.data_source_raw
    left join geo on u.location_abbr = geo.state_abbr
    left join ind on ixw.indicator_id = ind.indicator_id
    left join src on u.source_key = src.source_key
)
select
    -- 64-bit prefix of md5 over the grain: compact, stable across rebuilds, uniqueness tested
    left(md5(concat_ws('|', source_key, indicator_id, measure_type, geo_fips, year,
                       strat_category, strat_value)), 16) as estimate_id,
    *
from joined
