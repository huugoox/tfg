from pathlib import Path
import sqlite3
import pandas as pd


# =========================
# PATHS
# =========================
project_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool")
db_path = project_root / "data" / "thesis_database.db"

conn = sqlite3.connect(db_path)


# =========================
# TABLES
# =========================
tables = pd.read_sql_query(
    """
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
    """,
    conn
)

print("\nTABLAS:")
print(tables)


# =========================
# REGIONS
# =========================
regions = pd.read_sql_query(
    "SELECT * FROM Regions",
    conn
)

print("\nREGIONS:")
print(regions)


# =========================
# BIDDING ZONES
# =========================
zones = pd.read_sql_query(
    "SELECT * FROM BiddingZones ORDER BY zone_code",
    conn
)

print("\nBIDDING ZONES:")
print(zones)


# =========================
# ROW COUNTS
# =========================
for table in ["Prices", "Volumes", "Flows", "Capacities"]:
    try:
        count = pd.read_sql_query(
            f"SELECT COUNT(*) AS n FROM {table}",
            conn
        )
        print(f"\n{table}: {count['n'].iloc[0]} filas")
    except Exception as e:
        print(f"\nNo se pudo leer {table}: {e}")

conn.close()