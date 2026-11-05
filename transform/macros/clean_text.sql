{#- Trim, collapse internal whitespace, and turn empty strings into null. -#}
{% macro clean_text(col) -%}
nullif(trim(regexp_replace({{ col }}, '\s+', ' ', 'g')), '')
{%- endmacro %}
