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
flows_root = data_root / "Flows"

if not db_path.exists():
    raise FileNotFoundError(f"No existe la base de datos: {db_path}")

if not flows_root.exists():
    raise FileNotFoundError(f"No existe la carpeta de flows: {flows_root}")


# =========================
# READ FLOW FILE
# =========================
def read_flow_file(file_path: Path) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=None)

    header_candidates = df[df.iloc[:, 0].astype(str).str.contains("Delivery period", na=False)].index
    if len(header_candidates) == 0:
        raise ValueError(f"No se encontró la fila de cabecera con 'Delivery period' en {file_path.name}")

    header_row = header_candidates[0]
    df.columns = df.iloc[header_row]
    df = df[(header_row + 1):].reset_index(drop=True)

    return df


# =========================
# EXTRACT DATE FROM FILENAME
# =========================
def extract_date_from_filename(file_path: Path) -> pd.Timestamp:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
    if not match:
        raise ValueError(f"No se pudo extraer la fecha del archivo: {file_path.name}")
    return pd.to_datetime(match.group(1))


# =========================
# PARSE FLOW COLUMN
# =========================
def parse_flow_column(col_name: str):
    """
    Convierte una columna tipo:
    'NO1 -> NO2 (MW)'
    en:
    ('NO1', 'NO2')
    """
    col_name = str(col_name).strip()
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
flow_files = sorted(flows_root.rglob("*.xlsx"))

print(f"Archivos encontrados: {len(flow_files)}")

flows_dfs = []

for file in flow_files:
    try:
        df = read_flow_file(file)
        df["delivery_day"] = extract_date_from_filename(file)
        df["source_file"] = file.name
        flows_dfs.append(df)
    except Exception as e:
        print(f"Error leyendo {file.name}: {e}")

if not flows_dfs:
    raise ValueError("No se ha podido leer ningún archivo de flows.")

flows_raw = pd.concat(flows_dfs, ignore_index=True)

print("Shape combinado:", flows_raw.shape)
print("Columnas originales:")
print(flows_raw.columns.tolist())


# =========================
# CLEAN COLUMNS
# =========================
flows_raw.columns = [str(col).strip() for col in flows_raw.columns]

delivery_period_col = None
for col in flows_raw.columns:
    if "Delivery period" in col:
        delivery_period_col = col
        break

if delivery_period_col is None:
    raise ValueError("No se encontró la columna 'Delivery period'.")

flows_raw = flows_raw.rename(columns={delivery_period_col: "delivery_period"})


# =========================
# FILTER VALID HOURLY ROWS
# =========================
flows_raw["delivery_period"] = flows_raw["delivery_period"].astype(str).str.strip()

valid_period_mask = flows_raw["delivery_period"].str.match(
    r"^\d{2}:\d{2}\s*-\s*\d{2}:\d{2}$",
    na=False
)

invalid_periods = flows_raw.loc[~valid_period_mask, "delivery_period"].unique()
if len(invalid_periods) > 0:
    print("Delivery periods no válidos detectados y excluidos:")
    print(invalid_periods[:20])

flows_raw = flows_raw.loc[valid_period_mask].copy()


# =========================
# EXTRACT HOUR
# =========================
flows_raw["hour"] = flows_raw["delivery_period"].str.extract(r"^(\d{2}):")[0]
flows_raw["hour"] = pd.to_numeric(flows_raw["hour"], errors="coerce")

flows_raw = flows_raw.dropna(subset=["hour"]).copy()
flows_raw["hour"] = flows_raw["hour"].astype(int)


# =========================
# CONNECT TO DB AND GET ZONES
# =========================
conn = sqlite3.connect(db_path)

conn.execute("DELETE FROM Flows")

try:
    conn.execute("DELETE FROM sqlite_sequence WHERE name='Flows'")
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
# IDENTIFY FLOW COLUMNS
# =========================
flow_columns = []
flow_column_map = {}

for col in flows_raw.columns:
    if col in ["delivery_period", "delivery_day", "source_file", "hour"]:
        continue

    parsed = parse_flow_column(col)
    if parsed is None:
        continue

    from_zone, to_zone = parsed
    flow_columns.append(col)
    flow_column_map[col] = (from_zone, to_zone)

print("Columnas de flows detectadas:")
print(flow_columns[:20])
print(f"Total columnas de flows detectadas: {len(flow_columns)}")

if not flow_columns:
    raise ValueError("No se detectó ninguna columna de flujo con formato 'ZONE1 -> ZONE2 (MW)'.")


# =========================
# WIDE TO LONG
# =========================
flows_long = flows_raw.melt(
    id_vars=["delivery_day", "hour"],
    value_vars=flow_columns,
    var_name="flow_direction",
    value_name="flow_value"
)

flows_long["from_zone_code"] = flows_long["flow_direction"].map(lambda x: flow_column_map[x][0])
flows_long["to_zone_code"] = flows_long["flow_direction"].map(lambda x: flow_column_map[x][1])

flows_long["flow_value"] = (
    flows_long["flow_value"]
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.strip()
)

flows_long["flow_value"] = pd.to_numeric(flows_long["flow_value"], errors="coerce")

flows_long["from_zone_id"] = flows_long["from_zone_code"].map(zone_map)
flows_long["to_zone_id"] = flows_long["to_zone_code"].map(zone_map)

missing_from = flows_long.loc[flows_long["from_zone_id"].isna(), "from_zone_code"].dropna().unique()
missing_to = flows_long.loc[flows_long["to_zone_id"].isna(), "to_zone_code"].dropna().unique()

if len(missing_from) > 0:
    print("Aviso, zonas origen no encontradas en DB:", sorted(missing_from))

if len(missing_to) > 0:
    print("Aviso, zonas destino no encontradas en DB:", sorted(missing_to))


# =========================
# FINAL DATAFRAME
# =========================
flows_final = flows_long[
    ["from_zone_id", "to_zone_id", "delivery_day", "hour", "flow_value"]
].copy()

flows_final = flows_final.dropna(
    subset=["from_zone_id", "to_zone_id", "delivery_day", "hour", "flow_value"]
)

flows_final["from_zone_id"] = flows_final["from_zone_id"].astype(int)
flows_final["to_zone_id"] = flows_final["to_zone_id"].astype(int)
flows_final["delivery_day"] = pd.to_datetime(flows_final["delivery_day"]).dt.strftime("%Y-%m-%d")
flows_final["hour"] = flows_final["hour"].astype(int)

print(f"Filas a insertar antes de ordenar: {len(flows_final)}")

flows_final = flows_final.sort_values(
    ["delivery_day", "hour", "from_zone_id", "to_zone_id"]
).reset_index(drop=True)

print("Vista previa final:")
print(flows_final.head())
print(f"Filas totales a insertar: {len(flows_final)}")


# =========================
# INSERT INTO SQLITE
# =========================
flows_final.to_sql(
    "Flows",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.close()

print("Flows insertados correctamente.")