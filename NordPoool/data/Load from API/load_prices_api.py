from pathlib import Path
from datetime import date, timedelta
import sqlite3
import requests
import pandas as pd
import os
import time
import json


# ============================================================
# CONFIGURATION
# ============================================================

project_root = Path(
    r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool"
)

db_path = project_root / "data" / "thesis_database.db"

checkpoint_path = (
    project_root
    / "data"
    / "load_prices_checkpoint.json"
)

errors_path = (
    project_root
    / "data"
    / "load_prices_errors.csv"
)


# Rango completo
START_DATE = date(2000, 1, 1)
END_DATE = date(2026, 9, 9)


# Número de reintentos si hay errores temporales
MAX_RETRIES = 5


# Timeout:
# primer valor = tiempo máximo para conectar
# segundo valor = tiempo máximo esperando respuesta
REQUEST_TIMEOUT = (10, 60)


# Si es True, utilizará el checkpoint y continuará
# desde donde se quedó.
RESUME = True


# ============================================================
# CHECK DATABASE
# ============================================================

if not db_path.exists():
    raise FileNotFoundError(
        f"No existe la base de datos:\n{db_path}"
    )


# ============================================================
# API CREDENTIALS
# ============================================================

USERNAME = os.getenv("NORDPOOL_USERNAME")
PASSWORD = os.getenv("NORDPOOL_PASSWORD")

if not USERNAME or not PASSWORD:
    raise ValueError(
        "Faltan las variables de entorno "
        "NORDPOOL_USERNAME o NORDPOOL_PASSWORD"
    )


# ============================================================
# API CONFIGURATION
# ============================================================

TOKEN_URL = (
    "https://sts.nordpoolgroup.com/connect/token"
)

PRICES_URL = (
    "https://data-api.nordpoolgroup.com/"
    "api/v2/Auction/Prices/ByAreas"
)


AREAS = [
    "DK1",
    "DK2",
    "EE",
    "FI",
    "LT",
    "LV",
    "NO1",
    "NO2",
    "NO3",
    "NO4",
    "NO5",
    "SE1",
    "SE2",
    "SE3",
    "SE4",
]


MARKET = "DayAhead"
CURRENCY = "EUR"


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()


# ============================================================
# ACCESS TOKEN
# ============================================================

def get_access_token(username, password):

    print("Obteniendo access token...")

    headers = {
        "Authorization":
            "Basic "
            "Y2xpZW50X21hcmtldGRhdGFfYXBp"
            "OmNsaWVudF9tYXJrZXRkYXRhX2FwaQ==",

        "Content-Type":
            "application/x-www-form-urlencoded",
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
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"Error obteniendo token: "
            f"{response.status_code}\n"
            f"{response.text[:1000]}"
        )

    print("Token obtenido correctamente.")

    return response.json()["access_token"]


# ============================================================
# DATE RANGE
# ============================================================

def daterange(start_date, end_date):

    current = start_date

    while current <= end_date:

        yield current

        current += timedelta(days=1)


# ============================================================
# CHECKPOINT
# ============================================================

def save_checkpoint(day):

    """
    Guarda de forma segura el último día completamente
    procesado.
    """

    data = {
        "last_processed_date":
            day.strftime("%Y-%m-%d")
    }

    temp_path = checkpoint_path.with_suffix(".tmp")

    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=4
        )

    # Reemplazo atómico
    temp_path.replace(checkpoint_path)


def load_checkpoint():

    if not checkpoint_path.exists():
        return None

    try:

        with open(
            checkpoint_path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        value = data.get(
            "last_processed_date"
        )

        if not value:
            return None

        return date.fromisoformat(value)

    except Exception as e:

        print(
            "No se ha podido leer el checkpoint:"
        )

        print(e)

        return None


# ============================================================
# ERROR LOG
# ============================================================

def log_error(day, error):

    new_row = pd.DataFrame(
        [
            {
                "date":
                    day.strftime("%Y-%m-%d"),

                "error":
                    str(error),
            }
        ]
    )

    if errors_path.exists():

        new_row.to_csv(
            errors_path,
            mode="a",
            header=False,
            index=False
        )

    else:

        new_row.to_csv(
            errors_path,
            index=False
        )


# ============================================================
# DOWNLOAD ONE DAY
# ============================================================

def get_prices_json_for_day(
    access_token,
    day
):

    """
    Descarga un día.

    Devuelve:
        data, access_token

    El token puede cambiar si ha sido necesario renovarlo.
    """

    params = {
        "areas": AREAS,
        "market": MARKET,
        "currency": CURRENCY,
        "date": day.strftime("%Y-%m-%d"),
    }

    current_token = access_token

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        headers = {
            "Authorization":
                f"Bearer {current_token}",

            "Accept":
                "application/json",
        }

        try:

            response = session.get(
                PRICES_URL,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )


            # --------------------------------------------
            # SUCCESS
            # --------------------------------------------

            if response.status_code == 200:

                return (
                    response.json(),
                    current_token
                )


            # --------------------------------------------
            # TOKEN EXPIRED
            # --------------------------------------------

            if response.status_code == 401:

                print(
                    "  Token expirado. "
                    "Obteniendo uno nuevo..."
                )

                current_token = get_access_token(
                    USERNAME,
                    PASSWORD
                )

                continue


            # --------------------------------------------
            # TEMPORARY ERRORS
            # --------------------------------------------

            if response.status_code in [
                429,
                500,
                502,
                503,
                504,
            ]:

                retry_after = (
                    response.headers.get(
                        "Retry-After"
                    )
                )

                if (
                    retry_after
                    and retry_after.isdigit()
                ):

                    wait = int(retry_after)

                else:

                    wait = min(
                        5 * (2 ** (attempt - 1)),
                        60
                    )

                print(
                    f"  Error HTTP "
                    f"{response.status_code}."
                )

                print(
                    f"  Reintento "
                    f"{attempt}/{MAX_RETRIES} "
                    f"en {wait}s..."
                )

                time.sleep(wait)

                continue


            # --------------------------------------------
            # NON TEMPORARY ERROR
            # --------------------------------------------

            raise RuntimeError(
                f"HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )


        # --------------------------------------------
        # NETWORK ERROR
        # --------------------------------------------

        except requests.RequestException as e:

            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    f"Error de conexión "
                    f"después de "
                    f"{MAX_RETRIES} intentos: "
                    f"{e}"
                )

            wait = min(
                5 * (2 ** (attempt - 1)),
                60
            )

            print(
                f"  Error de conexión: {e}"
            )

            print(
                f"  Reintento "
                f"{attempt}/{MAX_RETRIES} "
                f"en {wait}s..."
            )

            time.sleep(wait)


    raise RuntimeError(
        "Se alcanzó el máximo "
        "de reintentos."
    )


# ============================================================
# JSON -> DATAFRAME
# ============================================================

def prices_json_to_long_dataframe(data):

    rows = []

    if not data:
        return pd.DataFrame()

    for area_data in data:

        zone_code = area_data.get(
            "deliveryArea"
        )

        prices = area_data.get(
            "prices",
            []
        )

        for item in prices:

            delivery_start_utc = (
                pd.to_datetime(
                    item["deliveryStart"],
                    utc=True
                )
            )

            delivery_start_local = (
                delivery_start_utc
                .tz_convert(
                    "Europe/Oslo"
                )
            )

            rows.append(
                {
                    "zone_code":
                        zone_code,

                    "delivery_day":
                        delivery_start_local.date(),

                    "hour":
                        delivery_start_local.hour,

                    "price_value":
                        item["price"],
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# DATABASE CONNECTION
# ============================================================

conn = sqlite3.connect(
    db_path
)


# ============================================================
# GET BIDDING ZONES
# ============================================================

zones_df = pd.read_sql_query(
    """
    SELECT
        zone_id,
        zone_code
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


print(
    "\nZonas disponibles en la DB:"
)

print(
    sorted(zone_map.keys())
)


# ============================================================
# PREPARE DATAFRAME
# ============================================================

def prepare_dataframe(df):

    if df.empty:
        return df


    # --------------------------------------------
    # MAP ZONE CODE -> ID
    # --------------------------------------------

    df = df.copy()

    df["zone_id"] = (
        df["zone_code"]
        .map(zone_map)
    )


    missing = df.loc[
        df["zone_id"].isna(),
        "zone_code"
    ].unique()


    if len(missing) > 0:

        raise ValueError(
            "Zonas no encontradas "
            f"en BiddingZones: "
            f"{missing}"
        )


    # --------------------------------------------
    # SELECT FINAL COLUMNS
    # --------------------------------------------

    df = df[
        [
            "zone_id",
            "delivery_day",
            "hour",
            "price_value",
        ]
    ].copy()


    # --------------------------------------------
    # TYPES
    # --------------------------------------------

    df["delivery_day"] = (
        pd.to_datetime(
            df["delivery_day"]
        )
        .dt.strftime("%Y-%m-%d")
    )


    df["zone_id"] = (
        df["zone_id"]
        .astype(int)
    )


    df["hour"] = (
        df["hour"]
        .astype(int)
    )


    df["price_value"] = (
        pd.to_numeric(
            df["price_value"],
            errors="coerce"
        )
    )


    # --------------------------------------------
    # REMOVE INVALID VALUES
    # --------------------------------------------

    df = df.dropna(
        subset=[
            "zone_id",
            "delivery_day",
            "hour",
            "price_value",
        ]
    )


    # --------------------------------------------
    # SORT
    # --------------------------------------------

    df = df.sort_values(
        [
            "delivery_day",
            "hour",
            "zone_id",
        ]
    ).reset_index(drop=True)


    return df


# ============================================================
# INSERT ONE DAY
# ============================================================

def save_day_to_database(
    conn,
    day,
    df_day
):

    """
    Guarda un día de forma transaccional.

    Primero elimina los registros existentes
    de ese día para evitar duplicados.

    Después inserta los nuevos.

    Si algo falla, hace rollback.
    """

    day_string = day.strftime(
        "%Y-%m-%d"
    )

    try:

        cursor = conn.cursor()

        # Comenzar transacción
        cursor.execute(
            "BEGIN"
        )


        # --------------------------------------------
        # REMOVE EXISTING DAY
        # --------------------------------------------

        cursor.execute(
            """
            DELETE FROM Prices
            WHERE delivery_day = ?
            """,
            (day_string,)
        )


        # --------------------------------------------
        # INSERT NEW DATA
        # --------------------------------------------

        if not df_day.empty:

            df_day.to_sql(
                "Prices",
                conn,
                if_exists="append",
                index=False,
                chunksize=5000,
            )


        # --------------------------------------------
        # COMMIT
        # --------------------------------------------

        conn.commit()


    except Exception:

        conn.rollback()

        raise


# ============================================================
# DETERMINE START DATE
# ============================================================

actual_start_date = START_DATE


if RESUME:

    checkpoint = load_checkpoint()

    if checkpoint is not None:

        candidate_date = (
            checkpoint
            + timedelta(days=1)
        )

        if candidate_date > START_DATE:

            actual_start_date = (
                candidate_date
            )

            print(
                "\nCheckpoint encontrado."
            )

            print(
                "Último día procesado:",
                checkpoint
            )

            print(
                "Continuando desde:",
                actual_start_date
            )


if actual_start_date < START_DATE:

    actual_start_date = START_DATE


# ============================================================
# DOWNLOAD
# ============================================================

print("\n====================================")
print("DESCARGA NORD POOL")
print("====================================")

print(
    "Fecha inicial:",
    actual_start_date
)

print(
    "Fecha final:",
    END_DATE
)

print(
    "Número aproximado de días:",
    (END_DATE - actual_start_date).days + 1
)

print("====================================\n")


access_token = get_access_token(
    USERNAME,
    PASSWORD
)


total_rows_session = 0
processed_days = 0


try:

    for day in daterange(
        actual_start_date,
        END_DATE
    ):

        print(
            f"\nDescargando precios "
            f"para {day}..."
        )


        # --------------------------------------------
        # DOWNLOAD
        # --------------------------------------------

        try:

            data, access_token = (
                get_prices_json_for_day(
                    access_token,
                    day
                )
            )


            # ----------------------------------------
            # JSON -> DATAFRAME
            # ----------------------------------------

            df_day = (
                prices_json_to_long_dataframe(
                    data
                )
            )


            print(
                f"  Filas recibidas: "
                f"{len(df_day):,}"
            )


            # ----------------------------------------
            # NO DATA
            # ----------------------------------------

            if df_day.empty:

                print(
                    "  Sin datos para "
                    "este día."
                )

                # Marcamos el día como procesado.
                save_checkpoint(day)

                processed_days += 1

                continue


            # ----------------------------------------
            # PREPARE
            # ----------------------------------------

            df_day = prepare_dataframe(
                df_day
            )


            print(
                f"  Filas válidas: "
                f"{len(df_day):,}"
            )


            # ----------------------------------------
            # DATABASE
            # ----------------------------------------

            save_day_to_database(
                conn,
                day,
                df_day
            )


            total_rows_session += (
                len(df_day)
            )

            processed_days += 1


            # ----------------------------------------
            # CHECKPOINT
            # ----------------------------------------

            save_checkpoint(day)


            print(
                f"  >>> {len(df_day):,} "
                f"filas guardadas."
            )

            print(
                f"  >>> Total sesión: "
                f"{total_rows_session:,}"
            )


        # --------------------------------------------
        # ERROR FOR THIS DAY
        # --------------------------------------------

        except Exception as e:

            print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(
                f"ERROR procesando {day}"
            )
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

            print(e)

            log_error(
                day,
                e
            )

            print(
                "\nLa descarga se detiene "
                "para no dejar huecos."
            )

            print(
                "Vuelve a ejecutar el script "
                "y continuará desde este día."
            )

            break


# ============================================================
# CTRL + C
# ============================================================

except KeyboardInterrupt:

    print(
        "\n\n===================================="
    )

    print(
        "DESCARGA INTERRUMPIDA "
        "MANUALMENTE"
    )

    print(
        "===================================="
    )

    print(
        "Los días anteriores ya están "
        "guardados en SQLite."
    )

    checkpoint = load_checkpoint()

    if checkpoint:

        print(
            "Último día completamente "
            "guardado:",
            checkpoint
        )

        print(
            "La próxima ejecución "
            "continuará desde:",
            checkpoint + timedelta(days=1)
        )


# ============================================================
# FINALLY
# ============================================================

finally:

    conn.close()

    session.close()


# ============================================================
# SUMMARY
# ============================================================

print("\n====================================")
print("FIN DE LA EJECUCIÓN")
print("====================================")

print(
    f"Días procesados "
    f"esta sesión: {processed_days:,}"
)

print(
    f"Filas guardadas "
    f"esta sesión: {total_rows_session:,}"
)

checkpoint = load_checkpoint()

if checkpoint:

    print(
        f"Última fecha procesada: "
        f"{checkpoint}"
    )

print("====================================")