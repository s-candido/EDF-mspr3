import openmeteo_requests
import psycopg2
import pandas as pd
import time
from openmeteo_requests.Client import OpenMeteoRequestsError

import requests_cache
from retry_requests import retry
from data.db_loader import DB_CONFIG

_LAST_CALL = 0
MIN_DELAY = 1.2

# TODO 
# Pour Moyenne nationale = Faire une moyenne des villes 
CITIES = {
    "Paris": (48.8566, 2.3522),
    "Marseille": (43.2965, 5.3698),
    "Bordeaux": (44.8378, -0.5792),
    "Brest": (48.3904, -4.4861),
    "Clermont-Ferrand": (45.7772, 3.0870),
    "Dijon": (47.3220, 5.0415),
    "Grenoble": (45.1885, 5.7245),
    "Lille": (50.6292, 3.0573),
    "Metz": (49.1193, 6.1757),
    "Montpellier": (43.6108, 3.8767),
    "Toulon": (43.1242, 5.9280),
    "Nancy": (48.6921, 6.1844),
    "Nantes": (47.2184, -1.5536),
    "Nice": (43.7102, 7.2620),
    "Orléans": (47.9029, 1.9093),
    "Rennes": (48.1173, -1.6778),
    "Rouen": (49.4431, 1.0993),
    "Saint-Etienne": (45.4397, 4.3872),
    "Strasbourg": (48.5734, 7.7521),
    "Toulouse": (43.6047, 1.4442),
    "Tours": (47.3941, 0.6848),
}


# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = -1)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://archive-api.open-meteo.com/v1/archive"

all_cities_data = []

def _fetch_weather_raw(start_date= str, end_date= str) -> pd.DataFrame :

    for city, (lat, lon) in CITIES.items():
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ["temperature_2m", "relative_humidity_2m", "snowfall", "precipitation", "weather_code"],
            "timezone": "Europe/London",
        }
        
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        
        print(f"Selected City : {city} ")


        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
        hourly_snowfall = hourly.Variables(2).ValuesAsNumpy()
        hourly_precipitation = hourly.Variables(3).ValuesAsNumpy()
        hourly_weather_code = hourly.Variables(4).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
            start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
            end =  pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = hourly.Interval()),
            inclusive = "left"
        )}
        
        hourly_data["city"] = city
        hourly_data["temperature_2m"] = hourly_temperature_2m
        hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
        hourly_data["snowfall"] = hourly_snowfall
        hourly_data["precipitation"] = hourly_precipitation
        hourly_data["weather_code"] = hourly_weather_code

        city_df = pd.DataFrame(hourly_data)
        all_cities_data.append(city_df)
        
    return pd.concat(all_cities_data, ignore_index=True)
              
def fetch_weather(start_date, end_date, max_retries=5):
    global _LAST_CALL

    now = time.time()
    elapsed = now - _LAST_CALL
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)

    try:
        _LAST_CALL = time.time()
        return _fetch_weather_raw(start_date, end_date)

    except OpenMeteoRequestsError as e:
        msg = str(e)

        if "Minutely API request limit exceeded" in msg and max_retries > 0:
            print("Quota météo atteint → pause 60s…")
            time.sleep(60)
            return fetch_weather(start_date, end_date, max_retries - 1)

        raise
