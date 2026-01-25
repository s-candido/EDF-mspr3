import pandas as pd
import psycopg2
from datetime import datetime
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.data_loader import load_all_data
from src.data.weather_loader import fetch_weather
from src.features.features import create_features

DB_CONFIG = {
    "host": "edf_postgresl",
    "database": "postgres", 
    "user": "postgres",
    "password": "postgres",
    "port": 5432
}

WEATHER_TABLE_NAME = "weather_data"
FEATURES_TABLE_NAME = "features_data"
DATA_DIR = "/opt/airflow/dags/src/data_folder"

def create_weather_table(conn, table_name):
    curs = conn.cursor()
    curs.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            city VARCHAR(100),
            date TIMESTAMP WITH TIME ZONE NOT NULL,
            temperature_2m REAL,
            relative_humidity_2m REAL,
            snowfall REAL,
            precipitation REAL,
            weather_code INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(city, date)
        )
    ''')
    conn.commit()

def create_features_table(conn, table_name):
    curs = conn.cursor()
    curs.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            hour INTEGER,
            day INTEGER,
            month INTEGER,
            dayofweek INTEGER,
            weekend INTEGER,
            consommation REAL,
            fioul INTEGER,
            charbon INTEGER,
            gaz INTEGER,
            nucleaire INTEGER,
            eolien INTEGER,
            solaire INTEGER,
            hydraulique INTEGER,
            pompage INTEGER,
            bioenergies INTEGER,
            ech_physiques INTEGER,
            taux_de_co2 INTEGER,
            temperature_2m REAL,
            relative_humidity_2m REAL,
            snowfall REAL,
            precipitation REAL,
            weather_code INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

def insert_weather_data(conn, table_name, df):
    curs = conn.cursor()
    
    if 'city' not in df.columns:
        df['city'] = 'Unknown'
    
    inserted_count = 0
    for _, row in df.iterrows():
        row_dict = row.where(pd.notnull(row), None).to_dict()
        
        try:
            curs.execute(f'''
                INSERT INTO {table_name} 
                (city, date, temperature_2m, relative_humidity_2m, snowfall, precipitation, weather_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (city, date) DO NOTHING
            ''', (
                row_dict.get('city'),
                row_dict.get('date'),
                row_dict.get('temperature_2m'),
                row_dict.get('relative_humidity_2m'),
                row_dict.get('snowfall'),
                row_dict.get('precipitation'),
                row_dict.get('weather_code')
            ))
            inserted_count += 1
        except Exception as e:
            print(f"Error inserting weather data: {e}")
            continue
    
    conn.commit()
    print(f"Inserted {inserted_count} weather records into {table_name}")

def insert_features_data(conn, table_name, df):
    curs = conn.cursor()
    
    required_columns = [
        'hour', 'day', 'month', 'dayofweek', 'weekend',
        'consommation', 'fioul', 'charbon', 'gaz', 'nucleaire',
        'eolien', 'solaire', 'hydraulique', 'pompage', 'bioenergies',
        'ech_physiques', 'taux_de_co2', 'temperature_2m', 'relative_humidity_2m',
        'snowfall', 'precipitation', 'weather_code'
    ]
    
    for col in required_columns:
        if col not in df.columns:
            df[col] = None
    
    inserted_count = 0
    for _, row in df.iterrows():
        row_dict = row.where(pd.notnull(row), None).to_dict()
        
        try:
            curs.execute(f'''
                INSERT INTO {table_name} 
                (hour, day, month, dayofweek, weekend, consommation, fioul, charbon, gaz, 
                 nucleaire, eolien, solaire, hydraulique, pompage, bioenergies, ech_physiques, 
                 taux_de_co2, temperature_2m, relative_humidity_2m, snowfall, precipitation, weather_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                row_dict.get('hour'),
                row_dict.get('day'),
                row_dict.get('month'),
                row_dict.get('dayofweek'),
                row_dict.get('weekend'),
                row_dict.get('consommation'),
                row_dict.get('fioul'),
                row_dict.get('charbon'),
                row_dict.get('gaz'),
                row_dict.get('nucleaire'),
                row_dict.get('eolien'),
                row_dict.get('solaire'),
                row_dict.get('hydraulique'),
                row_dict.get('pompage'),
                row_dict.get('bioenergies'),
                row_dict.get('ech_physiques'),
                row_dict.get('taux_de_co2'),
                row_dict.get('temperature_2m'),
                row_dict.get('relative_humidity_2m'),
                row_dict.get('snowfall'),
                row_dict.get('precipitation'),
                row_dict.get('weather_code')
            ))
            inserted_count += 1
        except Exception as e:
            print(f"Error inserting features data: {e}")
            continue
    
    conn.commit()
    print(f"Inserted {inserted_count} features records into {table_name}")

def load_weather_data_to_db(start_date="2020-01-01", end_date="2020-12-31"):
    print(f"Fetching weather data from {start_date} to {end_date}")
    weather_df = fetch_weather(start_date, end_date)
    
    if weather_df.empty:
        print("No weather data fetched")
        return
    
    print(f"Fetched {len(weather_df)} weather records")
    
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        create_weather_table(conn, WEATHER_TABLE_NAME)
        insert_weather_data(conn, WEATHER_TABLE_NAME, weather_df)
        print("Weather data loaded successfully")
    finally:
        conn.close()

def load_features_to_db(data_dir=DATA_DIR):
    print(f"Loading consumption data from {data_dir}")
    consumption_df = load_all_data(data_dir)
    
    if consumption_df.empty:
        print("No consumption data loaded")
        return
    
    print(f"Loaded {len(consumption_df)} consumption records")
    
    features_df = create_features(consumption_df)
    print(f"Created features: {len(features_df)} records")
    
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        weather_query = f"""
        SELECT date, temperature_2m, relative_humidity_2m, snowfall, precipitation, weather_code
        FROM {WEATHER_TABLE_NAME}
        ORDER BY date
        """
        weather_df = pd.read_sql(weather_query, conn)
        
        if not weather_df.empty:
            if 'datetime' in features_df.columns:
                features_df['date'] = pd.to_datetime(features_df['datetime']).dt.date
            else:
                features_df['date'] = pd.to_datetime(features_df[['year', 'month', 'day']].astype(str).agg('-'.join, axis=1)).dt.date
            
            weather_df['date'] = pd.to_datetime(weather_df['date']).dt.date
            
            merged_df = features_df.merge(weather_df, on='date', how='left')
            print(f"Merged data: {len(merged_df)} records")
        else:
            merged_df = features_df
            print("No weather data available, using features only")
        
        create_features_table(conn, FEATURES_TABLE_NAME)
        insert_features_data(conn, FEATURES_TABLE_NAME, merged_df)
        print("Features data loaded successfully")
        
    finally:
        conn.close()

def run_full_pipeline(start_date="2020-01-01", end_date="2020-12-31", data_dir=DATA_DIR):
    print("Starting full data pipeline...")
    
    load_weather_data_to_db(start_date, end_date)
    load_features_to_db(data_dir)
    
    print("Pipeline completed successfully!")

if __name__ == "__main__":
    run_full_pipeline(
        start_date="2020-01-01",
        end_date="2020-12-31",
        data_dir=DATA_DIR
    )