from pathlib import Path
import sqlite3
import pandas as pd
import re


# =========================
# PATHS
# =========================
project_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool")
db_path = project_root / "data" / "thesis_database.db"

data_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\TFG_Data")
capacities_root = data_root / "Capacities"

if not db_path.exists():
    raise FileNotFoundError(f"No existe la base de datos: {db_path}")

if not capacities_root.exists():
    raise FileNotFoundError(f"No existe la carpeta de capacities: {capacities_root}")


# =========================
# READ CAPACITY FILE
# =========================
def read_capacity_file(file_path: Path) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=None)

    header_candidates = df[
        df.iloc[:, 0]
        .astype(str)
        .str.contains("Delivery period", na=False)
    ].index

    if len(header_candidates) == 0:
        raise ValueError(
            f"No se encontró la fila de cabecera con 'Delivery period' en {file_path.name}"
        )

    header_row = header_candidates[0]
    df.columns = df.iloc[header_row]
    df = df[(header_row + 1):].reset_index(drop=True)

    return df


# =========================
# EXTRACT DATE
# =========================
def extract_date_from_filename(file_path: Path) -> pd.Timestamp:
    """
    Extrae la fecha desde el nombre del archivo.
    Si el nombre contiene algo como 2020-01-01, lo detecta.
    """
    match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)

    if not match:
        raise ValueError(f"No se pudo extraer la fecha del archivo: {file_path.name}")

    return pd.to_datetime(match.group(1))


# =========================
# PARSE CAPACITY COLUMN
# =========================
def parse_capacity_column(col_name: str):
    """
    Convierte una columna tipo:
    'NO1 -> NO3 (MW)'
    en:
    ('NO1', 'NO3')

    Ignora columnas tipo:
    'NO1 Total Import Capacity (MW)'
    'NO1 Total Export Capacity (MW)'
    """

    col_name = str(col_name).strip()

    # Exclude total import/export capacity columns
    if "Total" in col_name:
        return None

    # Remove unit
    col_name = re.sub(r"\s*\(MW\)\s*$", "", col_name).strip()

    match = re.match(r"^([A-Z0-9]+)\s*->\s*([A-Z0-9]+)$", col_name)

    if not match:
        return None

    from_zone = match.group(1).strip()
    to_zone = match.group(2).strip()

    return from_zone, to_zone


# =========================
# BUILD RAW DATAFRAME
# =========================
capacity_files = sorted(capacities_root.rglob("*.xlsx"))

print(f"Archivos encontrados: {len(capacity_files)}")

capacities_dfs = []

for file in capacity_files:
    try:
        df = read_capacity_file(file)
        df["delivery_day"] = extract_date_from_filename(file)
        df["source_file"] = file.name
        capacities_dfs.append(df)

    except Exception as e:
        print(f"Error leyendo {file.name}: {e}")

if not capacities_dfs:
    raise ValueError("No se ha podido leer ningún archivo de capacities.")

capacities_raw = pd.concat(capacities_dfs, ignore_index=True)

print("Shape combinado:", capacities_raw.shape)
print("Columnas originales:")
print(capacities_raw.columns.tolist())


# =========================
# CLEAN COLUMNS
# =========================
capacities_raw.columns = [str(col).strip() for col in capacities_raw.columns]

delivery_period_col = None

for col in capacities_raw.columns:
    if "Delivery period" in col:
        delivery_period_col = col
        break

if delivery_period_col is None:
    raise ValueError("No se encontró la columna 'Delivery period'.")

capacities_raw = capacities_raw.rename(columns={delivery_period_col: "delivery_period"})


# =========================
# FILTER VALID HOURLY ROWS
# =========================
capacities_raw["delivery_period"] = capacities_raw["delivery_period"].astype(str).str.strip()

valid_period_mask = capacities_raw["delivery_period"].str.match(
    r"^\d{2}:\d{2}\s*-\s*\d{2}:\d{2}$",
    na=False
)

invalid_periods = capacities_raw.loc[~valid_period_mask, "delivery_period"].unique()

if len(invalid_periods) > 0:
    print("Delivery periods no válidos detectados y excluidos:")
    print(invalid_periods[:20])

capacities_raw = capacities_raw.loc[valid_period_mask].copy()


# =========================
# EXTRACT HOUR
# =========================
capacities_raw["hour"] = capacities_raw["delivery_period"].str.extract(r"^(\d{2}):")[0]
capacities_raw["hour"] = pd.to_numeric(capacities_raw["hour"], errors="coerce")

capacities_raw = capacities_raw.dropna(subset=["hour"]).copy()
capacities_raw["hour"] = capacities_raw["hour"].astype(int)


# =========================
# CONNECT TO DB AND GET ZONES
# =========================
conn = sqlite3.connect(db_path)

conn.execute("DELETE FROM Capacities")

try:
    conn.execute("DELETE FROM sqlite_sequence WHERE name='Capacities'")
except sqlite3.OperationalError:
    pass

conn.commit()

zones_df = pd.read_sql_query(
    "SELECT zone_id, zone_code FROM BiddingZones",
    conn
)

zone_map = dict(zip(zones_df["zone_code"], zones_df["zone_id"]))
valid_zone_codes = set(zone_map.keys())

print("Zone codes en DB:", sorted(valid_zone_codes))


# =========================
# IDENTIFY CAPACITY COLUMNS
# =========================
capacity_columns = []
capacity_column_map = {}

for col in capacities_raw.columns:
    if col in ["delivery_period", "delivery_day", "source_file", "hour"]:
        continue

    parsed = parse_capacity_column(col)

    if parsed is None:
        continue

    from_zone, to_zone = parsed

    capacity_columns.append(col)
    capacity_column_map[col] = (from_zone, to_zone)

print("Columnas de capacities detectadas:")
print(capacity_columns[:20])
print(f"Total columnas de capacities detectadas: {len(capacity_columns)}")

if not capacity_columns:
    raise ValueError(
        "No se detectó ninguna columna de capacity con formato 'ZONE1 -> ZONE2 (MW)'."
    )


# =========================
# WIDE TO LONG
# =========================
capacities_long = capacities_raw.melt(
    id_vars=["delivery_day", "hour", "source_file"],
    value_vars=capacity_columns,
    var_name="capacity_direction",
    value_name="capacity_value"
)

capacities_long["from_zone_code"] = capacities_long["capacity_direction"].map(
    lambda x: capacity_column_map[x][0]
)

capacities_long["to_zone_code"] = capacities_long["capacity_direction"].map(
    lambda x: capacity_column_map[x][1]
)

capacities_long["capacity_code"] = (
    capacities_long["from_zone_code"]
    + "->"
    + capacities_long["to_zone_code"]
)


# =========================
# CLEAN NUMERIC VALUES
# =========================
capacities_long["capacity_value"] = (
    capacities_long["capacity_value"]
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.strip()
)

capacities_long["capacity_value"] = pd.to_numeric(
    capacities_long["capacity_value"],
    errors="coerce"
)


# =========================
# MAP ZONE CODES TO IDS
# =========================
capacities_long["from_zone_id"] = capacities_long["from_zone_code"].map(zone_map)
capacities_long["to_zone_id"] = capacities_long["to_zone_code"].map(zone_map)

missing_from = (
    capacities_long.loc[
        capacities_long["from_zone_id"].isna(),
        "from_zone_code"
    ]
    .dropna()
    .unique()
)

missing_to = (
    capacities_long.loc[
        capacities_long["to_zone_id"].isna(),
        "to_zone_code"
    ]
    .dropna()
    .unique()
)

if len(missing_from) > 0:
    print("Aviso, zonas origen no encontradas en DB:")
    print(sorted(missing_from))

if len(missing_to) > 0:
    print("Aviso, zonas destino no encontradas en DB:")
    print(sorted(missing_to))


# =========================
# FINAL DATAFRAME
# =========================
capacities_final = capacities_long[
    [
        "capacity_code",
        "from_zone_id",
        "to_zone_id",
        "delivery_day",
        "hour",
        "capacity_value",
        "source_file"
    ]
].copy()

capacities_final = capacities_final.dropna(
    subset=[
        "capacity_code",
        "from_zone_id",
        "to_zone_id",
        "delivery_day",
        "hour",
        "capacity_value"
    ]
)

capacities_final["from_zone_id"] = capacities_final["from_zone_id"].astype(int)
capacities_final["to_zone_id"] = capacities_final["to_zone_id"].astype(int)

capacities_final["delivery_day"] = (
    pd.to_datetime(capacities_final["delivery_day"])
    .dt.strftime("%Y-%m-%d")
)

capacities_final["hour"] = capacities_final["hour"].astype(int)

print(f"Filas a insertar antes de eliminar duplicados: {len(capacities_final)}")


# =========================
# REMOVE DUPLICATES
# =========================
duplicate_mask = capacities_final.duplicated(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour"],
    keep="first"
)

num_duplicates = duplicate_mask.sum()
print(f"Duplicados exactos detectados: {num_duplicates}")

if num_duplicates > 0:
    print("Ejemplo de duplicados:")
    print(
        capacities_final.loc[
            duplicate_mask,
            [
                "capacity_code",
                "from_zone_id",
                "to_zone_id",
                "delivery_day",
                "hour",
                "capacity_value",
                "source_file"
            ]
        ].head(10)
    )

capacities_final = capacities_final.drop_duplicates(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour"],
    keep="first"
).copy()

capacities_final = capacities_final.drop(columns=["source_file"])

capacities_final = capacities_final.sort_values(
    ["delivery_day", "hour", "from_zone_id", "to_zone_id"]
).reset_index(drop=True)

print("Vista previa final:")
print(capacities_final.head())

print(f"Filas totales a insertar tras deduplicar: {len(capacities_final)}")


# =========================
# BASIC CHECKS
# =========================
print("Rango de fechas:")
print(capacities_final["delivery_day"].min(), "->", capacities_final["delivery_day"].max())

print("Número de conexiones distintas:")
print(capacities_final["capacity_code"].nunique())

print("Conexiones detectadas:")
print(sorted(capacities_final["capacity_code"].unique())[:50])


# =========================
# INSERT INTO SQLITE
# =========================
capacities_final.to_sql(
    "Capacities",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.close()

print("Capacities insertadas correctamente.")