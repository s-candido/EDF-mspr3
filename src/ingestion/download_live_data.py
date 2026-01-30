import requests
import zipfile
import io
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

LIVE_URL = "https://eco2mix.rte-france.com/download/eco2mix/eCO2mix_RTE_En-cours-TR.zip"

def download_and_extract_live() -> list[Path]:
    """
    Télécharge et extrait le fichier live RTE.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Téléchargement du fichier RTE live")
    response = requests.get(LIVE_URL)
    response.raise_for_status()

    extracted_files = []

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        for member in zip_file.namelist():
            output_file = DATA_DIR / member

            # on écrase l'ancien pour refresh
            if output_file.exists():
                output_file.unlink()

            zip_file.extract(member, DATA_DIR)
            extracted_files.append(output_file)
            print(f"Extrait : {output_file.name}")

    return extracted_files


def delete_live_files():
    """
    Supprime uniquement les fichiers live (En-cours) dans PROJECT_ROOT/data
    """

    deleted = 0

    for file in DATA_DIR.iterdir():
        if not file.is_file():
            continue

        name = file.name.lower()

        # signatures du fichier live
        if "en-cours" in name or "tr" in name:
            file.unlink()
            print("Supprimé :", file.name)
            deleted += 1

    if deleted == 0:
        print("Aucun fichier live à supprimer")

