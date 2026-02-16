import requests
import zipfile
import io
from pathlib import Path

from db.regions_log import already_ingested_region

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data_regions"


BASE_URL = "https://eco2mix.rte-france.com/download/eco2mix/"

REGIONS = [
    "Auvergne-Rhône-Alpes",
    "Bourgogne-Franche-Comté",
    "Bretagne",
    "Centre-Val de Loire",
    "Grand-Est",
    "Hauts-de-France",
    "Île-de-France",
    "Normandie",
    "Nouvelle-Aquitaine",
    "Occitanie",
    "PACA",
    "Pays-de-la-Loire"
]


def download_region_year(region: str, year: int) -> list[Path]:
    """
    Télécharge et extrait les données annuelles définitives
    pour une région donnée.
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"eCO2mix_RTE_{region}_Annuel-Definitif_{year}.zip"
    url = BASE_URL + filename

    print(f"Téléchargement {region} {year}")
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Non disponible : {region} {year}")
        return []

    extracted_files = []

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        for member in zip_file.namelist():
            output_path = DATA_DIR / member

            if output_path.exists():
                print("Déjà présent :", output_path.name)
                continue

            zip_file.extract(member, DATA_DIR)
            extracted_files.append(output_path)
            print("Extrait :", output_path.name)

    return extracted_files

def get_last_region_year(conn):
    cur = conn.cursor()
    cur.execute("SELECT MAX(EXTRACT(YEAR FROM date)) FROM eco2mix_region_raw")
    result = cur.fetchone()[0]
    cur.close()
    return int(result) if result else 2012


def download_all_regions(conn, start_year=2012):

    year = start_year

    while True:
        success_for_year = False

        for region in REGIONS:

            if already_ingested_region(conn, region, year):
                continue

            filename = f"eCO2mix_RTE_{region}_Annuel-Definitif_{year}.zip"
            url = BASE_URL + filename

            response = requests.head(url)

            if response.status_code == 200:
                print(f"Téléchargement : {region} {year}")
                download_region_year(region, year)
                success_for_year = True
            else:
                pass

        if not success_for_year:
            print(f"Aucune région disponible pour {year}, arrêt.")
            break

        year += 1
