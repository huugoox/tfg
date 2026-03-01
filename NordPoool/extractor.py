# DIARI NORDPOOL - EXTRACTOR DE PRECIOS
import pandas as pd
from pymongo import MongoClient

# --- 1. CONFIGURACIÓN ---
EXCEL_FILE = "auction_prices_Day-ahead_NO1,NO2,NO3,NO4,NO5_EUR_2026-02-23.xlsx" # <-- ¡Asegúrate de poner el nombre real de tu Excel!
DELIVERY_DAY = "2026-02-23" 

# --- 2. CONEXIÓN A LA BASE DE DATOS ---
print("Conectando a MongoDB...")
# ¡Fíjate que ahora usamos el puerto 27018 y el authSource!
client = MongoClient("mongodb://admin:password123@localhost:27018/?authSource=admin")
db = client["tfg_database"]
collection = db["prices_nordpool"]

# --- 3. EXTRACCIÓN (Tasca 2) ---
print(f"Leyendo el archivo {EXCEL_FILE}...")
df = pd.read_excel(EXCEL_FILE, skiprows=4)

# --- 4. TRANSFORMACIÓN E INGESTIÓN (Tasca 2) ---
records_to_insert = []

print("Procesando los datos...")
for index, row in df.iterrows():
    period = str(row['Delivery period (CET)'])
    
    if "-" in period:
        start_time, end_time = period.split(" - ")
        
        document = {
            "delivery_day": DELIVERY_DAY,
            "period_start": start_time.strip(),
            "period_end": end_time.strip(),
            "prices": {
                "NO1": float(row['NO1 (EUR)']),
                "NO2": float(row['NO2 (EUR)']),
                "NO3": float(row['NO3 (EUR)']),
                "NO4": float(row['NO4 (EUR)']),
                "NO5": float(row['NO5 (EUR)'])
            }
        }
        records_to_insert.append(document)

# Insertamos todos los documentos
if records_to_insert:
    collection.insert_many(records_to_insert)
    print(f"¡Éxito! Se han guardado {len(records_to_insert)} registros en tu base de datos.")
else:
    print("No se han encontrado datos. Revisa el formato del Excel.")