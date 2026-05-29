-- Silver: reviews, deduped to latest per order, typed score.
with reviews as (
    select *,
        row_number() over (partition by order_id order by review_creation_date desc) as rn
    from {{ ref('br_order_reviews') }}
)
select
    review_id,
    order_id,
    cast(review_score as integer) as review_score,
    try_cast(review_creation_date as date) as review_creation_date
from reviews
where rn = 1
