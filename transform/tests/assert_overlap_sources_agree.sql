-- Cross-source consistency check (warn only). Where two sources publish the same
-- harmonized indicator for the same state/year/stratum/measure (e.g. USDSS vs CDI
-- for diagnosed diabetes; VEHSS vs BRFSS Prevalence for difficulty seeing),
-- flag pairs whose point estimates differ by more than 1.0 percentage point.
{{ config(severity='warn') }}
with f as (
    select * from {{ ref('fct_indicator_estimates') }}
    where estimate is not null and unit = 'percent'
)
select
    a.indicator_id, a.measure_type, a.geo_abbr, a.year, a.strat_category, a.strat_value,
    a.source_key as source_a, a.estimate as estimate_a,
    b.source_key as source_b, b.estimate as estimate_b,
    abs(a.estimate - b.estimate) as abs_diff
from f a
join f b
  on  a.indicator_id = b.indicator_id
  and a.measure_type = b.measure_type
  and a.geo_fips = b.geo_fips
  and a.year = b.year
  and a.strat_category = b.strat_category
  and a.strat_value = b.strat_value
  and a.source_key < b.source_key
where abs(a.estimate - b.estimate) > 1.0
