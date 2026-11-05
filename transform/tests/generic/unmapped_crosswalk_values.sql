{#-
  Custom test: every distinct combination of `columns` in the model must exist in
  the crosswalk (matched on `crosswalk_columns`, same order). Returns the
  unmapped combinations with their row counts, so a failure tells you exactly
  which crosswalk entries to add (see docs/SOP_onboarding_a_new_source.md).
-#}
{% test unmapped_crosswalk_values(model, columns, crosswalk, crosswalk_columns=none, where=none) %}
{%- set xcols = crosswalk_columns if crosswalk_columns else columns -%}
with observed as (
    select {{ columns | join(', ') }}, count(*) as n_rows
    from {{ model }}
    {% if where %}where {{ where }}{% endif %}
    group by all
),
xw as (
    select distinct {{ xcols | join(', ') }} from {{ crosswalk }}
)
select o.*
from observed o
left join xw
  on {% for c in columns -%}
     o.{{ c }} is not distinct from xw.{{ xcols[loop.index0] }}{% if not loop.last %} and {% endif %}
     {%- endfor %}
where xw.{{ xcols[0] }} is null
{% endtest %}
