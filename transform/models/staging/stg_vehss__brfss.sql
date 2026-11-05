-- VEHSS BRFSS summary table: rename, type-cast, clean. No business logic.
with src as (
    select * from {{ latest_snapshot('vehss_brfss') }}
)
select
    'vehss_brfss'                                as source_key,
    _dataset_id                                  as dataset_id,
    try_cast(yearstart as integer)               as year_start,
    try_cast(yearend as integer)                 as year_end,
    {{ clean_text('locationabbr') }}             as location_abbr,
    {{ clean_text('locationdesc') }}             as location_name,
    {{ clean_text('geographic_level') }}         as geographic_level,
    {{ clean_text('datasource') }}               as data_source_raw,
    {{ clean_text('topic') }}                    as topic,
    {{ clean_text('category') }}                 as category,
    {{ clean_text('questionid') }}               as question_id,
    {{ clean_text('question') }}                 as question,
    {{ clean_text('response') }}                 as response,
    {{ clean_text('age') }}                      as age,
    {{ clean_text('sex') }}                      as sex,
    {{ clean_text('raceethnicity') }}            as race_ethnicity,
    {{ clean_text('riskfactor') }}               as risk_factor,
    {{ clean_text('riskfactorresponse') }}       as risk_factor_response,
    {{ clean_text('data_value_unit') }}          as unit,
    {{ clean_text('data_value_type') }}          as data_value_type,
    try_cast(data_value as double)               as estimate,
    try_cast(low_confidence_limit as double)     as ci_low,
    try_cast(high_confidence_limit as double)    as ci_high,
    {{ clean_text('data_value_footnote_symbol') }} as footnote_symbol,
    {{ clean_text('data_value_footnote') }}      as footnote,
    try_cast(numerator as double)                as numerator,
    try_cast(sample_size as double)              as sample_size,
    _loaded_at                                   as loaded_at,
    _source_rows_updated_at::bigint              as source_rows_updated_at
from src
