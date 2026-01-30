import requests
import zipfile
import io
from pathlib import Path

DATA_DIR = "/opt/airflow/dags/src/data_folder"
DATA_DIR_PATH = Path(DATA_DIR)
BASE_URL = (
    "https://eco2mix.rte-france.com/download/eco2mix/"
    "eCO2mix_RTE_Annuel-Definitif_{year}.zip"
)


def download_and_extract(
    start_year: int = 2012,
    target_dir: str = "./src/data_folder"
) -> list[Path]:
    """
    Télécharge et dézippe automatiquement les données éCO2mix annuelles
    depuis start_year jusqu'à la dernière année disponible.

    - S'arrête dès qu'une année n'est plus disponible
    - Extrait les fichiers directement dans data
    - Évite les doublons
    """

    DATA_DIR_PATH.mkdir(parents=True, exist_ok=True)

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
                output_file = DATA_DIR_PATH / member

                # Éviter de réécrire si le fichier existe déjà
                if output_file.exists():
                    print(f"Fichier déjà présent : {output_file.name}")
                    continue

                zip_file.extract(member, DATA_DIR_PATH)
                extracted_files.append(output_file)

        year += 1

    return extracted_files

