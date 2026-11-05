{#- Referential integrity on a multi-column key. -#}
{% test relationships_composite(model, to, columns, to_columns=none) %}
{%- set tcols = to_columns if to_columns else columns -%}
select m.*
from (select distinct {{ columns | join(', ') }} from {{ model }}) m
left join {{ to }} t
  on {% for c in columns -%}
     m.{{ c }} = t.{{ tcols[loop.index0] }}{% if not loop.last %} and {% endif %}
     {%- endfor %}
where t.{{ tcols[0] }} is null
{% endtest %}
