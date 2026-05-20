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
volumes_root = data_root / "Volumes"

if not db_path.exists():
    raise FileNotFoundError(f"No existe la base de datos: {db_path}")

if not volumes_root.exists():
    raise FileNotFoundError(f"No existe la carpeta de volumes: {volumes_root}")


# =========================
# EXTRACT DATE FROM FILENAME
# =========================
def extract_date_from_filename(file_path: Path) -> pd.Timestamp:
    match = re.search(r"(\d{4}-\d{2}-\d{2})_MW\.xlsx$", file_path.name)
    if not match:
        raise ValueError(f"No se pudo extraer la fecha del archivo: {file_path.name}")
    return pd.to_datetime(match.group(1))


# =========================
# READ VOLUME FILE
# =========================
def read_volume_file(file_path: Path, valid_zone_codes: set[str]) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=None)

    header_row = df[df.iloc[:, 0].astype(str).str.contains("Delivery period", na=False)].index[0]
    header_values = df.iloc[header_row].tolist()

    final_columns = []
    zone_counter = {}

    for i, value in enumerate(header_values):
        value_str = str(value).strip()

        if i == 0 and "Delivery period" in value_str:
            final_columns.append("delivery_period")
            continue

        if value_str not in valid_zone_codes:
            final_columns.append(f"unknown_{i}")
            continue

        zone_counter[value_str] = zone_counter.get(value_str, 0) + 1

        if zone_counter[value_str] == 1:
            final_columns.append(f"{value_str}_buy")
        elif zone_counter[value_str] == 2:
            final_columns.append(f"{value_str}_sell")
        else:
            final_columns.append(f"{value_str}_{zone_counter[value_str]}")

    df.columns = final_columns
    df = df[(header_row + 1):].reset_index(drop=True)

    return df


# =========================
# CONNECT TO DB AND GET ZONES
# =========================
conn = sqlite3.connect(db_path)

conn.execute("DELETE FROM Volumes")

try:
    conn.execute("DELETE FROM sqlite_sequence WHERE name='Volumes'")
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
# BUILD RAW DATAFRAME
# =========================
volume_files = sorted(volumes_root.rglob("*.xlsx"))

print(f"Archivos encontrados: {len(volume_files)}")

volumes_dfs = []

for file in volume_files:
    try:
        df = read_volume_file(file, valid_zone_codes)
        df["delivery_day"] = extract_date_from_filename(file)
        df["source_file"] = file.name
        volumes_dfs.append(df)
    except Exception as e:
        print(f"Error leyendo {file.name}: {e}")

if not volumes_dfs:
    raise ValueError("No se ha podido leer ningún archivo de volumes.")

volumes_raw = pd.concat(volumes_dfs, ignore_index=True)

print("Shape combinado:", volumes_raw.shape)
print("Columnas originales:")
print(volumes_raw.columns.tolist())


# =========================
# CLEAN COLUMNS
# =========================
volumes_raw.columns = [str(col).strip() for col in volumes_raw.columns]


# =========================
# FILTER VALID HOURLY ROWS
# =========================
volumes_raw["delivery_period"] = volumes_raw["delivery_period"].astype(str).str.strip()

valid_period_mask = volumes_raw["delivery_period"].str.match(
    r"^\d{2}:\d{2}\s*-\s*\d{2}:\d{2}$",
    na=False
)

invalid_periods = volumes_raw.loc[~valid_period_mask, "delivery_period"].unique()
if len(invalid_periods) > 0:
    print("Delivery periods no válidos detectados y excluidos:")
    print(invalid_periods[:20])

volumes_raw = volumes_raw.loc[valid_period_mask].copy()


# =========================
# EXTRACT HOUR
# =========================
volumes_raw["hour"] = volumes_raw["delivery_period"].str.extract(r"^(\d{2}):")[0]
volumes_raw["hour"] = pd.to_numeric(volumes_raw["hour"], errors="coerce")

volumes_raw = volumes_raw.dropna(subset=["hour"]).copy()
volumes_raw["hour"] = volumes_raw["hour"].astype(int)


# =========================
# ADD HOUR INSTANCE
# =========================
# Esto evita el producto cruzado en días con cambio horario
volumes_raw["hour_instance"] = (
    volumes_raw.groupby(["delivery_day", "hour"]).cumcount() + 1
)


# =========================
# IDENTIFY VOLUME COLUMNS
# =========================
buy_columns = []
sell_columns = []

for col in volumes_raw.columns:
    if col.endswith("_buy"):
        zone_code = col[:-4]
        if zone_code in valid_zone_codes:
            buy_columns.append(col)
    elif col.endswith("_sell"):
        zone_code = col[:-5]
        if zone_code in valid_zone_codes:
            sell_columns.append(col)

print("Columnas BUY detectadas:", buy_columns)
print("Columnas SELL detectadas:", sell_columns)

detected_zones = {col[:-4] for col in buy_columns} | {col[:-5] for col in sell_columns}
missing_expected = valid_zone_codes - detected_zones

if missing_expected:
    print("Aviso, zonas en DB no encontradas en el dataframe:", sorted(missing_expected))


# =========================
# MELT BUY
# =========================
buy_df = volumes_raw.melt(
    id_vars=["delivery_day", "hour", "hour_instance"],
    value_vars=buy_columns,
    var_name="zone_code",
    value_name="buy_volume_value"
)

buy_df["zone_code"] = buy_df["zone_code"].str.replace("_buy", "", regex=False)
buy_df["buy_volume_value"] = pd.to_numeric(buy_df["buy_volume_value"], errors="coerce")


# =========================
# MELT SELL
# =========================
sell_df = volumes_raw.melt(
    id_vars=["delivery_day", "hour", "hour_instance"],
    value_vars=sell_columns,
    var_name="zone_code",
    value_name="sell_volume_value"
)

sell_df["zone_code"] = sell_df["zone_code"].str.replace("_sell", "", regex=False)
sell_df["sell_volume_value"] = pd.to_numeric(sell_df["sell_volume_value"], errors="coerce")


# =========================
# MERGE BUY + SELL
# =========================
volumes_merged = pd.merge(
    buy_df,
    sell_df,
    on=["delivery_day", "hour", "hour_instance", "zone_code"],
    how="outer"
)

volumes_merged["zone_id"] = volumes_merged["zone_code"].map(zone_map)


# =========================
# FINAL DATAFRAME
# =========================
volumes_final = volumes_merged[
    ["zone_id", "delivery_day", "hour", "buy_volume_value", "sell_volume_value"]
].copy()

volumes_final = volumes_final.dropna(
    subset=["zone_id", "delivery_day", "hour"]
)

volumes_final["zone_id"] = volumes_final["zone_id"].astype(int)
volumes_final["delivery_day"] = pd.to_datetime(volumes_final["delivery_day"]).dt.strftime("%Y-%m-%d")
volumes_final["hour"] = volumes_final["hour"].astype(int)

print(f"Filas a insertar antes de ordenar: {len(volumes_final)}")

volumes_final = volumes_final.sort_values(
    ["delivery_day", "hour", "zone_id"]
).reset_index(drop=True)

print("Vista previa final:")
print(volumes_final.head())
print(f"Filas totales a insertar: {len(volumes_final)}")


# =========================
# INSERT INTO SQLITE
# =========================
volumes_final.to_sql(
    "Volumes",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.close()

print("Volumes insertados correctamente.")