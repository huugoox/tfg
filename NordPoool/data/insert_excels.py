from pathlib import Path
import sqlite3
import pandas as pd


# --- Paths ---
project_root = Path(__file__).resolve().parent / "thesis_database.db"
excel_path = project_root / "ExcelFilesNoProcessed" / "Prices" / "2020" / "NordPoool/ExcelFilesNoProcessed/Prices/2020/auction_prices_Day-ahead_EE,LT,LV,AT,BE,FR,GER,NL,PL,DK1,DK2,FI,NO1,NO2,NO3,NO4,NO5,SE1,SE2,SE3,SE4_EUR_2020-01-01.xlsx"  # ajusta esta ruta


# --- Connect to DB ---
conn = sqlite3.connect(db_path)

# 1. Read bidding zones from DB
zones_df = pd.read_sql_query(
    "SELECT zone_id, zone_code FROM BiddingZones",
    conn
)
zone_map = dict(zip(zones_df["zone_code"], zones_df["zone_id"]))

# 2. Read Excel
df = pd.read_excel(excel_path)

print("Columnas originales:", df.columns.tolist())

# 3. Example expected columns:
#    - delivery_day
#    - hour
#    - zone columns like EE, LT, LV, AT...
#
# If your file still has 'Delivery period (CET)', you must derive day/hour first.
# For now, we assume delivery_day and hour already exist.

id_vars = ["delivery_day", "hour"]
zone_columns = [col for col in df.columns if col in zone_map.keys()]

prices_long = df.melt(
    id_vars=id_vars,
    value_vars=zone_columns,
    var_name="zone_code",
    value_name="price_value"
)

# 4. Map zone_code -> zone_id
prices_long["zone_id"] = prices_long["zone_code"].map(zone_map)

# 5. Keep final columns
prices_final = prices_long[["zone_id", "delivery_day", "hour", "price_value"]].copy()

# Optional: remove nulls
prices_final = prices_final.dropna(subset=["zone_id", "delivery_day", "hour", "price_value"])

print(prices_final.head())
print(f"Filas a insertar: {len(prices_final)}")

# 6. Insert into SQLite
prices_final.to_sql("Prices", conn, if_exists="append", index=False)

conn.close()

print("Inserción de prueba completada.")