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
    / "load_flows_checkpoint.json"
)

errors_path = (
    project_root
    / "data"
    / "load_flows_errors.csv"
)


START_DATE = date(2015, 1, 1)
END_DATE = date(2026, 9, 9)

MAX_RETRIES = 5

REQUEST_TIMEOUT = (10, 60)

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

FLOWS_URL = (
    "https://data-api.nordpoolgroup.com/"
    "api/v2/Auction/Flows/ByAreas"
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

def get_flows_json_for_day(
    access_token,
    day
):

    params = {
        "areas": AREAS,
        "market": MARKET,
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
                FLOWS_URL,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )


            # SUCCESS
            if response.status_code == 200:

                return (
                    response.json(),
                    current_token
                )


            # TOKEN EXPIRED
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


            # TEMPORARY ERRORS
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


            # NON TEMPORARY ERROR
            raise RuntimeError(
                f"HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )


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

valid_zone_codes = set(
    zone_map.keys()
)

print(
    "\nZonas disponibles en la DB:"
)

print(
    sorted(valid_zone_codes)
)


# ============================================================
# JSON -> DATAFRAME
# ============================================================

def flows_json_to_long_dataframe(
    data,
    valid_zone_codes
):

    rows = []
    skipped_external_connections = set()

    if not data:
        return pd.DataFrame()

    for area_data in data:

        delivery_area = area_data.get(
            "deliveryArea"
        )

        if (
            delivery_area
            not in valid_zone_codes
        ):

            skipped_external_connections.add(
                delivery_area
            )

            continue


        flows = area_data.get(
            "flows",
            []
        )


        for flow_item in flows:

            delivery_start_utc = (
                pd.to_datetime(
                    flow_item["deliveryStart"],
                    utc=True
                )
            )

            delivery_start_local = (
                delivery_start_utc
                .tz_convert(
                    "Europe/Oslo"
                )
            )

            delivery_day = (
                delivery_start_local.date()
            )

            hour = (
                delivery_start_local.hour
            )


            connections = (
                flow_item.get(
                    "byConnections",
                    []
                )
            )


            for connection in connections:

                connection_area = (
                    connection.get("area")
                )


                # Ignorar conexiones externas
                if (
                    connection_area
                    not in valid_zone_codes
                ):

                    skipped_external_connections.add(
                        connection_area
                    )

                    continue


                import_value = (
                    connection.get(
                        "import",
                        0
                    )
                    or 0
                )

                export_value = (
                    connection.get(
                        "export",
                        0
                    )
                    or 0
                )


                # Import into delivery_area:
                # connection_area -> delivery_area
                if import_value != 0:

                    rows.append(
                        {
                            "from_zone_code":
                                connection_area,

                            "to_zone_code":
                                delivery_area,

                            "delivery_day":
                                delivery_day,

                            "hour":
                                hour,

                            "flow_value":
                                import_value,
                        }
                    )


                # Export from delivery_area:
                # delivery_area -> connection_area
                if export_value != 0:

                    rows.append(
                        {
                            "from_zone_code":
                                delivery_area,

                            "to_zone_code":
                                connection_area,

                            "delivery_day":
                                delivery_day,

                            "hour":
                                hour,

                            "flow_value":
                                export_value,
                        }
                    )


    if skipped_external_connections:

        print(
            "  Conexiones externas ignoradas:",
            sorted(
                skipped_external_connections
            )
        )


    return pd.DataFrame(rows)


# ============================================================
# PREPARE DATAFRAME
# ============================================================

def prepare_dataframe(df):

    if df.empty:
        return df

    df = df.copy()


    # MAP ZONES
    df["from_zone_id"] = (
        df["from_zone_code"]
        .map(zone_map)
    )

    df["to_zone_id"] = (
        df["to_zone_code"]
        .map(zone_map)
    )


    missing_from = df.loc[
        df["from_zone_id"].isna(),
        "from_zone_code"
    ].unique()

    missing_to = df.loc[
        df["to_zone_id"].isna(),
        "to_zone_code"
    ].unique()


    if (
        len(missing_from) > 0
        or len(missing_to) > 0
    ):

        raise ValueError(
            "Zonas no encontradas. "
            f"From missing: {missing_from}. "
            f"To missing: {missing_to}"
        )


    # FINAL COLUMNS
    df = df[
        [
            "from_zone_id",
            "to_zone_id",
            "delivery_day",
            "hour",
            "flow_value",
        ]
    ].copy()


    # TYPES
    df["from_zone_id"] = (
        df["from_zone_id"]
        .astype(int)
    )

    df["to_zone_id"] = (
        df["to_zone_id"]
        .astype(int)
    )

    df["delivery_day"] = (
        pd.to_datetime(
            df["delivery_day"]
        )
        .dt.strftime("%Y-%m-%d")
    )

    df["hour"] = (
        df["hour"]
        .astype(int)
    )

    df["flow_value"] = (
        pd.to_numeric(
            df["flow_value"],
            errors="coerce"
        )
    )


    # REMOVE INVALID
    df = df.dropna(
        subset=[
            "from_zone_id",
            "to_zone_id",
            "delivery_day",
            "hour",
            "flow_value",
        ]
    )


    # REMOVE DUPLICATES
    duplicate_mask = (
        df.duplicated(
            subset=[
                "from_zone_id",
                "to_zone_id",
                "delivery_day",
                "hour",
            ],
            keep="first"
        )
    )

    num_duplicates = (
        duplicate_mask.sum()
    )

    if num_duplicates > 0:

        print(
            f"  Duplicados detectados: "
            f"{num_duplicates}"
        )


    df = (
        df.drop_duplicates(
            subset=[
                "from_zone_id",
                "to_zone_id",
                "delivery_day",
                "hour",
            ],
            keep="first"
        )
        .copy()
    )


    # SORT
    df = (
        df.sort_values(
            [
                "delivery_day",
                "hour",
                "from_zone_id",
                "to_zone_id",
            ]
        )
        .reset_index(drop=True)
    )


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
    Guarda todos los flows de un día.

    Primero elimina los flows existentes
    para esa fecha para evitar duplicados.

    Después inserta los nuevos.

    Si algo falla, hace rollback.
    """

    day_string = (
        day.strftime("%Y-%m-%d")
    )

    try:

        cursor = conn.cursor()

        cursor.execute(
            "BEGIN"
        )


        # REMOVE EXISTING DAY
        cursor.execute(
            """
            DELETE FROM Flows
            WHERE delivery_day = ?
            """,
            (day_string,)
        )


        # INSERT NEW DATA
        if not df_day.empty:

            df_day.to_sql(
                "Flows",
                conn,
                if_exists="append",
                index=False,
                chunksize=5000,
            )


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
print("DESCARGA NORD POOL FLOWS")
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
            f"\nDescargando flows "
            f"para {day}..."
        )


        try:

            # DOWNLOAD
            data, access_token = (
                get_flows_json_for_day(
                    access_token,
                    day
                )
            )


            # JSON -> DATAFRAME
            df_day = (
                flows_json_to_long_dataframe(
                    data,
                    valid_zone_codes
                )
            )


            print(
                f"  Filas recibidas: "
                f"{len(df_day):,}"
            )


            # NO DATA
            if df_day.empty:

                print(
                    "  Sin flows internos "
                    "para este día."
                )

                if RESUME:
                    save_checkpoint(day)

                processed_days += 1

                continue


            # PREPARE
            df_day = prepare_dataframe(
                df_day
            )


            print(
                f"  Filas válidas: "
                f"{len(df_day):,}"
            )


            # DATABASE
            save_day_to_database(
                conn,
                day,
                df_day
            )


            total_rows_session += (
                len(df_day)
            )

            processed_days += 1


            # CHECKPOINT
            if RESUME:
                save_checkpoint(day)


            print(
                f"  >>> {len(df_day):,} "
                f"filas guardadas."
            )

            print(
                f"  >>> Total sesión: "
                f"{total_rows_session:,}"
            )


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