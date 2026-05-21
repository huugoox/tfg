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
# PHYSICAL LINK COVERAGE CHECK
# =========================
# A physical link is considered undirected:
# DK1 -> DK2 and DK2 -> DK1 belong to the same physical connection.
# This is more appropriate for checking daily hourly coverage,
# because the flow direction can change within the same day.

physical_link_hours = pd.read_sql_query(
    """
    WITH normalized_flows AS (
        SELECT
            delivery_day,
            hour,
            CASE 
                WHEN from_zone_id < to_zone_id THEN from_zone_id
                ELSE to_zone_id
            END AS zone_a_id,
            CASE 
                WHEN from_zone_id < to_zone_id THEN to_zone_id
                ELSE from_zone_id
            END AS zone_b_id
        FROM Flows
    )
    SELECT
        nf.delivery_day,
        za.zone_code AS zone_a,
        zb.zone_code AS zone_b,
        COUNT(DISTINCT nf.hour) AS n_hours,
        COUNT(*) AS n_rows
    FROM normalized_flows nf
    JOIN BiddingZones za
        ON nf.zone_a_id = za.zone_id
    JOIN BiddingZones zb
        ON nf.zone_b_id = zb.zone_id
    GROUP BY
        nf.delivery_day,
        nf.zone_a_id,
        nf.zone_b_id
    HAVING COUNT(DISTINCT nf.hour) NOT IN (23, 24, 25)
    ORDER BY
        nf.delivery_day,
        zone_a,
        zone_b
    """,
    conn
)

print("\n=========================")
print("PHYSICAL LINK-DAYS WITH UNEXPECTED NUMBER OF HOURS")
print("=========================")

if physical_link_hours.empty:
    print("Todos los enlaces físicos tienen 23, 24 o 25 horas por día.")
else:
    print(physical_link_hours.head(100))
    print(f"Total casos raros: {len(physical_link_hours)}")
    
    
# =========================
# PHYSICAL LINK COVERAGE SUMMARY
# =========================
physical_link_coverage = pd.read_sql_query(
    """
    WITH normalized_flows AS (
        SELECT
            delivery_day,
            hour,
            flow_value,
            CASE 
                WHEN from_zone_id < to_zone_id THEN from_zone_id
                ELSE to_zone_id
            END AS zone_a_id,
            CASE 
                WHEN from_zone_id < to_zone_id THEN to_zone_id
                ELSE from_zone_id
            END AS zone_b_id
        FROM Flows
    )
    SELECT
        za.zone_code AS zone_a,
        zb.zone_code AS zone_b,
        COUNT(DISTINCT nf.delivery_day) AS n_days,
        COUNT(*) AS n_rows,
        MIN(nf.delivery_day) AS min_day,
        MAX(nf.delivery_day) AS max_day,
        MIN(nf.flow_value) AS min_flow,
        MAX(nf.flow_value) AS max_flow,
        AVG(nf.flow_value) AS avg_flow
    FROM normalized_flows nf
    JOIN BiddingZones za
        ON nf.zone_a_id = za.zone_id
    JOIN BiddingZones zb
        ON nf.zone_b_id = zb.zone_id
    GROUP BY
        nf.zone_a_id,
        nf.zone_b_id
    ORDER BY
        zone_a,
        zone_b
    """,
    conn
)

print("\n=========================")
print("PHYSICAL LINK COVERAGE SUMMARY")
print("=========================")
print(physical_link_coverage)
print(f"\nTotal physical links: {len(physical_link_coverage)}")


# =========================
# PHYSICAL LINK COVERAGE PERCENTAGE
# =========================
# This estimates how much of the possible hourly coverage is available
# for each physical link.
#
# Expected rows are computed between the first and last available date
# of each physical link, not necessarily between 2015-01-01 and 2024-12-31.
# This is useful because some links appear later in the dataset.

physical_link_coverage_pct = pd.read_sql_query(
    """
    WITH normalized_flows AS (
        SELECT
            delivery_day,
            hour,
            flow_value,
            CASE 
                WHEN from_zone_id < to_zone_id THEN from_zone_id
                ELSE to_zone_id
            END AS zone_a_id,
            CASE 
                WHEN from_zone_id < to_zone_id THEN to_zone_id
                ELSE from_zone_id
            END AS zone_b_id
        FROM Flows
    ),
    link_summary AS (
        SELECT
            zone_a_id,
            zone_b_id,
            MIN(delivery_day) AS min_day,
            MAX(delivery_day) AS max_day,
            COUNT(*) AS actual_rows,
            COUNT(DISTINCT delivery_day) AS actual_days
        FROM normalized_flows
        GROUP BY zone_a_id, zone_b_id
    )
    SELECT
        za.zone_code AS zone_a,
        zb.zone_code AS zone_b,
        ls.min_day,
        ls.max_day,
        ls.actual_days,
        ls.actual_rows
    FROM link_summary ls
    JOIN BiddingZones za
        ON ls.zone_a_id = za.zone_id
    JOIN BiddingZones zb
        ON ls.zone_b_id = zb.zone_id
    ORDER BY za.zone_code, zb.zone_code
    """,
    conn
)

# Compute expected rows in Python because it is easier and safer
# to handle leap years and date ranges here.
coverage_rows = []

for _, row in physical_link_coverage_pct.iterrows():
    min_day = pd.to_datetime(row["min_day"])
    max_day = pd.to_datetime(row["max_day"])

    expected_hours = pd.date_range(
        start=min_day,
        end=max_day + pd.Timedelta(days=1),
        freq="h",
        inclusive="left"
    )

    expected_rows = len(expected_hours)
    actual_rows = int(row["actual_rows"])

    coverage_pct = round((actual_rows / expected_rows) * 100, 2) if expected_rows > 0 else None

    coverage_rows.append({
        "zone_a": row["zone_a"],
        "zone_b": row["zone_b"],
        "min_day": row["min_day"],
        "max_day": row["max_day"],
        "actual_days": int(row["actual_days"]),
        "actual_rows": actual_rows,
        "expected_rows_24h": expected_rows,
        "coverage_pct": coverage_pct,
        "missing_rows_estimate": expected_rows - actual_rows
    })

coverage_pct_df = pd.DataFrame(coverage_rows)

coverage_pct_df = coverage_pct_df.sort_values(
    ["coverage_pct", "zone_a", "zone_b"]
).reset_index(drop=True)

print("\n=========================")
print("PHYSICAL LINK COVERAGE PERCENTAGE")
print("=========================")
print(coverage_pct_df)

print("\n=========================")
print("LOWEST COVERAGE PHYSICAL LINKS")
print("=========================")
print(coverage_pct_df.head(10))

print("\n=========================")
print("HIGHEST COVERAGE PHYSICAL LINKS")
print("=========================")
print(coverage_pct_df.tail(10))


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