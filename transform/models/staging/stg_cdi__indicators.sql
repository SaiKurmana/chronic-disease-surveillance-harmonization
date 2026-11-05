-- U.S. Chronic Disease Indicators (CKD01, DIA01): rename, type-cast, clean.
with src as (
    select * from {{ latest_snapshot('cdi') }}
)
select
    'cdi'                                        as source_key,
    _dataset_id                                  as dataset_id,
    try_cast(yearstart as integer)               as year_start,
    try_cast(yearend as integer)                 as year_end,
    {{ clean_text('locationabbr') }}             as location_abbr,
    {{ clean_text('locationdesc') }}             as location_name,
    {{ clean_text('datasource') }}               as data_source_raw,
    {{ clean_text('topic') }}                    as topic,
    {{ clean_text('questionid') }}               as question_id,
    {{ clean_text('question') }}                 as question,
    {{ clean_text('datavalueunit') }}            as unit,
    {{ clean_text('datavaluetype') }}            as data_value_type,
    try_cast(datavalue as double)                as estimate,
    try_cast(lowconfidencelimit as double)       as ci_low,
    try_cast(highconfidencelimit as double)      as ci_high,
    {{ clean_text('datavaluefootnotesymbol') }}  as footnote_symbol,
    {{ clean_text('datavaluefootnote') }}        as footnote,
    {{ clean_text('stratificationcategory1') }}  as strat_category_1,
    {{ clean_text('stratification1') }}          as strat_value_1,
    {{ clean_text('stratificationcategory2') }}  as strat_category_2,
    {{ clean_text('stratification2') }}          as strat_value_2,
    {{ clean_text('stratificationcategory3') }}  as strat_category_3,
    {{ clean_text('stratification3') }}          as strat_value_3,
    _loaded_at                                   as loaded_at,
    _source_rows_updated_at::bigint              as source_rows_updated_at
from src
