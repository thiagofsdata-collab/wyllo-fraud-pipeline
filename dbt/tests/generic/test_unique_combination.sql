{#
  Custom generic test: asserts the combination of columns is unique.
  Replaces dbt_utils.unique_combination_of_columns without the external
  dependency. Used to enforce the composite PK of the feature store.
#}
{% test unique_combination(model, combination_of_columns) %}
with grouped as (
    select
        {{ combination_of_columns | join(', ') }},
        count(*) as n
    from {{ model }}
    group by {{ combination_of_columns | join(', ') }}
    having count(*) > 1
)
select * from grouped
{% endtest %}
