-- BRFSS Prevalence & Trends (kidney + BLIND questions): rename, type-cast, clean.
with src as (
    select * from {{ latest_snapshot('brfss_prevalence') }}
)
select
    'brfss_prevalence'                           as source_key,
    _dataset_id                                  as dataset_id,
    try_cast(year as integer)                    as year,
    {{ clean_text('locationabbr') }}             as location_abbr,
    {{ clean_text('locationdesc') }}             as location_name,
    {{ clean_text('class') }}                    as class,
    {{ clean_text('topic') }}                    as topic,
    {{ clean_text('questionid') }}               as question_id,
    {{ clean_text('question') }}                 as question,
    {{ clean_text('response') }}                 as response,
    {{ clean_text('break_out_category') }}       as break_out_category,
    {{ clean_text('break_out') }}                as break_out,
    try_cast(sample_size as double)              as sample_size,
    try_cast(data_value as double)               as estimate,
    try_cast(confidence_limit_low as double)     as ci_low,
    try_cast(confidence_limit_high as double)    as ci_high,
    {{ clean_text('data_value_unit') }}          as unit,
    {{ clean_text('data_value_type') }}          as data_value_type,
    {{ clean_text('data_value_footnote_symbol') }} as footnote_symbol,
    {{ clean_text('data_value_footnote') }}      as footnote,
    {{ clean_text('datasource') }}               as data_source_raw,
    -- 'US' / 'UW' rows are medians of states, not national estimates
    {{ clean_text('locationdesc') }} ilike '%(median)%' as is_median_of_states,
    _loaded_at                                   as loaded_at,
    _source_rows_updated_at::bigint              as source_rows_updated_at
from src
