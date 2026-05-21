"""
City ↔ Region mapping for per-region consumption prediction.

Each French administrative region (RTE éCO2mix) is mapped to 1-2
representative cities whose weather data (Open-Meteo) serves as
features for predicting that region's consumption.

Usage:
    from db.city_region_mapping import (
        REGION_CITIES,
        get_cities_for_region,
        get_region_for_city,
        normalize_region_name,
        all_cities,
        all_regions,
        create_city_region_mapping_table,
        build_region_feature_table,
    )
"""

import re
import unicodedata

import psycopg2
from psycopg2 import sql

# ──────────────────────────────────────────────
# Mapping: each region → list of representative cities
# ──────────────────────────────────────────────
REGION_CITIES: dict[str, list[str]] = {
    "Auvergne-Rhône-Alpes": ["Clermont-Ferrand"],
    "Bourgogne-Franche-Comté": ["Dijon"],
    "Bretagne": ["Brest"],
    "Centre-Val de Loire": ["Orléans"],
    "Grand-Est": ["Metz"],
    "Hauts-de-France": ["Lille"],
    "Île-de-France": ["Paris"],
    "Normandie": ["Rouen"],
    "Nouvelle-Aquitaine": ["Bordeaux"],
    "Occitanie": ["Montpellier"],
    "PACA": ["Marseille", "Nice"],
    "Pays-de-la-Loire": ["Nantes"],
}

# ──────────────────────────────────────────────
# Lookup helpers
# ──────────────────────────────────────────────


def all_regions() -> list[str]:
    """Return sorted list of all region names."""
    return sorted(REGION_CITIES.keys())


def all_cities() -> list[str]:
    """Return sorted list of all mapped cities (no duplicates)."""
    seen: set[str] = set()
    for cities in REGION_CITIES.values():
        seen.update(cities)
    return sorted(seen)


def get_cities_for_region(region: str) -> list[str]:
    """Return the list of representative cities for a region."""
    return REGION_CITIES.get(region, [])


def get_region_for_city(city: str) -> str | None:
    """Return the region that a city belongs to, or None."""
    for region, cities in REGION_CITIES.items():
        if city in cities:
            return region
    return None


def normalize_region_name(region: str) -> str:
    """
    Normalize a region name for use in SQL table names.

    Examples:
        "Île-de-France"    → "ile_de_france"
        "Auvergne-Rhône-Alpes" → "auvergne_rhone_alpes"
        "PACA"             → "paca"
        "Pays-de-la-Loire" → "pays_de_la_loire"
    """
    name = region.lower().strip()
    # Replace accented chars with ASCII equivalents
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    # Replace non-alphanumeric with underscore
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name


# ──────────────────────────────────────────────
# PostgreSQL persistence
# ──────────────────────────────────────────────

CITY_REGION_TABLE = "city_region_mapping"


def create_city_region_mapping_table(conn: psycopg2.extensions.connection) -> None:
    """
    Create (if not exists) and populate the city_region_mapping table.

    Columns: city TEXT PRIMARY KEY, region TEXT
    """
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {CITY_REGION_TABLE} (
                city TEXT PRIMARY KEY,
                region TEXT NOT NULL
            );
        """)
        for region, cities in REGION_CITIES.items():
            for city in cities:
                cur.execute(
                    f"""
                    INSERT INTO {CITY_REGION_TABLE} (city, region)
                    VALUES (%s, %s)
                    ON CONFLICT (city) DO UPDATE SET region = EXCLUDED.region
                    """,
                    (city, region),
                )
        conn.commit()


# ──────────────────────────────────────────────
# Feature-table builder per region
# ──────────────────────────────────────────────

FEATURE_TABLE_PREFIX = "agg_conso_meteo_features"


def build_region_feature_table(
    conn: psycopg2.extensions.connection,
    region: str,
    replace: bool = False,
) -> str:
    """
    Create (or replace) the per-region feature table.

    Joins the region's consumption (from conso_clean_region) with the
    hourly weather data for each city mapped to this region.

    Args:
        conn: Active PostgreSQL connection.
        region: Region name (e.g. "Île-de-France").
        replace: If True, DROP the existing table before recreating.

    Returns:
        The name of the created table.
    """
    suffix = normalize_region_name(region)
    table_name = f"{FEATURE_TABLE_PREFIX}_{suffix}"

    cities = get_cities_for_region(region)
    if not cities:
        raise ValueError(f"No cities mapped for region: {region}")

    cities_quoted = ", ".join(f"'{c}'" for c in cities)

    if replace:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table_name)))
        conn.commit()

    sql_create = f"""
        CREATE TABLE IF NOT EXISTS {table_name} AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY w.datetime) AS id,
            w.city,
            cr.region,
            cr.consommation,
            w.temperature_2m,
            w.relative_humidity_2m,
            w.precipitation,
            w.snowfall,
            w.weather_code,
            EXTRACT(YEAR  FROM w.datetime)::INT AS year,
            EXTRACT(MONTH FROM w.datetime)::INT AS month,
            EXTRACT(DAY   FROM w.datetime)::INT AS day,
            EXTRACT(HOUR  FROM w.datetime)::INT AS hour,
            EXTRACT(DOW   FROM w.datetime)::INT AS dayofweek,
            CASE WHEN EXTRACT(DOW FROM w.datetime) IN (0, 6) THEN 1 ELSE 0 END AS weekend,
            w.datetime
        FROM weather_data w
        JOIN {CITY_REGION_TABLE} crm ON crm.city = w.city
        JOIN conso_clean_region cr
            ON cr.region = crm.region
            AND cr.year = EXTRACT(YEAR  FROM w.datetime)
            AND cr.month = EXTRACT(MONTH FROM w.datetime)
            AND cr.day   = EXTRACT(DAY   FROM w.datetime)
            AND cr.hour  = EXTRACT(HOUR  FROM w.datetime)
        WHERE crm.region = '{region}'
          AND w.city IN ({cities_quoted})
        ORDER BY w.datetime, w.city;
    """

    with conn.cursor() as cur:
        cur.execute(sql_create)
    conn.commit()

    # Add index on (city, datetime) for fast lookups
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{suffix}_city_dt "
            f"ON {table_name} (city, datetime);"
        )
    conn.commit()

    return table_name
