-- All sources in one common pre-harmonization shape (still source vocabularies).
{% set parts = ['int_usdss__estimates', 'int_vehss__estimates', 'int_brfss__estimates', 'int_cdi__estimates'] %}
{% for p in parts %}
select
    source_key, dataset_id, source_indicator_code, source_indicator_text, source_measure,
    location_abbr, year, raw_strat_category, raw_strat_value, n_strat_dims,
    estimate, ci_low, ci_high, standard_error, footnote, data_status, data_source_raw, loaded_at
from {{ ref(p) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
