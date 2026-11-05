-- VEHSS BRFSS -> common long shape. VEHSS publishes cross-classified cells
-- (e.g. age x sex x race). The harmonized model keeps one stratifier per row,
-- so cells with >1 non-total dimension are flagged here and dropped in the mart.
with s as (
    select * from {{ ref('stg_vehss__brfss') }}
),
shaped as (
    select
        *,
        (case when age <> '18 years and older' then 1 else 0 end)
          + (case when sex <> 'Both sexes' then 1 else 0 end)
          + (case when race_ethnicity <> 'All races' then 1 else 0 end)
          + (case when risk_factor <> 'All participants' then 1 else 0 end) as n_strat_dims
    from s
)
select
    source_key,
    dataset_id,
    question_id                                 as source_indicator_code,
    question                                    as source_indicator_text,
    data_value_type                             as source_measure,
    location_abbr,
    year_start                                  as year,
    case
        when age <> '18 years and older' then 'Age'
        when sex <> 'Both sexes' then 'Sex'
        when race_ethnicity <> 'All races' then 'RaceEthnicity'
        when risk_factor <> 'All participants' then 'RiskFactor: ' || risk_factor
        else 'Overall'
    end                                         as raw_strat_category,
    case
        when age <> '18 years and older' then age
        when sex <> 'Both sexes' then sex
        when race_ethnicity <> 'All races' then race_ethnicity
        when risk_factor <> 'All participants' then risk_factor_response
        else 'Overall'
    end                                         as raw_strat_value,
    n_strat_dims,
    estimate,
    ci_low,
    ci_high,
    cast(null as double)                        as standard_error,
    coalesce(footnote_symbol || ' ', '') || coalesce(footnote, '') as footnote,
    case
        when footnote_symbol = '#' then 'suppressed'
        when estimate is null then 'not_available'
        else 'reported'
    end                                         as data_status,
    data_source_raw,
    loaded_at
from shaped
where year_start = year_end
