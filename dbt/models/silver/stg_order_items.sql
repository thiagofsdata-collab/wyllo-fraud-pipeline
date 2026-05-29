-- Silver: one row per (order, item). Typed prices.
select
    order_id,
    cast(order_item_id as integer) as order_item_id,
    product_id,
    seller_id,
    cast(price as double) as price,
    cast(freight_value as double) as freight_value
from {{ ref('br_order_items') }}
