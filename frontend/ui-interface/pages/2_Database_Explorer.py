"""
Database Explorer — Browse all PostgreSQL tables and inspect temporal data coverage.

Use this page to:
- See every table in the database with row counts
- Know exactly how many years, months, days, hours of data you have
- Decide when you can train your model
- Preview table contents
"""

import os
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

st.set_page_config(
    page_title="Database Explorer",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME", "postgres"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
    "port": int(os.environ.get("DB_PORT", "5441")),
}


@st.cache_resource
def get_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


def fetch_all_tables(conn):
    query = """
        SELECT
            t.table_name,
            (SELECT count(*)::int
             FROM information_schema.columns c
             WHERE c.table_name = t.table_name) AS column_count
        FROM information_schema.tables t
        WHERE t.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name
    """
    return pd.read_sql_query(query, conn)


def get_row_count(conn, table):
    df = pd.read_sql_query(f'SELECT COUNT(*) AS cnt FROM "{table}"', conn)
    return int(df["cnt"].iloc[0]) if not df.empty else 0


def detect_temporal_columns(conn, table):
    cols = pd.read_sql_query(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        conn,
        params=(table,),
    )
    names = set(cols["column_name"])
    types = dict(zip(cols["column_name"], cols["data_type"]))

    # Priority 1: native timestamp/datetime column
    if "datetime" in names:
        dtype = types.get("datetime", "")
        if "timestamp" in dtype.lower() or "date" in dtype.lower():
            return "datetime", "datetime"

    if "date" in names and "heure" in names:
        return "date_heure", ("date", "heure")

    # Priority 2: year/month/day/hour integer columns
    has_y = "year" in names
    has_m = "month" in names
    has_d = "day" in names
    has_h = "hour" in names
    if has_y:
        return "ymdh", ("year", "month", "day", "hour")

    # Priority 3: any 'date' typed column
    date_cols = [c for c, t in types.items() if "date" in t.lower() or "timestamp" in t.lower()]
    if date_cols:
        return "generic_date", date_cols[0]

    return None, None


def analyze_datetime_column(conn, table, col):
    """Full temporal coverage for a table with a proper datetime column."""
    sql = f"""
        SELECT
            MIN({col})::text                        AS min_date,
            MAX({col})::text                        AS max_date,
            COUNT(*)::int                           AS total_rows,
            COUNT(DISTINCT EXTRACT(YEAR  FROM {col}))::int AS years,
            COUNT(DISTINCT EXTRACT(MONTH FROM {col}))::int  AS months,
            COUNT(DISTINCT EXTRACT(DAY   FROM {col}))::int  AS days,
            COUNT(DISTINCT EXTRACT(HOUR  FROM {col}))::int  AS hours
        FROM "{table}"
        WHERE {col} IS NOT NULL
    """
    return pd.read_sql_query(sql, conn)


def analyze_date_heure_columns(conn, table, date_col, heure_col):
    """Temporal coverage for tables with separate date + heure text columns."""
    sql = f"""
        SELECT
            MIN({date_col})::text                              AS min_date,
            MAX({date_col})::text                              AS max_date,
            COUNT(*)::int                                      AS total_rows,
            COUNT(DISTINCT SUBSTRING({date_col}, 1, 4))::int   AS years,
            COUNT(DISTINCT SUBSTRING({date_col}, 6, 2))::int   AS months,
            COUNT(DISTINCT {date_col})::int                    AS days,
            COUNT(DISTINCT {heure_col})::int                   AS hours
        FROM "{table}"
        WHERE {date_col} IS NOT NULL
    """
    return pd.read_sql_query(sql, conn)


def analyze_ymdh_columns(conn, table, cols):
    """Temporal coverage for tables with year/month/day/hour int columns."""
    y, m, d, h = cols
    sql = f"""
        SELECT
            MIN({y})::text || '-' || MIN({m})::text  AS min_date,
            MAX({y})::text || '-' || MAX({m})::text  AS max_date,
            COUNT(*)::int                            AS total_rows,
            COUNT(DISTINCT {y})::int                 AS years,
            COUNT(DISTINCT {m})::int                 AS months,
            COUNT(DISTINCT {d})::int                 AS days,
            COUNT(DISTINCT {h})::int                 AS hours,
            ARRAY_AGG(DISTINCT {y}::int ORDER BY {y}::int) AS year_list
        FROM "{table}"
    """
    return pd.read_sql_query(sql, conn)


def analyze_generic_date_column(conn, table, col):
    """Fallback for any date/timestamp column."""
    sql = f"""
        SELECT
            MIN({col})::text AS min_date,
            MAX({col})::text AS max_date,
            COUNT(*)::int    AS total_rows
        FROM "{table}"
        WHERE {col} IS NOT NULL
    """
    return pd.read_sql_query(sql, conn)


def preview_table(conn, table, limit=50):
    return pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT {limit}', conn)


def delete_table(conn, table_name):
    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
    conn.commit()


def temporal_summary_box(label, value):
    st.markdown(
        f"""
        <div style="
            background: #1a1a2e;
            border-radius: 8px;
            padding: 10px 14px;
            text-align: center;
            border: 1px solid #333;
        ">
            <div style="font-size: 0.7rem; color: #aaa; text-transform: uppercase;">
                {label}
            </div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #f0f0f0;">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.title("🗄️ Database Explorer")
    st.markdown(
        "Browse all database tables and inspect **temporal data coverage** — "
        "know exactly how many years, months, days, and hours of data are available "
        "to train your model."
    )

    conn = get_connection()
    if not conn:
        st.warning("Could not connect to the database. Check your connection settings.")
        return

    # ---- Fetch table list ----
    with st.spinner("Scanning database tables…"):
        tables_df = fetch_all_tables(conn)

    if tables_df.empty:
        st.info("No tables found in the public schema.")
        return

    st.success(f"Found **{len(tables_df)}** tables in the database")
    st.markdown("---")

    # ---- Per-table analysis ----
    for _, row in tables_df.iterrows():
        table = row["table_name"]
        col_count = row["column_count"]

        with st.expander(f"📋 **{table}** ({col_count} columns)", expanded=False):
            row_count = get_row_count(conn, table)

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Table:** `{table}`")
                st.caption(f"Columns: {col_count}  •  Rows: {row_count:,}")
            with col2:
                if row_count > 0:
                    st.button(
                        "🔍 Preview",
                        key=f"preview_{table}",
                        help="Show first 50 rows",
                    )

            if row_count == 0:
                st.info("This table is empty.")
                continue

            # ---- Temporal analysis ----
            kind, cols = detect_temporal_columns(conn, table)

            if kind is None:
                st.caption("⏱️ No temporal columns detected.")
                col_df = pd.read_sql_query(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    """,
                    conn,
                    params=(table,),
                )
                st.dataframe(col_df, use_container_width=True, hide_index=True)
                continue

            try:
                if kind == "datetime":
                    info = analyze_datetime_column(conn, table, cols)
                elif kind == "date_heure":
                    info = analyze_date_heure_columns(conn, table, *cols)
                elif kind == "ymdh":
                    info = analyze_ymdh_columns(conn, table, cols)
                elif kind == "generic_date":
                    info = analyze_generic_date_column(conn, table, cols)
                else:
                    info = pd.DataFrame()
            except Exception as e:
                st.warning(f"Could not analyze temporal coverage: {e}")
                continue

            if info.empty:
                continue

            r = info.iloc[0]

            # ── Coverage metrics ──
            st.markdown("**📅 Temporal Coverage**")

            if kind in ("datetime", "date_heure", "ymdh"):
                metrics_cols = st.columns(5)
                with metrics_cols[0]:
                    temporal_summary_box("Years", int(r["years"]) if pd.notna(r["years"]) else "—")
                with metrics_cols[1]:
                    temporal_summary_box("Months", int(r["months"]) if pd.notna(r["months"]) else "—")
                with metrics_cols[2]:
                    temporal_summary_box("Days", int(r["days"]) if pd.notna(r["days"]) else "—")
                with metrics_cols[3]:
                    temporal_summary_box("Hours", int(r["hours"]) if pd.notna(r["hours"]) else "—")
                with metrics_cols[4]:
                    temporal_summary_box("Rows", int(r["total_rows"]) if pd.notna(r["total_rows"]) else "—")

                min_d = str(r["min_date"])[:10] if pd.notna(r["min_date"]) else "—"
                max_d = str(r["max_date"])[:10] if pd.notna(r["max_date"]) else "—"
                st.markdown(f"**Range:** `{min_d}` → `{max_d}`")

                # Year list for ymdh tables
                ylv = r.get("year_list")
                if kind == "ymdh" and ylv is not None:
                    years_avail = sorted(ylv)
                    st.markdown(
                        f"**Years in table:** {' · '.join(str(y) for y in years_avail)}"
                    )

                # Model readiness indicator
                if kind in ("ymdh", "datetime", "date_heure"):
                    y_count = int(r["years"]) if pd.notna(r["years"]) else 0
                    if y_count >= 3:
                        st.success(
                            f"✅ **{y_count} years** of data — sufficient for model training!"
                        )
                    elif y_count >= 1:
                        st.warning(
                            f"⚠️ Only **{y_count} year(s)** — consider collecting more data."
                        )
                    else:
                        st.info("No temporal data available yet.")

            else:
                # generic date — just show range
                st.markdown(
                    f"**Range:** `{r['min_date']}` → `{r['max_date']}`  •  "
                    f"**Rows:** {r['total_rows']:,}"
                )

            # ── Table preview (toggled by button) ──
            preview_key = f"preview_{table}"
            if preview_key in st.session_state and st.session_state[preview_key]:
                with st.spinner("Loading preview…"):
                    preview_df = preview_table(conn, table)
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

            # ── Column listing ──
            with st.popover("📐 View columns", help="See all column names and types"):
                col_df = pd.read_sql_query(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    """,
                    conn,
                    params=(table,),
                )
                st.dataframe(col_df, use_container_width=True, hide_index=True)

            # ── Delete table (destructive, double-confirmation) ──
            st.markdown("---")
            del_key = f"del_{table}"
            confirm_key = f"del_confirm_{table}"
            if st.button("🗑️ Delete table permanently", key=del_key, type="secondary"):
                st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key, False):
                st.error(
                    f"This will permanently drop `{table}` and ALL its data. "
                    "This action cannot be undone."
                )
                ca, cb = st.columns([1, 5])
                with ca:
                    if st.button("✅ Yes, delete it", key=f"del_yes_{table}"):
                        try:
                            delete_table(conn, table)
                            st.success(f"Table `{table}` deleted successfully!")
                            st.session_state[confirm_key] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete table: {e}")
                            st.session_state[confirm_key] = False
                with cb:
                    if st.button("❌ Cancel", key=f"del_no_{table}"):
                        st.session_state[confirm_key] = False
                        st.rerun()

    # ---- Footer ----
    st.markdown("---")
    st.caption(f"🔄 Page refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
