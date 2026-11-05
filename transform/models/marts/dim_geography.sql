select
    geo_fips,
    state_abbr,
    geo_name,
    geo_level,
    census_region
from {{ ref('seed_geography') }}
