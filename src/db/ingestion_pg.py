import psycopg2
import requests
import zipfile
import io
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

BASE_URL = (
    "https://eco2mix.rte-france.com/download/eco2mix/"
    "eCO2mix_RTE_Annuel-Definitif_{year}.zip"
)

# Database credentials
HOST = "localhost"
DB = "postgres"
USER = "postgres"
PASSWORD = "postgres"
PORT = 5441

def download_and_extract(
    start_year: int = 2012,
    target_dir: str = "../data"
) -> list[Path]:
    """
    Télécharge et dézippe automatiquement les données éCO2mix annuelles
    depuis start_year jusqu'à la dernière année disponible.

    - S'arrête dès qu'une année n'est plus disponible
    - Extrait les fichiers directement dans data
    - Évite les doublons
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    extracted_files = []
    year = start_year

    while True:
        url = BASE_URL.format(year=year)
        print(f"Vérification : {url}")

        response = requests.get(url)

        if response.status_code != 200:
            print(f"Fin de téléchargement à l'année {year - 1}")
            break

        print(f"download : {year}")

        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            for member in zip_file.namelist():
                output_file = DATA_DIR / member

                # Éviter de réécrire si le fichier existe déjà
                if output_file.exists():
                    print(f"Fichier déjà présent : {output_file.name}")
                    continue

                zip_file.extract(member, DATA_DIR)
                extracted_files.append(output_file)

        year += 1

    return extracted_files

def store_csv_to_postgres(file_path: Path, table_name: str):
    """
    Store the content of a CSV file into a PostgreSQL table.

    Args:
        file_path (Path): Path to the CSV file.
        table_name (str): Name of the table in PostgreSQL.
    """
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            database=DB, user=USER, password=PASSWORD, host=HOST, port=PORT
        )
        curs = conn.cursor()

        # Create the table if it doesn't exist
        curs.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                perimetre TEXT,
                nature TEXT,
                date DATE,
                heures TIME,
                consommation FLOAT,
                prevision_j_1 FLOAT,
                prevision_j FLOAT,
                fioul FLOAT,
                charbon FLOAT,
                gaz FLOAT,
                nucleaire FLOAT,
                eolien FLOAT,
                solaire FLOAT,
                hydraulique FLOAT,
                pompage FLOAT,
                bioenergies FLOAT,
                ech_physiques FLOAT,
                taux_de_co2 FLOAT,
                ech_comm_angleterre FLOAT,
                ech_comm_espagne FLOAT,
                ech_comm_italie FLOAT,
                ech_comm_suisse FLOAT,
                ech_comm_allemagne_belgique FLOAT,
                fioul_tac FLOAT,
                fioul_cogen FLOAT,
                fioul_autres FLOAT,
                gaz_tac FLOAT,
                gaz_cogen FLOAT,
                gaz_ccg FLOAT,
                gaz_autres FLOAT,
                hydraulique_fil_de_leau_eclusee FLOAT,
                hydraulique_lacs FLOAT,
                hydraulique_step_turbinage FLOAT,
                bioenergies_dechets FLOAT,
                bioenergies_biomasse FLOAT,
                bioenergies_biogaz FLOAT
            )
        ''')
        conn.commit()

        # Read and insert data from the CSV file
        with open(file_path, 'r', encoding='ISO-8859-1') as csv_file:  # Use ISO-8859-1 encoding for special characters
            reader = csv.reader(csv_file, delimiter=';')
            headers = next(reader)  # Skip the header row
            for row in reader:
                # Ensure the row has the correct number of columns
                if len(row) != len(headers):
                    print(f"Skipping row due to incorrect number of columns: {row}")
                    continue

                # Replace empty strings with None for NULL values in PostgreSQL
                row = [None if value == '' else value for value in row]

                # Insert data into the table
                curs.execute(f'''
                    INSERT INTO {table_name} (
                        perimetre, nature, date, heures, consommation, prevision_j_1, prevision_j, fioul, charbon, gaz,
                        nucleaire, eolien, solaire, hydraulique, pompage, bioenergies, ech_physiques, taux_de_co2,
                        ech_comm_angleterre, ech_comm_espagne, ech_comm_italie, ech_comm_suisse, ech_comm_allemagne_belgique,
                        fioul_tac, fioul_cogen, fioul_autres, gaz_tac, gaz_cogen, gaz_ccg, gaz_autres,
                        hydraulique_fil_de_leau_eclusee, hydraulique_lacs, hydraulique_step_turbinage,
                        bioenergies_dechets, bioenergies_biomasse, bioenergies_biogaz
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', row)

        conn.commit()
        print(f"Data from {file_path.name} has been inserted into {table_name}.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Download and extract CSV files
    csv_files = download_and_extract()

    # Store each CSV file into PostgreSQL
    for csv_file in csv_files:
        store_csv_to_postgres(csv_file, table_name="eco2mix_data")