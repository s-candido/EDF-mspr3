import psycopg2


DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

SQL = """
DROP TABLE IF EXISTS aggregated_conso_weather;

CREATE TABLE aggregated_conso_weather AS
WITH conso AS (
    SELECT
        id AS conso_id,
        consommation,
        prevision_j_1,
        prevision_j,
        fioul,
        charbon,
        gaz,
        nucleaire,
        eolien,
        solaire,
        hydraulique,
        pompage,
        bioenergies,
        ech_physiques,
        taux_de_co2,
        ech_comm_angleterre,
        ech_comm_espagne,
        ech_comm_italie,
        ech_comm_suisse,
        ech_comm_allemagne_belgique,
        fioul_tac,
        fioul_cogen,
        fioul_autres,
        gaz_tac,
        gaz_cogen,
        gaz_ccg,
        gaz_autres,
        hydraulique_fil_de_leau_eclusee,
        hydraulique_lacs,
        hydraulique_step_turbinage,
        bioenergies_dechets,
        bioenergies_biomasse,
        bioenergies_biogaz,
        destockage_batterie,
        eolien_terrestre,
        eolien_offshore,
        stockage_batterie,
        year,
        month,
        day,
        hour,
        dayofweek,
        weekend,
        make_timestamp(year, month, day, hour, 0, 0) AS datetime
    FROM conso_clean
),
weather_fr AS (
    SELECT
        datetime,
        AVG(temperature_2m)          AS temp_fr,
        AVG(relative_humidity_2m)    AS hum_fr,
        AVG(snowfall)                AS snow_fr,
        AVG(precipitation)           AS rain_fr
    FROM weather_data
    GROUP BY datetime
)
SELECT
    ROW_NUMBER() OVER (ORDER BY c.datetime) AS id,
    c.*,
    w.temp_fr,
    w.hum_fr,
    w.snow_fr,
    w.rain_fr
FROM conso c
LEFT JOIN weather_fr w
    ON c.datetime = w.datetime
ORDER BY c.datetime;
"""

def ingest_conso_meteo():
    print("Connexion PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("Création de aggregated_conso_weather")
    cur.execute(SQL)

    cur.close()
    conn.close()
    print("aggregated_conso_weather créée")
