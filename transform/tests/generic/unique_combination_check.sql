{#- No duplicate rows across a set of columns (grain check, nulls treated as values). -#}
{% test unique_combination_check(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by all
having count(*) > 1
{% endtest %}
