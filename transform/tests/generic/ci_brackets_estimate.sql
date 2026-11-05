{#-
  ci_low <= estimate <= ci_high whenever all three are present. `tolerance`
  absorbs rounding in published values (sources round estimate and limits
  independently).
-#}
{% test ci_brackets_estimate(model, estimate='estimate', ci_low='ci_low', ci_high='ci_high', tolerance=0) %}
select *
from {{ model }}
where {{ estimate }} is not null
  and {{ ci_low }} is not null
  and {{ ci_high }} is not null
  and (
        {{ ci_low }} > {{ estimate }} + {{ tolerance }}
     or {{ estimate }} > {{ ci_high }} + {{ tolerance }}
  )
{% endtest %}
