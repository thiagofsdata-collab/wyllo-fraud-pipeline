{#
  Haversine distance in km between two lat/lng points.
  Used for customer<->seller geographic distance features.
#}
{% macro haversine_km(lat1, lng1, lat2, lng2) %}
    (
        6371 * 2 * asin(sqrt(
            power(sin(radians(({{ lat2 }} - {{ lat1 }}) / 2)), 2) +
            cos(radians({{ lat1 }})) * cos(radians({{ lat2 }})) *
            power(sin(radians(({{ lng2 }} - {{ lng1 }}) / 2)), 2)
        ))
    )
{% endmacro %}
