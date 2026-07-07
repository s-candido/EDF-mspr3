import requests
import pytest
from pytest_bdd import scenarios, given, when, then

from tests.deploy.steps.conftest import ECO2MIX_URL, OPENMETEO_URL

scenarios("../features/api_integration.feature")

# shared state between Given -> When -> Then steps within a scenario
_scenario_state: dict = {}


@given("the eco2mix RTE download URL is accessible")
def eco2mix_url_reachable():
    try:
        resp = requests.get(
            "https://eco2mix.rte-france.com", timeout=10
        )
        assert resp.status_code < 500
    except requests.ConnectionError:
        pytest.skip("eco2mix.rte-france.com is not reachable - skipping")


@when("I request the annual file for a valid year")
def request_eco2mix_file():
    url = ECO2MIX_URL.format(year=2023)
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        _scenario_state["eco2mix_status"] = resp.status_code
        _scenario_state["eco2mix_content_type"] = resp.headers.get(
            "Content-Type", ""
        )
    except requests.RequestException as exc:
        _scenario_state["eco2mix_status"] = 0
        _scenario_state["eco2mix_error"] = str(exc)


@then("I should receive a valid zip archive")
def verify_eco2mix_response():
    status = _scenario_state.get("eco2mix_status", 0)
    ctype = _scenario_state.get("eco2mix_content_type", "")

    if "eco2mix_error" in _scenario_state:
        pytest.skip(
            f"eco2mix download failed: {_scenario_state['eco2mix_error']}"
        )

    assert status == 200, f"Expected HTTP 200, got {status}"
    assert "zip" in ctype.lower(), f"Expected Content-Type to contain 'zip', got '{ctype}'"


@given("the Open-Meteo archive API is accessible")
def openmeteo_reachable():
    try:
        resp = requests.get(
            "https://archive-api.open-meteo.com", timeout=10
        )
        assert resp.status_code < 500
    except requests.ConnectionError:
        pytest.skip("archive-api.open-meteo.com is not reachable - skipping")


@when("I request hourly weather data for Paris")
def request_openmeteo_data():
    params = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "start_date": "2024-06-01",
        "end_date": "2024-06-02",
        "hourly": "temperature_2m",
        "timezone": "Europe/London",
    }
    try:
        resp = requests.get(OPENMETEO_URL, params=params, timeout=20)
        _scenario_state["openmeteo_status"] = resp.status_code
        _scenario_state["openmeteo_data"] = resp.json()
    except requests.RequestException as exc:
        _scenario_state["openmeteo_status"] = 0
        _scenario_state["openmeteo_error"] = str(exc)


@then("I should receive valid JSON with weather measurements")
def verify_openmeteo_response():
    if "openmeteo_error" in _scenario_state:
        pytest.skip(
            f"Open-Meteo API call failed: {_scenario_state['openmeteo_error']}"
        )

    status = _scenario_state.get("openmeteo_status", 0)
    assert status == 200, f"Expected HTTP 200, got {status}"

    data = _scenario_state.get("openmeteo_data", {})
    assert "hourly" in data, "Response JSON missing 'hourly' key"
    hourly = data["hourly"]
    assert "time" in hourly, "hourly data missing 'time' array"
    assert "temperature_2m" in hourly, "hourly data missing 'temperature_2m' array"
    assert len(hourly["temperature_2m"]) > 0, "temperature_2m array is empty"
