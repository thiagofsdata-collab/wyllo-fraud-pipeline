-- Intermediate: one row per order with everything needed for feature
-- aggregation downstream — payment, review, geo distance joined in.
with orders as (
    select * from {{ ref('stg_orders') }}
),
payments_agg as (
    select
        order_id,
        sum(payment_value)                          as order_value,
        max(payment_installments)                   as max_installments,
        count(*)                                    as payment_slices,
        -- primary payment type = highest value slice
        arg_max(payment_type, payment_value)        as primary_payment_type
    from {{ ref('stg_order_payments') }}
    group by 1
),
reviews as (
    select order_id, review_score from {{ ref('stg_order_reviews') }}
),
items_seller as (
    select
        order_id,
        arg_min(seller_id, order_item_id)           as primary_seller_id
    from {{ ref('stg_order_items') }}
    group by 1
),
cust_geo as (
    select customer_unique_id, zip_code_prefix, lat as cust_lat, lng as cust_lng
    from {{ ref('stg_customers') }} c
    left join {{ ref('stg_geolocation') }} g
        on c.customer_zip_code_prefix = g.zip_code_prefix
),
seller_geo as (
    select s.seller_id, g.lat as seller_lat, g.lng as seller_lng
    from {{ ref('br_sellers') }} s
    left join {{ ref('stg_geolocation') }} g
        on s.seller_zip_code_prefix = g.zip_code_prefix
)
select
    o.order_id,
    o.customer_unique_id,
    o.customer_state,
    o.order_status,
    o.order_purchase_ts,
    o.order_approved_ts,
    o.order_delivered_ts,
    o.is_cancelled_post_approval,
    coalesce(p.order_value, 0)                       as order_value,
    p.primary_payment_type,
    p.max_installments,
    i.primary_seller_id,
    r.review_score,
    case when o.order_status = 'delivered' and r.review_score <= 2
         then true else false end                    as is_low_review_delivered,
    case when o.order_status = 'delivered' and r.review_score is null
         then true else false end                    as is_no_review_delivered,
    {{ haversine_km('cg.cust_lat', 'cg.cust_lng', 'sg.seller_lat', 'sg.seller_lng') }}
                                                      as customer_seller_distance_km
from orders o
left join payments_agg p on o.order_id = p.order_id
left join reviews r      on o.order_id = r.order_id
left join items_seller i on o.order_id = i.order_id
left join cust_geo cg    on o.customer_unique_id = cg.customer_unique_id
left join seller_geo sg  on i.primary_seller_id = sg.seller_id
