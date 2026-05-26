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
VOLUMES_URL = "https://data-api.nordpoolgroup.com/api/v2/Auction/Volumes/ByAreas"

AREAS = [
    "DK1", "DK2",
    "EE", "FI", "LT", "LV",
    "NO1", "NO2", "NO3", "NO4", "NO5",
    "SE1", "SE2", "SE3", "SE4"
]

MARKET = "DayAhead"

# Cambia aquí el rango que quieres cargar
START_DATE = date(2004, 1, 1)
END_DATE = date(2007, 12, 31)


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
def get_volumes_json_for_day(access_token: str, areas: list[str], day: date):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    params = {
        "areas": areas,
        "market": MARKET,
        "date": day.strftime("%Y-%m-%d"),
    }

    response = requests.get(VOLUMES_URL, headers=headers, params=params)

    if response.status_code != 200:
        raise RuntimeError(
            f"Error descargando {day}: {response.status_code}\n{response.text[:1000]}"
        )

    return response.json()


# =========================
# JSON TO LONG DATAFRAME
# =========================
def volumes_json_to_long_dataframe(data) -> pd.DataFrame:
    rows = []

    for area_data in data:
        zone_code = area_data["deliveryArea"]

        for item in area_data["volumes"]:
            delivery_start_utc = pd.to_datetime(item["deliveryStart"], utc=True)
            delivery_start_local = delivery_start_utc.tz_convert("Europe/Oslo")

            rows.append({
                "zone_code": zone_code,
                "delivery_day": delivery_start_local.date(),
                "hour": delivery_start_local.hour,
                "buy_volume_value": item["buy"],
                "sell_volume_value": item["sell"],
            })

    return pd.DataFrame(rows)


# =========================
# MAIN
# =========================
print("Obteniendo access token...")
access_token = get_access_token(USERNAME, PASSWORD)

all_volumes = []

for day in daterange(START_DATE, END_DATE):
    print(f"Descargando volumes para {day}...")

    data = get_volumes_json_for_day(
        access_token=access_token,
        areas=AREAS,
        day=day
    )

    df_day = volumes_json_to_long_dataframe(data)
    all_volumes.append(df_day)

if not all_volumes:
    raise ValueError("No se ha descargado ningún dato.")

volumes_long = pd.concat(all_volumes, ignore_index=True)

print("\nShape descargado:", volumes_long.shape)
print(volumes_long.head())


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
print("Zone codes descargados:", sorted(volumes_long["zone_code"].unique()))


# =========================
# MAP ZONE CODES TO ZONE IDS
# =========================
volumes_long["zone_id"] = volumes_long["zone_code"].map(zone_map)

missing_zones = volumes_long.loc[
    volumes_long["zone_id"].isna(),
    "zone_code"
].unique()

if len(missing_zones) > 0:
    conn.close()
    raise ValueError(f"Zonas no encontradas en BiddingZones: {missing_zones}")


# =========================
# FINAL DATAFRAME
# =========================
volumes_final = volumes_long[
    [
        "zone_id",
        "delivery_day",
        "hour",
        "buy_volume_value",
        "sell_volume_value"
    ]
].copy()

volumes_final["delivery_day"] = pd.to_datetime(
    volumes_final["delivery_day"]
).dt.strftime("%Y-%m-%d")

volumes_final["hour"] = volumes_final["hour"].astype(int)
volumes_final["zone_id"] = volumes_final["zone_id"].astype(int)

volumes_final["buy_volume_value"] = pd.to_numeric(
    volumes_final["buy_volume_value"],
    errors="coerce"
)

volumes_final["sell_volume_value"] = pd.to_numeric(
    volumes_final["sell_volume_value"],
    errors="coerce"
)

volumes_final = volumes_final.dropna(
    subset=[
        "zone_id",
        "delivery_day",
        "hour",
        "buy_volume_value",
        "sell_volume_value"
    ]
)

# Ordenado para que encaje bien con análisis temporal/event-based
volumes_final = volumes_final.sort_values(
    ["delivery_day", "hour", "zone_id"]
).reset_index(drop=True)

print("\nVista previa final:")
print(volumes_final.head(20))
print(f"\nFilas finales: {len(volumes_final)}")


# =========================
# RESET VOLUMES TABLE
# =========================
# print("\nVaciando tabla Volumes y reiniciando volume_id...")

# cursor = conn.cursor()

# cursor.execute("DELETE FROM Volumes")

# try:
#     cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'Volumes'")
# except sqlite3.OperationalError:
#     pass

# conn.commit()


# =========================
# INSERT INTO SQLITE
# =========================
print("\nInsertando datos en Volumes...")

volumes_final.to_sql(
    "Volumes",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.commit()
conn.close()

print("\nVolumes insertados correctamente.")