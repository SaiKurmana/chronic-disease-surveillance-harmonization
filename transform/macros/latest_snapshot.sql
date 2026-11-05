{#-
  Read every raw parquet snapshot for a source and keep only the most recent
  load. Older snapshots stay on disk for audit; downstream sees one version.
-#}
{% macro latest_snapshot(source_key) -%}
(
    select *
    from read_parquet('{{ var("data_dir") }}/{{ source_key }}/*.parquet', union_by_name = true)
    qualify _loaded_at = max(_loaded_at) over ()
)
{%- endmacro %}
