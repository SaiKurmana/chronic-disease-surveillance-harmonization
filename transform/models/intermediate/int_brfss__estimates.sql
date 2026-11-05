-- BRFSS Prevalence -> common long shape. One stratifier per row already.
-- Median-of-states rows (US / UW) are not population estimates and are removed.
with s as (
    select * from {{ ref('stg_brfss__prevalence') }}
)
select
    source_key,
    dataset_id,
    question_id                                 as source_indicator_code,
    question                                    as source_indicator_text,
    data_value_type                             as source_measure,
    location_abbr,
    year,
    break_out_category                          as raw_strat_category,
    break_out                                   as raw_strat_value,
    case when break_out_category = 'Overall' then 0 else 1 end as n_strat_dims,
    estimate,
    ci_low,
    ci_high,
    cast(null as double)                        as standard_error,
    nullif(coalesce(footnote_symbol || ' ', '') || coalesce(footnote, ''), '') as footnote,
    case
        when footnote_symbol = '*' and estimate is null then 'suppressed'
        when estimate is null then 'not_available'
        else 'reported'
    end                                         as data_status,
    data_source_raw,
    loaded_at
from s
where not is_median_of_states
