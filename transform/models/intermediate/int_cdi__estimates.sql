-- CDI -> common long shape. CDI allows up to three stratification pairs; for the
-- indicators used here only pair 1 is populated (asserted by n_strat_dims test).
with s as (
    select * from {{ ref('stg_cdi__indicators') }}
)
select
    source_key,
    dataset_id,
    question_id                                 as source_indicator_code,
    question                                    as source_indicator_text,
    data_value_type                             as source_measure,
    location_abbr,
    year_start                                  as year,
    strat_category_1                            as raw_strat_category,
    strat_value_1                               as raw_strat_value,
    (case when strat_category_1 <> 'Overall' then 1 else 0 end)
      + (case when strat_category_2 is not null then 1 else 0 end)
      + (case when strat_category_3 is not null then 1 else 0 end) as n_strat_dims,
    estimate,
    ci_low,
    ci_high,
    cast(null as double)                        as standard_error,
    nullif(coalesce(footnote_symbol || ' ', '') || coalesce(footnote, ''), '') as footnote,
    case
        when footnote_symbol = '****' then 'suppressed'
        when estimate is null then 'not_available'
        else 'reported'
    end                                         as data_status,
    data_source_raw,
    loaded_at
from s
where year_start = year_end
