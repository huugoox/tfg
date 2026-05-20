from pathlib import Path
import shutil
import sqlite3
import pandas as pd


# =========================
# PATHS
# =========================
project_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool")
db_path = project_root / "data" / "thesis_database.db"

backup_path = project_root / "data" / "thesis_database_backup_before_api_cleanup.db"

if not db_path.exists():
    raise FileNotFoundError(f"No existe la base de datos: {db_path}")


# =========================
# BACKUP
# =========================
shutil.copy2(db_path, backup_path)
print(f"Backup creado en: {backup_path}")


# =========================
# NEW DATABASE SCOPE
# =========================
regions = [
    (1, "Baltic"),
    (2, "Nordic"),
]

bidding_zones = [
    # Baltic
    (1, "EE", "Estonia", 1),
    (2, "LT", "Lithuania", 1),
    (3, "LV", "Latvia", 1),

    # Nordic
    (4, "DK1", "Denmark", 2),
    (5, "DK2", "Denmark", 2),
    (6, "FI", "Finland", 2),
    (7, "NO1", "Norway", 2),
    (8, "NO2", "Norway", 2),
    (9, "NO3", "Norway", 2),
    (10, "NO4", "Norway", 2),
    (11, "NO5", "Norway", 2),
    (12, "SE1", "Sweden", 2),
    (13, "SE2", "Sweden", 2),
    (14, "SE3", "Sweden", 2),
    (15, "SE4", "Sweden", 2),
]


# =========================
# CONNECT
# =========================
conn = sqlite3.connect(db_path)
cursor = conn.cursor()


# =========================
# SHOW CURRENT STATE
# =========================
print("\nEstado antes de limpiar:")

for table in ["Regions", "BiddingZones", "Prices", "Volumes", "Flows", "Capacities"]:
    count = pd.read_sql_query(
        f"SELECT COUNT(*) AS n FROM {table}",
        conn
    )["n"].iloc[0]

    print(f"{table}: {count} filas")


# =========================
# CLEAN ALL TABLES
# =========================
print("\nVaciando tablas...")

cursor.execute("DELETE FROM Prices")
cursor.execute("DELETE FROM Volumes")
cursor.execute("DELETE FROM Flows")
cursor.execute("DELETE FROM Capacities")
cursor.execute("DELETE FROM BiddingZones")
cursor.execute("DELETE FROM Regions")


# =========================
# RESET SQLITE SEQUENCES
# =========================
try:
    cursor.execute(
        """
        DELETE FROM sqlite_sequence
        WHERE name IN (
            'Prices',
            'Volumes',
            'Flows',
            'Capacities',
            'BiddingZones',
            'Regions'
        )
        """
    )
except sqlite3.OperationalError:
    pass


# =========================
# REINSERT REGIONS
# =========================
cursor.executemany(
    """
    INSERT INTO Regions (region_id, region_name)
    VALUES (?, ?)
    """,
    regions
)


# =========================
# REINSERT BIDDING ZONES
# =========================
cursor.executemany(
    """
    INSERT INTO BiddingZones (zone_id, zone_code, country, region_id)
    VALUES (?, ?, ?, ?)
    """,
    bidding_zones
)


# =========================
# COMMIT
# =========================
conn.commit()


# =========================
# CHECK FINAL STATE
# =========================
print("\nEstado después de limpiar:")

for table in ["Regions", "BiddingZones", "Prices", "Volumes", "Flows", "Capacities"]:
    count = pd.read_sql_query(
        f"SELECT COUNT(*) AS n FROM {table}",
        conn
    )["n"].iloc[0]

    print(f"{table}: {count} filas")


regions_after = pd.read_sql_query(
    """
    SELECT *
    FROM Regions
    ORDER BY region_id
    """,
    conn
)

zones_after = pd.read_sql_query(
    """
    SELECT *
    FROM BiddingZones
    ORDER BY zone_id
    """,
    conn
)

print("\nRegiones restantes:")
print(regions_after)

print("\nZonas restantes:")
print(zones_after)

conn.close()

print("\nLimpieza completada correctamente.")