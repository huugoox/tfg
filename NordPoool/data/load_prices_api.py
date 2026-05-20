from pathlib import Path
from datetime import date, timedelta
import sqlite3
import requests
import pandas as pd


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
USERNAME = "API_DATA_USN"
PASSWORD = "t1E7(So6vw3CSp1Y%)"

TOKEN_URL = "https://sts.nordpoolgroup.com/connect/token"
PRICES_URL = "https://data-api.nordpoolgroup.com/api/v2/Auction/Prices/ByAreas"

AREAS = [
    "EE", "LT", "LV",
    "DK1", "DK2", "FI",
    "NO1", "NO2", "NO3", "NO4", "NO5",
    "SE1", "SE2", "SE3", "SE4"
]

MARKET = "DayAhead"
CURRENCY = "EUR"

START_DATE = date(2019, 1, 1)
END_DATE = date(2019, 1, 3)  # Primero probamos solo 3 días

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

prices_long = pd.concat(all_prices, ignore_index=True)

print("Shape descargado:", prices_long.shape)
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

print("Zone codes en DB:", sorted(valid_zone_codes))
print("Zone codes descargados:", sorted(prices_long["zone_code"].unique()))