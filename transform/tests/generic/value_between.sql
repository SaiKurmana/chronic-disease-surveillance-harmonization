{#- Column values must fall within [min_value, max_value] (nulls ignored). -#}
{% test value_between(model, column_name, min_value, max_value, where=none) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
  {% if where %}and {{ where }}{% endif %}
{% endtest %}
