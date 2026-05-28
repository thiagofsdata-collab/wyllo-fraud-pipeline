{#
  Custom generic test replicating dbt_utils.expression_is_true.
  Written in-house to avoid an external package dependency for a
  one-line check. Fails if any row does NOT satisfy the expression.
#}
{% test expression_is_true(model, column_name, expression) %}
select *
from {{ model }}
where not ({{ column_name }} {{ expression }})
{% endtest %}
