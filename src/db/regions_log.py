def create_region_log_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eco2mix_region_log (
            region TEXT,
            year INTEGER,
            ingested_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (region, year)
        );
    """)
    conn.commit()
    cur.close()


def already_ingested_region(conn, region, year):
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM eco2mix_region_log
        WHERE region=%s AND year=%s
    """, (region, year))
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def log_region_year(conn, region, year):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO eco2mix_region_log (region, year)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (region, year))
    conn.commit()
    cur.close()
