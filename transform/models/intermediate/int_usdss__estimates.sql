-- USDSS -> common long shape. The `age` column mixes two concepts: the
-- standardization method ("Crude" / "Age-Adjusted") and age bands. Split them.
with s as (
    select * from {{ ref('stg_usdss__state_indicators') }}
),
shaped as (
    select
        *,
        case when age in ('Crude', 'Age-Adjusted') then age else 'Age-specific' end as age_basis,
        (case when age not in ('Crude', 'Age-Adjusted') then 1 else 0 end)
          + (case when race <> 'All' then 1 else 0 end)
          + (case when sex <> 'All' then 1 else 0 end)
          + (case when education <> 'All' then 1 else 0 end) as n_strat_dims
    from s
)
select
    source_key,
    dataset_id,
    indicator                                   as source_indicator_code,
    indicator                                   as source_indicator_text,
    unit || ' | ' || age_basis                  as source_measure,
    location_abbr,
    year,
    case
        when age_basis = 'Age-specific' then 'Age'
        when race <> 'All' then 'Race'
        when sex <> 'All' then 'Sex'
        when education <> 'All' then 'Education'
        else 'Overall'
    end                                         as raw_strat_category,
    case
        when age_basis = 'Age-specific' then age
        when race <> 'All' then race
        when sex <> 'All' then sex
        when education <> 'All' then education
        else 'Overall'
    end                                         as raw_strat_value,
    n_strat_dims,
    estimate,
    ci_low,
    ci_high,
    standard_error,
    footnote,
    case
        when footnote = 'Suppressed' then 'suppressed'
        when footnote = 'No Data' or estimate is null then 'not_available'
        else 'reported'
    end                                         as data_status,
    data_source_raw,
    loaded_at
from shaped
