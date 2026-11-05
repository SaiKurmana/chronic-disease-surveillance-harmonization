-- USDSS state burden indicators: rename, type-cast, clean. No business logic.
with src as (
    select * from {{ latest_snapshot('usdss_state') }}
)
select
    'usdss_state'                                as source_key,
    _dataset_id                                  as dataset_id,
    {{ clean_text('state') }}                    as location_abbr,
    try_cast(year as integer)                    as year,
    {{ clean_text('topic') }}                    as topic,
    {{ clean_text('indicator') }}                as indicator,
    {{ clean_text('unit') }}                     as unit,
    try_cast(estimate as double)                 as estimate,
    try_cast(seestimate as double)               as standard_error,
    try_cast(lowerlimit as double)               as ci_low,
    try_cast(upperlimit as double)               as ci_high,
    {{ clean_text('estimatefootnote') }}         as footnote,
    {{ clean_text('datasource') }}               as data_source_raw,
    {{ clean_text('population') }}               as population,
    {{ clean_text('age') }}                      as age,
    {{ clean_text('race') }}                     as race,
    {{ clean_text('sex') }}                      as sex,
    {{ clean_text('education') }}                as education,
    {{ clean_text('other_stratification') }}     as other_stratification,
    _loaded_at                                   as loaded_at,
    _source_rows_updated_at::bigint              as source_rows_updated_at
from src
