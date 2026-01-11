## Exemple Nomencalture PostgreSQL

```py

import psycopg2 as psycopg


def create_table(conn, table_name):

    # Creating a cursor object using the cursor() method meteo_all_cities
    curs = conn.cursor()

    # Create the table if it doesn't exist
    curs.execute(f'''CREATE TABLE IF NOT EXISTS {table_name} (
        db_id TEXT PRIMARY KEY,
        dt BIGINT NOT NULL,
        min_temp REAL,
        max_temp REAL,
        min_humidity INTEGER,
        max_humidity INTEGER,
        precipitation REAL,
        uv INTEGER,
        weather_icon TEXT,
        weather_desc TEXT,
        sunrise BIGINT,
        sunset BIGINT,
        latitude REAL,
        longitude REAL,
        city TEXT
    )''')
    conn.commit()
    return conn

def create_table_for_gps(conn, table_name):
    
    cur = conn.cursor()
    # Create table if it doesn't exist
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        insee_code VARCHAR(10),
        city_code VARCHAR(50),
        zip_code VARCHAR(10),
        label VARCHAR(50),
        latitude VARCHAR(50),
        longitude VARCHAR(50),
        department_name VARCHAR(100),
        department_number VARCHAR(10),
        region_name VARCHAR(100),
        region_geojson_name VARCHAR(100)
    );
    """
    cur.execute(create_table_query)
    conn.commit()
    
    return conn, table_name
def insert_db(conn, latitude, longitude, today_forecast,  city_name):
        
    curs = conn.cursor()
    
    db_id = city_name + '_' + str(today_forecast['dt'])

  # Check if the data already exists before inserting
    curs.execute("SELECT * FROM meteo_all_cities WHERE db_id=%s", (db_id,))
    existing_data = curs.fetchone()

    if not existing_data:
        # Insert the JSON data into the database
        curs.execute("INSERT INTO meteo_all_cities(db_id, dt, min_temp, max_temp, min_humidity, max_humidity, precipitation, uv, weather_icon, weather_desc, sunrise, sunset, latitude, longitude, city) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (db_id, today_forecast['dt'], today_forecast['T']['min'], today_forecast['T']['max'], today_forecast['humidity']['min'], today_forecast['humidity']['max'], today_forecast['precipitation']['24h'], today_forecast['uv'], today_forecast['weather12H']['icon'], today_forecast['weather12H']['desc'], today_forecast['sun']['rise'], today_forecast['sun']['set'], latitude, longitude, city_name))

        # Commit the changes
        conn.commit()
    
        # Verify the data was inserted correctly
        curs.execute("SELECT * FROM meteo_all_cities WHERE db_id=%s", (db_id,))
        inserted_data = curs.fetchone()
        
        print(inserted_data[1])
        
        
        # Print the inserted data
        print(f"Inserted data: {inserted_data[1]} in meteo_all_cities" )

    else:
        print(f"Data already exists: {existing_data[1]} in meteo_all_cities")

def load_json_to_postgres_function(conn, json_data, table_name):
    try:
        cur=conn.cursor()
        create_table_for_gps(conn, table_name)

        # Insert JSON data into the table
        for city in json_data["cities"]:
            insert_query = f"""
            INSERT INTO {table_name} (insee_code, city_code, zip_code, label, latitude, longitude, department_name, department_number, region_name, region_geojson_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            cur.execute(insert_query, (city["insee_code"], city["city_code"], city["zip_code"], city["label"], city["latitude"], city["longitude"], city["department_name"], city["department_number"], city["region_name"], city["region_geojson_name"]))
        conn.commit()

        print("Database created and connected")
    except Exception as e:

        print(f"An error occurred: {e}")

```