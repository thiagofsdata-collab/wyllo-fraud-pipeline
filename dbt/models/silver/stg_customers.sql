-- Silver: customer dimension at unique-id grain.
-- Olist customer_id is per-order; customer_unique_id is the stable identity.
-- A single customer_unique_id can have MULTIPLE customer_id rows (one per
-- order) with different zip/state values (shipping to different addresses
-- over time). We keep ONE row per customer_unique_id with the most recent
-- zip/state — the "current state" interpretation appropriate for a
-- customer dimension feeding the feature store.
with customers_with_orders as (
    select
        c.customer_unique_id,
        c.customer_state,
        c.customer_zip_code_prefix,
        o.order_purchase_timestamp,
        row_number() over (
            partition by c.customer_unique_id
            order by o.order_purchase_timestamp desc nulls last
        ) as rn
    from {{ ref('br_customers') }} c
    left join {{ ref('br_orders') }} o
        on c.customer_id = o.customer_id
)
select
    customer_unique_id,
    customer_state,
    customer_zip_code_prefix
from customers_with_orders
where rn = 1