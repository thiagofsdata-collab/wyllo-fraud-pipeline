{#
  Generates a monthly date spine between the earliest and latest order.
  Used to build the (customer, snapshot_date) grain of the feature store.
  DuckDB supports generate_series over dates natively.
#}
{% macro generate_month_spine() %}
    select cast(unnest(generate_series(
        date_trunc('month', (select min(order_purchase_ts) from {{ ref('stg_orders') }})),
        date_trunc('month', (select max(order_purchase_ts) from {{ ref('stg_orders') }})),
        interval '1 month'
    )) as date) as snapshot_date
{% endmacro %}
