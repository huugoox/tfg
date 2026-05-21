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
FLOWS_URL = "https://data-api.nordpoolgroup.com/api/v2/Auction/Flows/ByAreas"

AREAS = [
    "DK1", "DK2",
    "EE", "FI", "LT", "LV",
    "NO1", "NO2", "NO3", "NO4", "NO5",
    "SE1", "SE2", "SE3", "SE4"
]

MARKET = "DayAhead"

# Primero prueba pocos días
START_DATE = date(2015, 1, 1)
END_DATE = date(2024, 12, 31)


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
def get_flows_json_for_day(access_token: str, areas: list[str], day: date):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    params = {
        "areas": areas,
        "market": MARKET,
        "date": day.strftime("%Y-%m-%d"),
    }

    response = requests.get(FLOWS_URL, headers=headers, params=params)

    if response.status_code != 200:
        raise RuntimeError(
            f"Error descargando {day}: {response.status_code}\n{response.text[:1000]}"
        )

    return response.json()


# =========================
# JSON TO LONG DATAFRAME
# =========================
def flows_json_to_long_dataframe(data, valid_zone_codes: set[str]) -> pd.DataFrame:
    rows = []
    skipped_external_connections = set()

    for area_data in data:
        delivery_area = area_data["deliveryArea"]

        if delivery_area not in valid_zone_codes:
            skipped_external_connections.add(delivery_area)
            continue

        for flow_item in area_data["flows"]:
            delivery_start_utc = pd.to_datetime(flow_item["deliveryStart"], utc=True)
            delivery_start_local = delivery_start_utc.tz_convert("Europe/Oslo")

            delivery_day = delivery_start_local.date()
            hour = delivery_start_local.hour

            for connection in flow_item["byConnections"]:
                connection_area = connection["area"]

                if connection_area not in valid_zone_codes:
                    skipped_external_connections.add(connection_area)
                    continue

                import_value = connection.get("import", 0) or 0
                export_value = connection.get("export", 0) or 0

                # Import into delivery_area:
                # connection_area -> delivery_area
                if import_value != 0:
                    rows.append({
                        "from_zone_code": connection_area,
                        "to_zone_code": delivery_area,
                        "delivery_day": delivery_day,
                        "hour": hour,
                        "flow_value": import_value,
                    })

                # Export from delivery_area:
                # delivery_area -> connection_area
                if export_value != 0:
                    rows.append({
                        "from_zone_code": delivery_area,
                        "to_zone_code": connection_area,
                        "delivery_day": delivery_day,
                        "hour": hour,
                        "flow_value": export_value,
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
all_flows = []

for day in daterange(START_DATE, END_DATE):
    print(f"Descargando flows para {day}...")

    data = get_flows_json_for_day(
        access_token=access_token,
        areas=AREAS,
        day=day
    )

    df_day = flows_json_to_long_dataframe(
        data=data,
        valid_zone_codes=valid_zone_codes
    )

    all_flows.append(df_day)

if not all_flows:
    conn.close()
    raise ValueError("No se ha descargado ningún dato.")

flows_long = pd.concat(all_flows, ignore_index=True)

if flows_long.empty:
    conn.close()
    raise ValueError("La descarga no produjo flows internos entre zonas de la DB.")

print("\nShape descargado:", flows_long.shape)
print(flows_long.head())


# =========================
# MAP ZONE CODES TO ZONE IDS
# =========================
flows_long["from_zone_id"] = flows_long["from_zone_code"].map(zone_map)
flows_long["to_zone_id"] = flows_long["to_zone_code"].map(zone_map)

missing_from = flows_long.loc[
    flows_long["from_zone_id"].isna(),
    "from_zone_code"
].unique()

missing_to = flows_long.loc[
    flows_long["to_zone_id"].isna(),
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
flows_final = flows_long[
    ["from_zone_id", "to_zone_id", "delivery_day", "hour", "flow_value"]
].copy()

flows_final["from_zone_id"] = flows_final["from_zone_id"].astype(int)
flows_final["to_zone_id"] = flows_final["to_zone_id"].astype(int)

flows_final["delivery_day"] = pd.to_datetime(
    flows_final["delivery_day"]
).dt.strftime("%Y-%m-%d")

flows_final["hour"] = flows_final["hour"].astype(int)
flows_final["flow_value"] = pd.to_numeric(
    flows_final["flow_value"],
    errors="coerce"
)

flows_final = flows_final.dropna(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour", "flow_value"]
)


# =========================
# REMOVE DUPLICATES
# =========================
print(f"\nFilas antes de deduplicar: {len(flows_final)}")

duplicate_mask = flows_final.duplicated(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour"],
    keep="first"
)

num_duplicates = duplicate_mask.sum()
print(f"Duplicados detectados: {num_duplicates}")

if num_duplicates > 0:
    print("Ejemplo de duplicados:")
    print(flows_final.loc[duplicate_mask].head(10))

flows_final = flows_final.drop_duplicates(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour"],
    keep="first"
).copy()


# =========================
# SORT
# =========================
flows_final = flows_final.sort_values(
    ["delivery_day", "hour", "from_zone_id", "to_zone_id"]
).reset_index(drop=True)

print("\nVista previa final:")
print(flows_final.head(20))
print(f"\nFilas finales: {len(flows_final)}")


# =========================
# RESET FLOWS TABLE
# =========================
print("\nVaciando tabla Flows y reiniciando flow_id...")

cursor = conn.cursor()

cursor.execute("DELETE FROM Flows")

try:
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'Flows'")
except sqlite3.OperationalError:
    pass

conn.commit()


# =========================
# INSERT INTO SQLITE
# =========================
print("\nInsertando datos en Flows...")

flows_final.to_sql(
    "Flows",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.commit()
conn.close()

print("\nFlows insertados correctamente.")