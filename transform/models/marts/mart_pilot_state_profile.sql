-- Pilot: state comparison and co-occurrence for the pilot indicators.
-- Uses each indicator's primary source and pilot measure, overall adults, states + DC,
-- in the most recent year that every pilot indicator has data for.
with pilot as (
    select indicator_id, pilot_measure_type
    from {{ ref('seed_indicator_catalog') }}
    where is_pilot
),
base as (
    select f.*
    from {{ ref('fct_indicator_estimates') }} f
    join pilot p
      on f.indicator_id = p.indicator_id
     and f.measure_type = p.pilot_measure_type
    where f.is_primary_source
      and f.geo_level = 'state'
      and f.strat_category = 'overall'
      and f.estimate is not null
),
years as (
    select year
    from base
    group by year
    having count(distinct indicator_id) = (select count(*) from pilot)
),
pilot_year as (
    select max(year) as year from years
),
scored as (
    select
        b.indicator_id,
        b.indicator_name,
        b.condition,
        b.measure_type,
        b.unit,
        b.year,
        b.geo_fips,
        b.geo_abbr,
        b.geo_name,
        b.estimate,
        b.ci_low,
        b.ci_high,
        b.source_key,
        b.dataset_id,
        rank() over (partition by b.indicator_id order by b.estimate desc) as state_rank,
        count(*) over (partition by b.indicator_id) as n_states,
        ntile(3) over (partition by b.indicator_id order by b.estimate desc, b.geo_fips) as tertile
    from base b
    join pilot_year y on b.year = y.year
)
select
    *,
    tertile = 1 as is_top_tertile,
    sum(case when tertile = 1 then 1 else 0 end) over (partition by geo_fips) as n_top_tertile_conditions,
    count(*) over (partition by geo_fips) as n_indicators_with_data
from scored
