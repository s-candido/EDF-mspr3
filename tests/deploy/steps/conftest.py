import os
import sys
from pathlib import Path

import pytest
import psycopg2

_src = Path(__file__).resolve().parents[3] / "dags" / "src"
sys.path.insert(0, str(_src))

DB_CONFIG = {
    "host": os.environ.get("TEST_DB_HOST", "localhost"),
    "database": os.environ.get("TEST_DB_NAME", "postgres"),
    "user": os.environ.get("TEST_DB_USER", "postgres"),
    "password": os.environ.get("TEST_DB_PASSWORD", "postgres"),
    "port": int(os.environ.get("TEST_DB_PORT", "5442")),
}

MLFLOW_URL = os.environ.get("TEST_MLFLOW_URL", "http://localhost:5001")

ECO2MIX_URL = (
    "https://eco2mix.rte-france.com/download/eco2mix"
    "/eCO2mix_RTE_Annuel-Definitif_{year}.zip"
)

OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "deploy: marks a deploy/integration test that requires Docker services",
    )


def _try_pg(max_attempts: int = 3) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            return True
        except psycopg2.OperationalError:
            if attempt == max_attempts:
                return False


def _try_mlflow() -> bool:
    try:
        from mlflow.tracking import MlflowClient
        client = MlflowClient(tracking_uri=MLFLOW_URL)
        client.search_experiments(max_results=1)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_conn():
    if not _try_pg():
        pytest.skip("PostgreSQL not reachable — start docker-compose.test.yml")
    conn = psycopg2.connect(**DB_CONFIG)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def mlflow_uri():
    if not _try_mlflow():
        pytest.skip("MLflow not reachable — start docker-compose.test.yml")
    return MLFLOW_URL


@pytest.fixture(autouse=True)
def _deploy_marker(request):
    request.node.add_marker(pytest.mark.deploy)
