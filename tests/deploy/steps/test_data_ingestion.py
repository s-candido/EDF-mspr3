from pytest_bdd import scenarios, given, when, then

from dags.src.db.ingestion_postgre import (
    TABLE_DATA,
    clean_dataframe,
    insert_dataframe,
    create_tables,
)
import pandas as pd

scenarios("../features/data_ingestion.feature")

# shared state between Given -> When -> Then steps within a scenario
_scenario_state: dict = {}


@given("a PostgreSQL database is running and accessible")
def db_available(db_conn):
    assert db_conn is not None


@when("I run the data ingestion pipeline with a dummy CSV row")
def run_dummy_ingestion(db_conn):
    create_tables(db_conn)

    dummy = pd.DataFrame([
        {
            "perimetre": "France",
            "nature": "Consommation",
            "date": "2024-01-01",
            "heures": "12:00",
            "consommation": 50000,
            "prevision_j_1": 51000,
            "prevision_j": 50500,
            "fioul": 3000,
            "charbon": 2000,
            "gaz": 10000,
            "nucleaire": 30000,
            "eolien": 5000,
            "solaire": 0,
            "hydraulique": 4000,
            "pompage": 500,
            "bioenergies": 1500,
            "ech_physiques": 500,
            "taux_de_co2": 50,
            "ech_comm_angleterre": 0,
            "ech_comm_espagne": 0,
            "ech_comm_italie": 0,
            "ech_comm_suisse": 0,
            "ech_comm_allemagne_belgique": 0,
            "fioul_tac": None,
            "fioul_cogen": None,
            "fioul_autres": None,
            "gaz_tac": None,
            "gaz_cogen": None,
            "gaz_ccg": None,
            "gaz_autres": None,
            "hydraulique_fil_de_leau_eclusee": None,
            "hydraulique_lacs": None,
            "hydraulique_step_turbinage": None,
            "bioenergies_dechets": None,
            "bioenergies_biomasse": None,
            "bioenergies_biogaz": None,
            "stockage_batterie": None,
            "destockage_batterie": None,
            "eolien_terrestre": None,
            "eolien_offshore": None,
            "source_file": "dummy_test.csv",
        }
    ])

    cleaned = clean_dataframe(dummy)
    insert_dataframe(db_conn, cleaned)
    _scenario_state["dummy_count"] = len(dummy)


@then("the row should be persisted in the eco2mix_raw table")
def verify_row_persisted(db_conn):
    cur = db_conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_DATA}")
    count = cur.fetchone()[0]
    cur.close()
    assert count > 0, f"Expected at least 1 row in {TABLE_DATA}, found {count}"
