-- Silver: cleaned, typed orders. One row per order_id (deduped).
-- Casts timestamps, joins customer_unique_id (the stable identity), and
-- flags the cancellation-post-approval proxy.
with orders as (
    select * from {{ ref('br_orders') }}
),
customers as (
    select customer_id, customer_unique_id, customer_state, customer_zip_code_prefix
    from {{ ref('br_customers') }}
),
deduped as (
    select *,
        row_number() over (partition by order_id order by order_purchase_timestamp) as rn
    from orders
)
select
    d.order_id,
    c.customer_unique_id,
    d.customer_id,
    c.customer_state,
    c.customer_zip_code_prefix,
    d.order_status,
    try_cast(d.order_purchase_timestamp as timestamp)                  as order_purchase_ts,
    try_cast(d.order_approved_at as timestamp)                         as order_approved_ts,
    try_cast(d.order_delivered_customer_date as timestamp)             as order_delivered_ts,
    -- chargeback proxy: cancelled AFTER payment was approved.
    -- order_approved_ts is non-null only when payment cleared.
    case
        when d.order_status = 'canceled'
             and try_cast(d.order_approved_at as timestamp) is not null
        then true else false
    end                                                                as is_cancelled_post_approval
from deduped d
left join customers c on d.customer_id = c.customer_id
where d.rn = 1
