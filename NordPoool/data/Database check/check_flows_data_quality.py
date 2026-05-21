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
        MIN(flow_id) AS min_flow_id,
        MAX(flow_id) AS max_flow_id,
        MIN(delivery_day) AS min_day,
        MAX(delivery_day) AS max_day,
        COUNT(DISTINCT from_zone_id) AS n_from_zones,
        COUNT(DISTINCT to_zone_id) AS n_to_zones,
        COUNT(DISTINCT from_zone_id || '-' || to_zone_id) AS n_directed_connections
    FROM Flows
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
    FROM Flows
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
# CONNECTIONS LIST
# =========================
connections = pd.read_sql_query(
    """
    SELECT
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone,
        COUNT(*) AS rows,
        MIN(f.delivery_day) AS min_day,
        MAX(f.delivery_day) AS max_day
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    GROUP BY z1.zone_code, z2.zone_code
    ORDER BY z1.zone_code, z2.zone_code
    """,
    conn
)

print("\n=========================")
print("DIRECTED CONNECTIONS")
print("=========================")
print(connections)
print(f"\nTotal directed connections: {len(connections)}")


# =========================
# ROWS BY YEAR AND CONNECTION
# =========================
rows_by_year_connection = pd.read_sql_query(
    """
    SELECT
        substr(f.delivery_day, 1, 4) AS year,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone,
        COUNT(*) AS rows
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    GROUP BY substr(f.delivery_day, 1, 4), z1.zone_code, z2.zone_code
    ORDER BY year, from_zone, to_zone
    """,
    conn
)

print("\n=========================")
print("ROWS BY YEAR AND CONNECTION")
print("=========================")
print(rows_by_year_connection)


# =========================
# DUPLICATES CHECK
# =========================
duplicates = pd.read_sql_query(
    """
    SELECT
        from_zone_id,
        to_zone_id,
        delivery_day,
        hour,
        COUNT(*) AS n,
        MIN(flow_value) AS min_flow,
        MAX(flow_value) AS max_flow
    FROM Flows
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
        duplicates["min_flow"] != duplicates["max_flow"]
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
    """
    SELECT
        SUM(CASE WHEN flow_id IS NULL THEN 1 ELSE 0 END) AS null_flow_id,
        SUM(CASE WHEN from_zone_id IS NULL THEN 1 ELSE 0 END) AS null_from_zone_id,
        SUM(CASE WHEN to_zone_id IS NULL THEN 1 ELSE 0 END) AS null_to_zone_id,
        SUM(CASE WHEN delivery_day IS NULL THEN 1 ELSE 0 END) AS null_delivery_day,
        SUM(CASE WHEN hour IS NULL THEN 1 ELSE 0 END) AS null_hour,
        SUM(CASE WHEN flow_value IS NULL THEN 1 ELSE 0 END) AS null_flow_value
    FROM Flows
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
    """
    SELECT
        COUNT(*) AS self_loop_rows
    FROM Flows
    WHERE from_zone_id = to_zone_id
    """,
    conn
)

print("\n=========================")
print("SELF LOOPS")
print("=========================")
print(self_loops)


# =========================
# FLOW RANGE CHECK
# =========================
flow_range = pd.read_sql_query(
    """
    SELECT
        MIN(flow_value) AS min_flow,
        MAX(flow_value) AS max_flow,
        AVG(flow_value) AS avg_flow
    FROM Flows
    """,
    conn
)

print("\n=========================")
print("FLOW RANGE")
print("=========================")
print(flow_range)


# =========================
# NEGATIVE FLOWS CHECK
# =========================
negative_flows = pd.read_sql_query(
    """
    SELECT
        COUNT(*) AS negative_flow_rows
    FROM Flows
    WHERE flow_value < 0
    """,
    conn
)

print("\n=========================")
print("NEGATIVE FLOWS")
print("=========================")
print(negative_flows)


# =========================
# ZERO FLOWS CHECK
# =========================
zero_flows = pd.read_sql_query(
    """
    SELECT
        COUNT(*) AS zero_flow_rows
    FROM Flows
    WHERE flow_value = 0
    """,
    conn
)

print("\n=========================")
print("ZERO FLOWS")
print("=========================")
print(zero_flows)


# =========================
# DAYS WITH UNEXPECTED HOURS PER CONNECTION
# =========================
hours_per_day_connection = pd.read_sql_query(
    """
    SELECT
        delivery_day,
        from_zone_id,
        to_zone_id,
        COUNT(*) AS n_hours
    FROM Flows
    GROUP BY delivery_day, from_zone_id, to_zone_id
    HAVING COUNT(*) NOT IN (23, 24, 25)
    ORDER BY delivery_day, from_zone_id, to_zone_id
    """,
    conn
)

print("\n=========================")
print("CONNECTION-DAYS WITH UNEXPECTED NUMBER OF HOURS")
print("=========================")

if hours_per_day_connection.empty:
    print("Todas las conexiones-día tienen 23, 24 o 25 horas.")
else:
    print(hours_per_day_connection.head(100))
    print(f"Total casos raros: {len(hours_per_day_connection)}")


# =========================
# CONNECTION COVERAGE SUMMARY
# =========================
connection_coverage = pd.read_sql_query(
    """
    SELECT
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone,
        COUNT(DISTINCT f.delivery_day) AS n_days,
        COUNT(*) AS n_rows,
        MIN(f.delivery_day) AS min_day,
        MAX(f.delivery_day) AS max_day
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    GROUP BY z1.zone_code, z2.zone_code
    ORDER BY n_rows ASC
    """,
    conn
)

print("\n=========================")
print("CONNECTION COVERAGE SUMMARY")
print("=========================")
print(connection_coverage)


# =========================
# LOWEST FLOWS
# =========================
lowest_flows = pd.read_sql_query(
    """
    SELECT
        f.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    ORDER BY f.flow_value ASC
    LIMIT 20
    """,
    conn
)

highest_flows = pd.read_sql_query(
    """
    SELECT
        f.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    ORDER BY f.flow_value DESC
    LIMIT 20
    """,
    conn
)

print("\n=========================")
print("LOWEST FLOWS")
print("=========================")
print(lowest_flows)

print("\n=========================")
print("HIGHEST FLOWS")
print("=========================")
print(highest_flows)


# =========================
# FIRST AND LAST ROWS
# =========================
first_rows = pd.read_sql_query(
    """
    SELECT
        f.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    ORDER BY f.delivery_day, f.hour, f.from_zone_id, f.to_zone_id
    LIMIT 20
    """,
    conn
)

last_rows = pd.read_sql_query(
    """
    SELECT
        f.*,
        z1.zone_code AS from_zone,
        z2.zone_code AS to_zone
    FROM Flows f
    JOIN BiddingZones z1
        ON f.from_zone_id = z1.zone_id
    JOIN BiddingZones z2
        ON f.to_zone_id = z2.zone_id
    ORDER BY f.delivery_day DESC, f.hour DESC, f.from_zone_id DESC, f.to_zone_id DESC
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