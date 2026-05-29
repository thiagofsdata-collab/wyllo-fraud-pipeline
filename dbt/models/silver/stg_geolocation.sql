-- Silver: zip -> lat/lng, deduped to one centroid per zip prefix.
select
    geolocation_zip_code_prefix as zip_code_prefix,
    avg(cast(geolocation_lat as double)) as lat,
    avg(cast(geolocation_lng as double)) as lng
from {{ ref('br_geolocation') }}
group by 1
