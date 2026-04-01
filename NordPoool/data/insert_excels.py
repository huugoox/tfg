from pathlib import Path
import sqlite3
import pandas as pd
import re


# =========================
# PATHS
# =========================
project_root = Path(r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool")
db_path = project_root / "data" / "thesis_database.db"
prices_root = project_root / "ExcelFilesNoProcessed" / "Prices"


# =========================
# READ PRICE FILE
# =========================
def read_price_file(file_path: Path) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=None)

    header_row = df[df.iloc[:, 0].astype(str).str.contains("Delivery period", na=False)].index[0]
    df.columns = df.iloc[header_row]
    df = df[(header_row + 1):].reset_index(drop=True)

    return df


# =========================
# EXTRACT DATE FROM FILENAME
# =========================
def extract_date_from_filename(file_path: Path) -> pd.Timestamp:
    match = re.search(r"(\d{4}-\d{2}-\d{2})\.xlsx$", file_path.name)
    if not match:
        raise ValueError(f"No se pudo extraer la fecha del archivo: {file_path.name}")
    return pd.to_datetime(match.group(1))


# =========================
# BUILD RAW DATAFRAME
# =========================
price_files = sorted(prices_root.rglob("*.xlsx"))

print(f"Archivos encontrados: {len(price_files)}")

prices_dfs = []

for file in price_files:
    try:
        df = read_price_file(file)
        df["delivery_day"] = extract_date_from_filename(file)
        df["source_file"] = file.name
        prices_dfs.append(df)
    except Exception as e:
        print(f"Error leyendo {file.name}: {e}")

if not prices_dfs:
    raise ValueError("No se ha podido leer ningún archivo de precios.")

prices_raw = pd.concat(prices_dfs, ignore_index=True)

print("Shape combinado:", prices_raw.shape)
print("Columnas originales:")
print(prices_raw.columns.tolist())


# =========================
# CLEAN COLUMNS
# =========================
prices_raw.columns = [str(col).strip() for col in prices_raw.columns]

cleaned_columns = []
for col in prices_raw.columns:
    col = str(col).strip()
    col = re.sub(r"\s*\(EUR\)\s*$", "", col)
    cleaned_columns.append(col)

prices_raw.columns = cleaned_columns

delivery_period_col = None
for col in prices_raw.columns:
    if "Delivery period" in col:
        delivery_period_col = col
        break

if delivery_period_col is None:
    raise ValueError("No se encontró la columna 'Delivery period'.")

prices_raw = prices_raw.rename(columns={delivery_period_col: "delivery_period"})


# =========================
# FILTER VALID HOURLY ROWS
# =========================
prices_raw["delivery_period"] = prices_raw["delivery_period"].astype(str).str.strip()

valid_period_mask = prices_raw["delivery_period"].str.match(
    r"^\d{2}:\d{2}\s*-\s*\d{2}:\d{2}$",
    na=False
)

invalid_periods = prices_raw.loc[~valid_period_mask, "delivery_period"].unique()
if len(invalid_periods) > 0:
    print("Delivery periods no válidos detectados y excluidos:")
    print(invalid_periods[:20])

prices_raw = prices_raw.loc[valid_period_mask].copy()


# =========================
# EXTRACT HOUR
# =========================
prices_raw["hour"] = prices_raw["delivery_period"].str.extract(r"^(\d{2}):")[0]
prices_raw["hour"] = pd.to_numeric(prices_raw["hour"], errors="coerce")

prices_raw = prices_raw.dropna(subset=["hour"]).copy()
prices_raw["hour"] = prices_raw["hour"].astype(int)


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


# =========================
# IDENTIFY ZONE COLUMNS
# =========================
zone_columns = [col for col in prices_raw.columns if col in valid_zone_codes]

print("Columnas de zonas detectadas:", zone_columns)

missing_expected = valid_zone_codes - set(zone_columns)
if missing_expected:
    print("Aviso, zonas en DB no encontradas en el dataframe:", sorted(missing_expected))


# =========================
# WIDE TO LONG
# =========================
prices_long = prices_raw.melt(
    id_vars=["delivery_day", "hour"],
    value_vars=zone_columns,
    var_name="zone_code",
    value_name="price_value"
)

prices_long["price_value"] = pd.to_numeric(prices_long["price_value"], errors="coerce")
prices_long["zone_id"] = prices_long["zone_code"].map(zone_map)


# =========================
# FINAL DATAFRAME
# =========================
prices_final = prices_long[["zone_id", "delivery_day", "hour", "price_value"]].copy()
prices_final = prices_final.dropna(subset=["zone_id", "delivery_day", "hour", "price_value"])

prices_final["delivery_day"] = pd.to_datetime(prices_final["delivery_day"]).dt.strftime("%Y-%m-%d")
prices_final["hour"] = prices_final["hour"].astype(int)


print(f"Filas a insertar antes de ordenar: {len(prices_final)}")

# Insertion is sorted like this to fit better with an event-based architecture later on
prices_final = prices_final.sort_values(
    ["delivery_day", "hour", "zone_id"]
).reset_index(drop=True)

print("Vista previa final:")
print(prices_final.head())
print(f"Filas totales a insertar: {len(prices_final)}")


# =========================
# INSERT INTO SQLITE
# =========================
prices_final.to_sql(
    "Prices",
    conn,
    if_exists="append",
    index=False,
    chunksize=10000
)

conn.close()

print("Prices insertados correctamente.")


