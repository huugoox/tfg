from pathlib import Path
from datetime import date, timedelta
import sqlite3
import requests
import pandas as pd
import os


# =========================
# PATHS
# =========================
project_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool")
db_path = project_root / "data" / "thesis_database.db"

if not db_path.exists():
    raise FileNotFoundError(f"No existe la base de datos: {db_path}")


# =========================
# API CONFIG
# =========================
USERNAME = os.getenv("NORDPOOL_USERNAME")
PASSWORD = os.getenv("NORDPOOL_PASSWORD")

if USERNAME is None or PASSWORD is None:
    raise ValueError("Faltan las variables de entorno NORDPOOL_USERNAME o NORDPOOL_PASSWORD")

TOKEN_URL = "https://sts.nordpoolgroup.com/connect/token"
CAPACITIES_URL = "https://data-api.nordpoolgroup.com/api/v2/Auction/Capacities/ByAreas"

AREAS = [
    "DK1", "DK2",
    "EE", "FI", "LT", "LV",
    "NO1", "NO2", "NO3", "NO4", "NO5",
    "SE1", "SE2", "SE3", "SE4"
]

MARKET = "DayAhead"

START_DATE = date(2010, 1, 1)
END_DATE = date(2014, 12, 31)

# =========================
# GET ACCESS TOKEN
# =========================
def get_access_token(username: str, password: str) -> str:
    headers = {
        "Authorization": "Basic Y2xpZW50X21hcmtldGRhdGFfYXBpOmNsaWVudF9tYXJrZXRkYXRhX2FwaQ==",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "password",
        "scope": "marketdata_api",
        "username": username,
        "password": password,
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)

    if response.status_code != 200:
        raise RuntimeError(
            f"Error obteniendo token: {response.status_code}\n{response.text[:1000]}"
        )

    return response.json()["access_token"]


# =========================
# DATE RANGE
# =========================
def daterange(start_date: date, end_date: date):
    current = start_date

    while current <= end_date:
        yield current
        current += timedelta(days=1)


# =========================
# DOWNLOAD ONE DAY
# =========================
def get_capacities_json_for_day(access_token: str, areas: list[str], day: date):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    params = {
        "areas": areas,
        "market": MARKET,
        "date": day.strftime("%Y-%m-%d"),
    }

    response = requests.get(CAPACITIES_URL, headers=headers, params=params)

    if response.status_code != 200:
        raise RuntimeError(
            f"Error descargando {day}: {response.status_code}\n{response.text[:1000]}"
        )

    return response.json()


# =========================
# JSON TO LONG DATAFRAME
# =========================
def capacities_json_to_long_dataframe(data, valid_zone_codes: set[str]) -> pd.DataFrame:
    rows = []
    skipped_external_connections = set()

    for area_data in data:
        delivery_area = area_data["deliveryArea"]

        if delivery_area not in valid_zone_codes:
            skipped_external_connections.add(delivery_area)
            continue

        for capacity_item in area_data["capacities"]:
            delivery_start_utc = pd.to_datetime(capacity_item["deliveryStart"], utc=True)
            delivery_start_local = delivery_start_utc.tz_convert("Europe/Oslo")

            delivery_day = delivery_start_local.date()
            hour = delivery_start_local.hour

            # Imports into delivery_area:
            # connection_area -> delivery_area
            for connection in capacity_item.get("importsByConnection", []):
                connection_area = connection["area"]

                if connection_area not in valid_zone_codes:
                    skipped_external_connections.add(connection_area)
                    continue

                capacity_value = connection.get("capacity", None)

                rows.append({
                    "from_zone_code": connection_area,
                    "to_zone_code": delivery_area,
                    "delivery_day": delivery_day,
                    "hour": hour,
                    "capacity_value": capacity_value,
                })

            # Exports from delivery_area:
            # delivery_area -> connection_area
            for connection in capacity_item.get("exportsByConnection", []):
                connection_area = connection["area"]

                if connection_area not in valid_zone_codes:
                    skipped_external_connections.add(connection_area)
                    continue

                capacity_value = connection.get("capacity", None)

                rows.append({
                    "from_zone_code": delivery_area,
                    "to_zone_code": connection_area,
                    "delivery_day": delivery_day,
                    "hour": hour,
                    "capacity_value": capacity_value,
                })

    df = pd.DataFrame(rows)

    if skipped_external_connections:
        print(
            "Conexiones externas ignoradas porque no están en BiddingZones:",
            sorted(skipped_external_connections)
        )

    return df


# =========================
# MAIN
# =========================
print("Obteniendo access token...")
access_token = get_access_token(USERNAME, PASSWORD)


# =========================
# CONNECT TO DB AND GET ZONES
# =========================
conn = sqlite3.connect(db_path)

zones_df = pd.read_sql_query(
    "SELECT zone_id, zone_code FROM BiddingZones",
    conn
)

zone_map = dict(zip(zones_df["zone_code"], zones_df["zone_id"]))
valid_zone_codes = set(zone_map.keys())

print("\nZone codes en DB:", sorted(valid_zone_codes))


# =========================
# DOWNLOAD DATA
# =========================
all_capacities = []

for day in daterange(START_DATE, END_DATE):
    print(f"Descargando capacities para {day}...")

    data = get_capacities_json_for_day(
        access_token=access_token,
        areas=AREAS,
        day=day
    )

    df_day = capacities_json_to_long_dataframe(
        data=data,
        valid_zone_codes=valid_zone_codes
    )

    all_capacities.append(df_day)

if not all_capacities:
    conn.close()
    raise ValueError("No se ha descargado ningún dato.")

capacities_long = pd.concat(all_capacities, ignore_index=True)

if capacities_long.empty:
    conn.close()
    raise ValueError("La descarga no produjo capacities internas entre zonas de la DB.")

print("\nShape descargado:", capacities_long.shape)
print(capacities_long.head())


# =========================
# MAP ZONE CODES TO ZONE IDS
# =========================
capacities_long["from_zone_id"] = capacities_long["from_zone_code"].map(zone_map)
capacities_long["to_zone_id"] = capacities_long["to_zone_code"].map(zone_map)

missing_from = capacities_long.loc[
    capacities_long["from_zone_id"].isna(),
    "from_zone_code"
].unique()

missing_to = capacities_long.loc[
    capacities_long["to_zone_id"].isna(),
    "to_zone_code"
].unique()

if len(missing_from) > 0 or len(missing_to) > 0:
    conn.close()
    raise ValueError(
        f"Zonas no encontradas. From missing: {missing_from}. To missing: {missing_to}"
    )


# =========================
# FINAL DATAFRAME
# =========================
capacities_final = capacities_long[
    ["from_zone_id", "to_zone_id", "delivery_day", "hour", "capacity_value"]
].copy()

capacities_final["from_zone_id"] = capacities_final["from_zone_id"].astype(int)
capacities_final["to_zone_id"] = capacities_final["to_zone_id"].astype(int)

capacities_final["delivery_day"] = pd.to_datetime(
    capacities_final["delivery_day"]
).dt.strftime("%Y-%m-%d")

capacities_final["hour"] = capacities_final["hour"].astype(int)

capacities_final["capacity_value"] = pd.to_numeric(
    capacities_final["capacity_value"],
    errors="coerce"
)

capacities_final = capacities_final.dropna(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour", "capacity_value"]
)


# =========================
# CHECK DUPLICATE CONSISTENCY
# =========================
duplicate_check = (
    capacities_final
    .groupby(["from_zone_id", "to_zone_id", "delivery_day", "hour"])
    .agg(
        n=("capacity_value", "count"),
        min_capacity=("capacity_value", "min"),
        max_capacity=("capacity_value", "max")
    )
    .reset_index()
)

inconsistent_duplicates = duplicate_check[
    (duplicate_check["n"] > 1) &
    (duplicate_check["min_capacity"] != duplicate_check["max_capacity"])
]

if not inconsistent_duplicates.empty:
    print("\nATENCIÓN: Hay duplicados con valores distintos.")
    print(inconsistent_duplicates.head(50))
else:
    print("\nDuplicados consistentes: los valores repetidos coinciden.")


# =========================
# REMOVE DUPLICATES
# =========================
print(f"\nFilas antes de deduplicar: {len(capacities_final)}")

duplicate_mask = capacities_final.duplicated(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour"],
    keep="first"
)

num_duplicates = duplicate_mask.sum()
print(f"Duplicados detectados: {num_duplicates}")

if num_duplicates > 0:
    print("Ejemplo de duplicados:")
    print(capacities_final.loc[duplicate_mask].head(10))

capacities_final = capacities_final.drop_duplicates(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour"],
    keep="first"
).copy()


# =========================
# ADD CAPACITY CODE
# =========================
id_to_zone = {v: k for k, v in zone_map.items()}

capacities_final["capacity_code"] = (
    capacities_final["from_zone_id"].map(id_to_zone)
    + "->"
    + capacities_final["to_zone_id"].map(id_to_zone)
)


# =========================
# SORT
# =========================
capacities_final = capacities_final[
    ["capacity_code", "from_zone_id", "to_zone_id", "delivery_day", "hour", "capacity_value"]
].copy()

capacities_final = capacities_final.sort_values(
    ["delivery_day", "hour", "from_zone_id", "to_zone_id"]
).reset_index(drop=True)

print("\nVista previa final:")
print(capacities_final.head(20))
print(f"\nFilas finales: {len(capacities_final)}")


# =========================
# RESET CAPACITIES TABLE
# =========================
# print("\nVaciando tabla Capacities y reiniciando capacity_id...")
#
# cursor = conn.cursor()
#
# cursor.execute("DELETE FROM Capacities")
#
# try:
#     cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'Capacities'")
# except sqlite3.OperationalError:
#     pass
#
# conn.commit()


# =========================
# INSERT INTO SQLITE
# =========================
print("\nInsertando datos en Capacities...")

capacities_final.to_sql(
    "Capacities",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.commit()
conn.close()

print("\nCapacities insertadas correctamente.")