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
PRICES_URL = "https://data-api.nordpoolgroup.com/api/v2/Auction/Prices/ByAreas"

AREAS = [
    "DK1", "DK2",
    "EE", "FI", "LT", "LV",
    "NO1", "NO2", "NO3", "NO4", "NO5",
    "SE1", "SE2", "SE3", "SE4"
]

MARKET = "DayAhead"
CURRENCY = "EUR"

# Cambia aquí el rango que quieres cargar
START_DATE = date(2000, 1, 1)
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
def get_prices_json_for_day(access_token: str, areas: list[str], day: date):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    params = {
        "areas": areas,
        "market": MARKET,
        "currency": CURRENCY,
        "date": day.strftime("%Y-%m-%d"),
    }

    response = requests.get(PRICES_URL, headers=headers, params=params)

    if response.status_code != 200:
        raise RuntimeError(
            f"Error descargando {day}: {response.status_code}\n{response.text[:1000]}"
        )

    return response.json()


# =========================
# JSON TO LONG DATAFRAME
# =========================
def prices_json_to_long_dataframe(data) -> pd.DataFrame:
    rows = []

    for area_data in data:
        zone_code = area_data["deliveryArea"]

        for item in area_data["prices"]:
            delivery_start_utc = pd.to_datetime(item["deliveryStart"], utc=True)
            delivery_start_local = delivery_start_utc.tz_convert("Europe/Oslo")

            rows.append({
                "zone_code": zone_code,
                "delivery_day": delivery_start_local.date(),
                "hour": delivery_start_local.hour,
                "price_value": item["price"],
            })

    return pd.DataFrame(rows)


# =========================
# MAIN
# =========================
print("Obteniendo access token...")
access_token = get_access_token(USERNAME, PASSWORD)

all_prices = []

for day in daterange(START_DATE, END_DATE):
    print(f"Descargando precios para {day}...")

    data = get_prices_json_for_day(
        access_token=access_token,
        areas=AREAS,
        day=day
    )

    df_day = prices_json_to_long_dataframe(data)
    all_prices.append(df_day)

if not all_prices:
    raise ValueError("No se ha descargado ningún dato.")

prices_long = pd.concat(all_prices, ignore_index=True)

print("\nShape descargado:", prices_long.shape)
print(prices_long.head())


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
print("Zone codes descargados:", sorted(prices_long["zone_code"].unique()))


# =========================
# MAP ZONE CODES TO ZONE IDS
# =========================
prices_long["zone_id"] = prices_long["zone_code"].map(zone_map)

missing_zones = prices_long.loc[
    prices_long["zone_id"].isna(),
    "zone_code"
].unique()

if len(missing_zones) > 0:
    conn.close()
    raise ValueError(f"Zonas no encontradas en BiddingZones: {missing_zones}")


# =========================
# FINAL DATAFRAME
# =========================
prices_final = prices_long[
    ["zone_id", "delivery_day", "hour", "price_value"]
].copy()

prices_final["delivery_day"] = pd.to_datetime(
    prices_final["delivery_day"]
).dt.strftime("%Y-%m-%d")

prices_final["hour"] = prices_final["hour"].astype(int)
prices_final["zone_id"] = prices_final["zone_id"].astype(int)
prices_final["price_value"] = pd.to_numeric(
    prices_final["price_value"],
    errors="coerce"
)

prices_final = prices_final.dropna(
    subset=["zone_id", "delivery_day", "hour", "price_value"]
)

# Ordenado para que encaje bien con análisis temporal/event-based
prices_final = prices_final.sort_values(
    ["delivery_day", "hour", "zone_id"]
).reset_index(drop=True)

print("\nVista previa final:")
print(prices_final.head(20))
print(f"\nFilas finales: {len(prices_final)}")


# =========================
# RESET PRICES TABLE
# =========================
print("\nVaciando tabla Prices y reiniciando price_id...")

cursor = conn.cursor()

cursor.execute("DELETE FROM Prices")

try:
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'Prices'")
except sqlite3.OperationalError:
    pass

conn.commit()


# =========================
# INSERT INTO SQLITE
# =========================
print("\nInsertando datos en Prices...")

prices_final.to_sql(
    "Prices",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.commit()
conn.close()

print("\nPrices insertados correctamente.")