-- Harmonized indicator catalog plus coverage observed in the fact table.
with cat as (
    select * from {{ ref('seed_indicator_catalog') }}
),
cov as (
    select
        indicator_id,
        min(year) as first_year,
        max(year) as last_year,
        count(distinct source_key) as n_sources,
        string_agg(distinct source_key, ', ' order by source_key) as source_keys,
        string_agg(distinct measure_type, ', ' order by measure_type) as measure_types,
        any_value(unit) filter (where source_key = primary_source_key) as primary_unit
    from {{ ref('fct_indicator_estimates') }} f
    join cat using (indicator_id)
    group by indicator_id
)
select cat.*, cov.* exclude (indicator_id)
from cat
left join cov using (indicator_id)
