from pathlib import Path
import sqlite3
import pandas as pd


# =========================
# PATHS
# =========================
project_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool")
db_path = project_root / "data" / "thesis_database.db"

if not db_path.exists():
    raise FileNotFoundError(f"No existe la base de datos: {db_path}")


# =========================
# CONNECT
# =========================
conn = sqlite3.connect(db_path)


# =========================
# GENERAL SUMMARY
# =========================
summary = pd.read_sql_query(
    """
    SELECT
        COUNT(*) AS total_rows,
        MIN(volume_id) AS min_volume_id,
        MAX(volume_id) AS max_volume_id,
        MIN(delivery_day) AS min_day,
        MAX(delivery_day) AS max_day,
        COUNT(DISTINCT zone_id) AS n_zones
    FROM Volumes
    """,
    conn
)

print("\n=========================")
print("GENERAL SUMMARY")
print("=========================")
print(summary)


# =========================
# ROWS BY YEAR
# =========================
rows_by_year = pd.read_sql_query(
    """
    SELECT
        substr(delivery_day, 1, 4) AS year,
        COUNT(*) AS rows
    FROM Volumes
    GROUP BY substr(delivery_day, 1, 4)
    ORDER BY year
    """,
    conn
)

print("\n=========================")
print("ROWS BY YEAR")
print("=========================")
print(rows_by_year)


# =========================
# ROWS BY YEAR AND ZONE
# =========================
rows_by_year_zone = pd.read_sql_query(
    """
    SELECT
        substr(v.delivery_day, 1, 4) AS year,
        z.zone_code,
        COUNT(*) AS rows
    FROM Volumes v
    JOIN BiddingZones z
        ON v.zone_id = z.zone_id
    GROUP BY substr(v.delivery_day, 1, 4), z.zone_code
    ORDER BY year, z.zone_code
    """,
    conn
)

print("\n=========================")
print("ROWS BY YEAR AND ZONE")
print("=========================")
print(rows_by_year_zone)


# =========================
# EXPECTED ROWS BY YEAR
# =========================
zones_count = pd.read_sql_query(
    """
    SELECT COUNT(*) AS n_zones
    FROM BiddingZones
    """,
    conn
)["n_zones"].iloc[0]

expected = []

# Cambia el rango si cargas más años
for year in range(2015, 2025):
    days_in_year = 366 if pd.Timestamp(f"{year}-12-31").is_leap_year else 365
    expected_rows = days_in_year * 24 * zones_count

    actual_rows = rows_by_year.loc[
        rows_by_year["year"] == str(year),
        "rows"
    ]

    actual_rows = int(actual_rows.iloc[0]) if len(actual_rows) > 0 else 0

    expected.append({
        "year": year,
        "days": days_in_year,
        "zones": zones_count,
        "expected_rows_24h": expected_rows,
        "actual_rows": actual_rows,
        "difference": actual_rows - expected_rows
    })

expected_df = pd.DataFrame(expected)

print("\n=========================")
print("EXPECTED VS ACTUAL BY YEAR")
print("=========================")
print(expected_df)


# =========================
# DUPLICATES CHECK
# =========================
duplicates = pd.read_sql_query(
    """
    SELECT
        zone_id,
        delivery_day,
        hour,
        COUNT(*) AS n
    FROM Volumes
    GROUP BY zone_id, delivery_day, hour
    HAVING COUNT(*) > 1
    ORDER BY delivery_day, hour, zone_id
    """,
    conn
)

print("\n=========================")
print("DUPLICATES")
print("=========================")

if duplicates.empty:
    print("No hay duplicados por zone_id + delivery_day + hour.")
else:
    print(duplicates.head(50))
    print(f"Total combinaciones duplicadas: {len(duplicates)}")


# =========================
# NULL VALUES CHECK
# =========================
nulls = pd.read_sql_query(
    """
    SELECT
        SUM(CASE WHEN volume_id IS NULL THEN 1 ELSE 0 END) AS null_volume_id,
        SUM(CASE WHEN zone_id IS NULL THEN 1 ELSE 0 END) AS null_zone_id,
        SUM(CASE WHEN delivery_day IS NULL THEN 1 ELSE 0 END) AS null_delivery_day,
        SUM(CASE WHEN hour IS NULL THEN 1 ELSE 0 END) AS null_hour,
        SUM(CASE WHEN buy_volume_value IS NULL THEN 1 ELSE 0 END) AS null_buy_volume_value,
        SUM(CASE WHEN sell_volume_value IS NULL THEN 1 ELSE 0 END) AS null_sell_volume_value
    FROM Volumes
    """,
    conn
)

print("\n=========================")
print("NULL VALUES")
print("=========================")
print(nulls)


# =========================
# HOURS PER DAY CHECK
# =========================
hours_per_day = pd.read_sql_query(
    """
    SELECT
        delivery_day,
        zone_id,
        COUNT(*) AS n_hours
    FROM Volumes
    GROUP BY delivery_day, zone_id
    HAVING COUNT(*) NOT IN (23, 24, 25)
    ORDER BY delivery_day, zone_id
    """,
    conn
)

print("\n=========================")
print("DAYS WITH UNEXPECTED NUMBER OF HOURS")
print("=========================")

if hours_per_day.empty:
    print("Todos los días tienen 23, 24 o 25 horas por zona.")
else:
    print(hours_per_day.head(100))
    print(f"Total casos raros: {len(hours_per_day)}")


# =========================
# VOLUME RANGE CHECK
# =========================
volume_range = pd.read_sql_query(
    """
    SELECT
        MIN(buy_volume_value) AS min_buy_volume,
        MAX(buy_volume_value) AS max_buy_volume,
        AVG(buy_volume_value) AS avg_buy_volume,
        MIN(sell_volume_value) AS min_sell_volume,
        MAX(sell_volume_value) AS max_sell_volume,
        AVG(sell_volume_value) AS avg_sell_volume
    FROM Volumes
    """,
    conn
)

print("\n=========================")
print("VOLUME RANGE")
print("=========================")
print(volume_range)


# =========================
# NEGATIVE VOLUMES CHECK
# =========================
negative_volumes = pd.read_sql_query(
    """
    SELECT
        COUNT(*) AS negative_volume_rows
    FROM Volumes
    WHERE buy_volume_value < 0
       OR sell_volume_value < 0
    """,
    conn
)

print("\n=========================")
print("NEGATIVE VOLUMES")
print("=========================")
print(negative_volumes)


# =========================
# ZERO VOLUMES CHECK
# =========================
zero_volumes = pd.read_sql_query(
    """
    SELECT
        COUNT(*) AS zero_volume_rows
    FROM Volumes
    WHERE buy_volume_value = 0
       OR sell_volume_value = 0
    """,
    conn
)

print("\n=========================")
print("ZERO VOLUMES")
print("=========================")
print(zero_volumes)


# =========================
# EXTREME BUY VOLUMES
# =========================
extreme_buy_low = pd.read_sql_query(
    """
    SELECT
        v.*,
        z.zone_code
    FROM Volumes v
    JOIN BiddingZones z
        ON v.zone_id = z.zone_id
    ORDER BY buy_volume_value ASC
    LIMIT 20
    """,
    conn
)

extreme_buy_high = pd.read_sql_query(
    """
    SELECT
        v.*,
        z.zone_code
    FROM Volumes v
    JOIN BiddingZones z
        ON v.zone_id = z.zone_id
    ORDER BY buy_volume_value DESC
    LIMIT 20
    """,
    conn
)

print("\n=========================")
print("LOWEST BUY VOLUMES")
print("=========================")
print(extreme_buy_low)

print("\n=========================")
print("HIGHEST BUY VOLUMES")
print("=========================")
print(extreme_buy_high)


# =========================
# EXTREME SELL VOLUMES
# =========================
extreme_sell_low = pd.read_sql_query(
    """
    SELECT
        v.*,
        z.zone_code
    FROM Volumes v
    JOIN BiddingZones z
        ON v.zone_id = z.zone_id
    ORDER BY sell_volume_value ASC
    LIMIT 20
    """,
    conn
)

extreme_sell_high = pd.read_sql_query(
    """
    SELECT
        v.*,
        z.zone_code
    FROM Volumes v
    JOIN BiddingZones z
        ON v.zone_id = z.zone_id
    ORDER BY sell_volume_value DESC
    LIMIT 20
    """,
    conn
)

print("\n=========================")
print("LOWEST SELL VOLUMES")
print("=========================")
print(extreme_sell_low)

print("\n=========================")
print("HIGHEST SELL VOLUMES")
print("=========================")
print(extreme_sell_high)


# =========================
# FIRST AND LAST ROWS
# =========================
first_rows = pd.read_sql_query(
    """
    SELECT *
    FROM Volumes
    ORDER BY delivery_day, hour, zone_id
    LIMIT 20
    """,
    conn
)

last_rows = pd.read_sql_query(
    """
    SELECT *
    FROM Volumes
    ORDER BY delivery_day DESC, hour DESC, zone_id DESC
    LIMIT 20
    """,
    conn
)

print("\n=========================")
print("FIRST ROWS")
print("=========================")
print(first_rows)

print("\n=========================")
print("LAST ROWS")
print("=========================")
print(last_rows)


conn.close()