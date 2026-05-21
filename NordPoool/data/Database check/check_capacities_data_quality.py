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
# DATE FILTER
# =========================
START_DATE = "2020-01-01"
END_DATE = "2020-01-03"


# =========================
# CONNECT
# =========================
conn = sqlite3.connect(db_path)


# =========================
# GENERAL SUMMARY
# =========================
summary = pd.read_sql_query(
    f"""
    SELECT
        COUNT(*) AS total_rows,
        MIN(capacity_id) AS min_capacity_id,
        MAX(capacity_id) AS max_capacity_id,
        MIN(delivery_day) AS min_day,
        MAX(delivery_day) AS max_day,
        COUNT(DISTINCT from_zone_id) AS n_from_zones,
        COUNT(DISTINCT to_zone_id) AS n_to_zones,
        COUNT(DISTINCT from_zone_id || '-' || to_zone_id) AS n_directed_connections
    FROM Capacities
    WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    """,
    conn
)

print("\n=========================")
print("GENERAL SUMMARY")
print("=========================")
print(summary)


# =========================
# DIRECTED CONNECTIONS
# =========================
directed_connections = pd.read_sql_query(
    f"""
    SELECT
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone,
        COUNT(*) AS rows,
        MIN(c.delivery_day) AS min_day,
        MAX(c.delivery_day) AS max_day,
        MIN(c.capacity_value) AS min_capacity,
        MAX(c.capacity_value) AS max_capacity,
        AVG(c.capacity_value) AS avg_capacity
    FROM Capacities c
    JOIN BiddingZones z1
        ON c.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON c.to_zone_id = z2.zone_id
    WHERE c.delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    GROUP BY z1.zone_code, z2.zone_code
    ORDER BY z1.zone_code, z2.zone_code
    """,
    conn
)

print("\n=========================")
print("DIRECTED CONNECTIONS")
print("=========================")
print(directed_connections)
print(f"\nTotal directed connections: {len(directed_connections)}")


# =========================
# EXPECTED ROWS FOR 3 DAYS
# =========================
n_days = (
    pd.to_datetime(END_DATE) - pd.to_datetime(START_DATE)
).days + 1

n_directed_connections = len(directed_connections)
expected_rows = n_days * 24 * n_directed_connections

actual_rows = int(summary["total_rows"].iloc[0])

expected_df = pd.DataFrame([{
    "start_date": START_DATE,
    "end_date": END_DATE,
    "days": n_days,
    "directed_connections": n_directed_connections,
    "expected_rows_24h": expected_rows,
    "actual_rows": actual_rows,
    "difference": actual_rows - expected_rows
}])

print("\n=========================")
print("EXPECTED VS ACTUAL")
print("=========================")
print(expected_df)


# =========================
# DUPLICATES CHECK
# =========================
duplicates = pd.read_sql_query(
    f"""
    SELECT
        from_zone_id,
        to_zone_id,
        delivery_day,
        hour,
        COUNT(*) AS n,
        MIN(capacity_value) AS min_capacity,
        MAX(capacity_value) AS max_capacity
    FROM Capacities
    WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    GROUP BY from_zone_id, to_zone_id, delivery_day, hour
    HAVING COUNT(*) > 1
    ORDER BY delivery_day, hour, from_zone_id, to_zone_id
    """,
    conn
)

print("\n=========================")
print("DUPLICATES")
print("=========================")

if duplicates.empty:
    print("No hay duplicados por from_zone_id + to_zone_id + delivery_day + hour.")
else:
    print(duplicates.head(50))
    print(f"Total combinaciones duplicadas: {len(duplicates)}")

    inconsistent_duplicates = duplicates[
        duplicates["min_capacity"] != duplicates["max_capacity"]
    ]

    if inconsistent_duplicates.empty:
        print("Los duplicados tienen valores consistentes.")
    else:
        print("ATENCIÓN: Hay duplicados con valores distintos.")
        print(inconsistent_duplicates.head(50))


# =========================
# NULL VALUES CHECK
# =========================
nulls = pd.read_sql_query(
    f"""
    SELECT
        SUM(CASE WHEN capacity_id IS NULL THEN 1 ELSE 0 END) AS null_capacity_id,
        SUM(CASE WHEN from_zone_id IS NULL THEN 1 ELSE 0 END) AS null_from_zone_id,
        SUM(CASE WHEN to_zone_id IS NULL THEN 1 ELSE 0 END) AS null_to_zone_id,
        SUM(CASE WHEN delivery_day IS NULL THEN 1 ELSE 0 END) AS null_delivery_day,
        SUM(CASE WHEN hour IS NULL THEN 1 ELSE 0 END) AS null_hour,
        SUM(CASE WHEN capacity_value IS NULL THEN 1 ELSE 0 END) AS null_capacity_value
    FROM Capacities
    WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    """,
    conn
)

print("\n=========================")
print("NULL VALUES")
print("=========================")
print(nulls)


# =========================
# SELF LOOPS CHECK
# =========================
self_loops = pd.read_sql_query(
    f"""
    SELECT
        COUNT(*) AS self_loop_rows
    FROM Capacities
    WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
      AND from_zone_id = to_zone_id
    """,
    conn
)

print("\n=========================")
print("SELF LOOPS")
print("=========================")
print(self_loops)


# =========================
# CAPACITY RANGE CHECK
# =========================
capacity_range = pd.read_sql_query(
    f"""
    SELECT
        MIN(capacity_value) AS min_capacity,
        MAX(capacity_value) AS max_capacity,
        AVG(capacity_value) AS avg_capacity
    FROM Capacities
    WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    """,
    conn
)

print("\n=========================")
print("CAPACITY RANGE")
print("=========================")
print(capacity_range)


# =========================
# NEGATIVE / ZERO / POSITIVE CAPACITIES
# =========================
sign_summary = pd.read_sql_query(
    f"""
    SELECT
        SUM(CASE WHEN capacity_value < 0 THEN 1 ELSE 0 END) AS negative_capacity_rows,
        SUM(CASE WHEN capacity_value = 0 THEN 1 ELSE 0 END) AS zero_capacity_rows,
        SUM(CASE WHEN capacity_value > 0 THEN 1 ELSE 0 END) AS positive_capacity_rows
    FROM Capacities
    WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    """,
    conn
)

print("\n=========================")
print("CAPACITY SIGN SUMMARY")
print("=========================")
print(sign_summary)


# =========================
# NEGATIVE CAPACITIES DETAIL
# =========================
negative_detail = pd.read_sql_query(
    f"""
    SELECT
        c.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Capacities c
    JOIN BiddingZones z1
        ON c.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON c.to_zone_id = z2.zone_id
    WHERE c.delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
      AND c.capacity_value < 0
    ORDER BY c.delivery_day, c.hour, c.from_zone_id, c.to_zone_id
    LIMIT 100
    """,
    conn
)

print("\n=========================")
print("NEGATIVE CAPACITIES DETAIL")
print("=========================")

if negative_detail.empty:
    print("No hay capacidades negativas.")
else:
    print(negative_detail)


# =========================
# ZERO CAPACITIES DETAIL
# =========================
zero_detail = pd.read_sql_query(
    f"""
    SELECT
        c.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Capacities c
    JOIN BiddingZones z1
        ON c.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON c.to_zone_id = z2.zone_id
    WHERE c.delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
      AND c.capacity_value = 0
    ORDER BY c.delivery_day, c.hour, c.from_zone_id, c.to_zone_id
    LIMIT 100
    """,
    conn
)

print("\n=========================")
print("ZERO CAPACITIES DETAIL")
print("=========================")

if zero_detail.empty:
    print("No hay capacidades cero.")
else:
    print(zero_detail)


# =========================
# HOURS PER DIRECTED CONNECTION AND DAY
# =========================
hours_per_directed_connection = pd.read_sql_query(
    f"""
    SELECT
        c.delivery_day,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone,
        COUNT(*) AS n_hours
    FROM Capacities c
    JOIN BiddingZones z1
        ON c.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON c.to_zone_id = z2.zone_id
    WHERE c.delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    GROUP BY c.delivery_day, c.from_zone_id, c.to_zone_id
    HAVING COUNT(*) NOT IN (23, 24, 25)
    ORDER BY c.delivery_day, from_zone, to_zone
    """,
    conn
)

print("\n=========================")
print("DIRECTED CONNECTION-DAYS WITH UNEXPECTED NUMBER OF HOURS")
print("=========================")

if hours_per_directed_connection.empty:
    print("Todas las conexiones dirigidas tienen 23, 24 o 25 horas por día.")
else:
    print(hours_per_directed_connection.head(100))
    print(f"Total casos raros: {len(hours_per_directed_connection)}")


# =========================
# PHYSICAL LINK COVERAGE SUMMARY
# =========================
physical_link_coverage = pd.read_sql_query(
    f"""
    WITH normalized_capacities AS (
        SELECT
            delivery_day,
            hour,
            capacity_value,
            CASE
                WHEN from_zone_id < to_zone_id THEN from_zone_id
                ELSE to_zone_id
            END AS zone_a_id,
            CASE
                WHEN from_zone_id < to_zone_id THEN to_zone_id
                ELSE from_zone_id
            END AS zone_b_id
        FROM Capacities
        WHERE delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    )
    SELECT
        za.zone_code AS zone_a,
        zb.zone_code AS zone_b,
        COUNT(DISTINCT nc.delivery_day) AS n_days,
        COUNT(*) AS n_rows,
        MIN(nc.capacity_value) AS min_capacity,
        MAX(nc.capacity_value) AS max_capacity,
        AVG(nc.capacity_value) AS avg_capacity
    FROM normalized_capacities nc
    JOIN BiddingZones za
        ON nc.zone_a_id = za.zone_id
    JOIN BiddingZones zb
        ON nc.zone_b_id = zb.zone_id
    GROUP BY nc.zone_a_id, nc.zone_b_id
    ORDER BY zone_a, zone_b
    """,
    conn
)

print("\n=========================")
print("PHYSICAL LINK COVERAGE SUMMARY")
print("=========================")
print(physical_link_coverage)
print(f"\nTotal physical links: {len(physical_link_coverage)}")


# =========================
# FIRST AND LAST ROWS
# =========================
first_rows = pd.read_sql_query(
    f"""
    SELECT
        c.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Capacities c
    JOIN BiddingZones z1
        ON c.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON c.to_zone_id = z2.zone_id
    WHERE c.delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    ORDER BY c.delivery_day, c.hour, c.from_zone_id, c.to_zone_id
    LIMIT 20
    """,
    conn
)

last_rows = pd.read_sql_query(
    f"""
    SELECT
        c.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Capacities c
    JOIN BiddingZones z1
        ON c.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON c.to_zone_id = z2.zone_id
    WHERE c.delivery_day BETWEEN '{START_DATE}' AND '{END_DATE}'
    ORDER BY c.delivery_day DESC, c.hour DESC, c.from_zone_id DESC, c.to_zone_id DESC
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