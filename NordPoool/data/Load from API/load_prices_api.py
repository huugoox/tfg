from pathlib import Path
from datetime import date, timedelta
import sqlite3
import requests
import pandas as pd
import os
import time


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
    raise ValueError(
        "Faltan las variables de entorno "
        "NORDPOOL_USERNAME o NORDPOOL_PASSWORD"
    )

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

START_DATE = date(2000, 1, 1)
END_DATE = date(2026, 9, 9)

# Cada cuántos días hacemos insert en SQLite
BATCH_SIZE_DAYS = 30

# Número máximo de reintentos por día
MAX_RETRIES = 5


# =========================
# SESSION
# =========================
session = requests.Session()


# =========================
# ACCESS TOKEN
# =========================
def get_access_token(username: str, password: str) -> str:

    headers = {
        "Authorization":
            "Basic Y2xpZW50X21hcmtldGRhdGFfYXBpOmNsaWVudF9tYXJrZXRkYXRhX2FwaQ==",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "password",
        "scope": "marketdata_api",
        "username": username,
        "password": password,
    }

    response = session.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30
    )

    response.raise_for_status()

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
# DOWNLOAD DAY
# =========================
def get_prices_json_for_day(access_token, day):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    params = {
        "areas": AREAS,
        "market": MARKET,
        "currency": CURRENCY,
        "date": day.strftime("%Y-%m-%d"),
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = session.get(
                PRICES_URL,
                headers=headers,
                params=params,
                timeout=60
            )

            if response.status_code == 200:
                return response.json()

            # Rate limit / errores temporales
            if response.status_code in [429, 500, 502, 503, 504]:

                wait = attempt * 5

                print(
                    f"  Error {response.status_code}. "
                    f"Reintentando en {wait}s..."
                )

                time.sleep(wait)
                continue

            raise RuntimeError(
                f"Error {response.status_code} "
                f"para {day}: {response.text[:500]}"
            )

        except requests.RequestException as e:

            if attempt == MAX_RETRIES:
                raise

            wait = attempt * 5

            print(
                f"  Error de conexión: {e}. "
                f"Reintentando en {wait}s..."
            )

            time.sleep(wait)

    return None


# =========================
# JSON -> DATAFRAME
# =========================
def prices_json_to_long_dataframe(data):

    rows = []

    for area_data in data:

        zone_code = area_data["deliveryArea"]

        for item in area_data["prices"]:

            delivery_start_utc = pd.to_datetime(
                item["deliveryStart"],
                utc=True
            )

            delivery_start_local = (
                delivery_start_utc
                .tz_convert("Europe/Oslo")
            )

            rows.append({
                "zone_code": zone_code,
                "delivery_day": delivery_start_local.date(),
                "hour": delivery_start_local.hour,
                "price_value": item["price"],
            })

    return pd.DataFrame(rows)


# =========================
# CONNECT DATABASE
# =========================
conn = sqlite3.connect(db_path)

zones_df = pd.read_sql_query(
    """
    SELECT zone_id, zone_code
    FROM BiddingZones
    """,
    conn
)

zone_map = dict(
    zip(
        zones_df["zone_code"],
        zones_df["zone_id"]
    )
)


# =========================
# PREPARE DATAFRAME
# =========================
def prepare_dataframe(df):

    if df.empty:
        return df

    df["zone_id"] = df["zone_code"].map(zone_map)

    missing = df.loc[
        df["zone_id"].isna(),
        "zone_code"
    ].unique()

    if len(missing) > 0:
        raise ValueError(
            f"Zonas no encontradas: {missing}"
        )

    df = df[
        [
            "zone_id",
            "delivery_day",
            "hour",
            "price_value"
        ]
    ].copy()

    df["delivery_day"] = pd.to_datetime(
        df["delivery_day"]
    ).dt.strftime("%Y-%m-%d")

    df["zone_id"] = df["zone_id"].astype(int)

    df["hour"] = df["hour"].astype(int)

    df["price_value"] = pd.to_numeric(
        df["price_value"],
        errors="coerce"
    )

    df = df.dropna()

    df = df.sort_values(
        ["delivery_day", "hour", "zone_id"]
    )

    return df


# =========================
# DOWNLOAD
# =========================
print("Obteniendo access token...")

access_token = get_access_token(
    USERNAME,
    PASSWORD
)

batch = []

days_in_batch = 0
total_rows = 0


for day in daterange(START_DATE, END_DATE):

    print(f"Descargando {day}...")

    try:

        data = get_prices_json_for_day(
            access_token,
            day
        )

        if not data:
            print("  Sin datos.")
            continue

        df_day = prices_json_to_long_dataframe(data)

        if df_day.empty:
            print("  DataFrame vacío.")
            continue

        batch.append(df_day)
        days_in_batch += 1

    except Exception as e:

        print(f"  ERROR en {day}: {e}")

        # Continuamos con el siguiente día
        continue


    # =========================
    # WRITE BATCH
    # =========================
    if days_in_batch >= BATCH_SIZE_DAYS:

        df_batch = pd.concat(
            batch,
            ignore_index=True
        )

        df_batch = prepare_dataframe(
            df_batch
        )

        df_batch.to_sql(
            "Prices",
            conn,
            if_exists="append",
            index=False,
            chunksize=10000
        )

        conn.commit()

        total_rows += len(df_batch)

        print(
            f"  >>> Guardadas {len(df_batch):,} filas "
            f"(total: {total_rows:,})"
        )

        batch = []
        days_in_batch = 0


# =========================
# LAST BATCH
# =========================
if batch:

    df_batch = pd.concat(
        batch,
        ignore_index=True
    )

    df_batch = prepare_dataframe(
        df_batch
    )

    df_batch.to_sql(
        "Prices",
        conn,
        if_exists="append",
        index=False,
        chunksize=10000
    )

    conn.commit()

    total_rows += len(df_batch)


conn.close()

print("\n=========================")
print("DESCARGA FINALIZADA")
print("=========================")
print(f"Filas insertadas: {total_rows:,}")