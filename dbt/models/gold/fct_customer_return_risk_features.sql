-- ============================================================================
-- THE FEATURE STORE
-- Grain: (customer_unique_id, snapshot_date) — point-in-time correct.
-- Each row = "what did this customer look like on this date, using ONLY
-- data available on or before that date?"
-- The FILTER (WHERE ts <= snapshot_date) clauses are what prevent leakage.
-- ============================================================================
with spine as (
    {{ generate_month_spine() }}
),
customers as (
    select distinct customer_unique_id from {{ ref('stg_customers') }}
),
orders as (
    select * from {{ ref('int_orders_enriched') }}
),
-- every customer x every month they could plausibly exist for
customer_months as (
    select c.customer_unique_id, s.snapshot_date
    from customers c
    cross join spine s
    where exists (
        select 1 from orders o
        where o.customer_unique_id = c.customer_unique_id
          and o.order_purchase_ts <= s.snapshot_date + interval '1 month'
    )
)
select
    cm.customer_unique_id,
    cm.snapshot_date,

    -- ---- dimensions
    max(o.customer_state) as customer_state,
    date_diff('day', min(o.order_purchase_ts), cm.snapshot_date) as days_since_first_order,

    -- ---- Family 1: Velocity (lifetime + windowed, point-in-time)
    count(o.order_id) filter (where o.order_purchase_ts <= cm.snapshot_date) as total_orders_lifetime,
    count(o.order_id) filter (
        where o.order_purchase_ts between cm.snapshot_date - interval '30 days' and cm.snapshot_date
    ) as orders_last_30d,
    count(o.order_id) filter (
        where o.order_purchase_ts between cm.snapshot_date - interval '7 days' and cm.snapshot_date
    ) as orders_last_7d,
    count(distinct o.primary_seller_id) filter (
        where o.order_purchase_ts between cm.snapshot_date - interval '7 days' and cm.snapshot_date
    ) as distinct_sellers_last_7d,
    coalesce(sum(o.order_value) filter (
        where o.order_purchase_ts between cm.snapshot_date - interval '30 days' and cm.snapshot_date
    ), 0) as total_spent_last_30d,

    -- ---- Family 2: Cancellation proxy
    coalesce(
        count(o.order_id) filter (where o.is_cancelled_post_approval and o.order_purchase_ts <= cm.snapshot_date)::double
        / nullif(count(o.order_id) filter (where o.order_purchase_ts <= cm.snapshot_date), 0)
    , 0) as cancel_rate_lifetime,
    count(o.order_id) filter (
        where o.is_cancelled_post_approval
          and o.order_purchase_ts between cm.snapshot_date - interval '30 days' and cm.snapshot_date
    ) as cancel_post_approval_count_30d,

    -- ---- Family 3: Review proxy
    avg(o.review_score) filter (where o.order_purchase_ts <= cm.snapshot_date) as avg_review_score,
    coalesce(
        count(o.order_id) filter (where o.is_low_review_delivered and o.order_purchase_ts <= cm.snapshot_date)::double
        / nullif(count(o.order_id) filter (where o.order_status='delivered' and o.order_purchase_ts <= cm.snapshot_date), 0)
    , 0) as low_review_on_delivered_rate,

    -- ---- Family 4: Geographic
    avg(o.customer_seller_distance_km) filter (where o.order_purchase_ts <= cm.snapshot_date)
                                                                                   as avg_customer_seller_distance_km,
    count(distinct o.customer_state) filter (
        where o.order_purchase_ts between cm.snapshot_date - interval '30 days' and cm.snapshot_date
    ) as distinct_shipping_states_30d

from customer_months cm
left join orders o
    on o.customer_unique_id = cm.customer_unique_id
   and o.order_purchase_ts <= cm.snapshot_date
group by cm.customer_unique_id, cm.snapshot_date
