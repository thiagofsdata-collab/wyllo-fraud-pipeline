-- Silver: payments typed. Aggregated to order grain with risk-relevant fields.
select
    order_id,
    cast(payment_sequential as integer) as payment_sequential,
    payment_type,
    cast(payment_installments as integer) as payment_installments,
    cast(payment_value as double) as payment_value
from {{ ref('br_order_payments') }}
