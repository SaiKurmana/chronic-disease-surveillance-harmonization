select
    strat_category,
    strat_value,
    strat_category || ':' || strat_value as strat_key,
    strat_label,
    sort_order,
    age_min,
    age_max,
    comparability_note
from {{ ref('seed_stratification_catalog') }}
