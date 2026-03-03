import pandas as pd

class Extractor:
    def __init__(self, file_path):
        self.file_path = file_path

    def process_entsoe_file(self):
        print(f"📂 Reading file {self.file_path}...")
        
        if self.file_path.endswith('.csv'):
            df = pd.read_csv(self.file_path, sep=None, engine='python') 
        else:
            df = pd.read_excel(self.file_path)
        
        records = []
        print("⚙️ Processing and cleaning data...")
        
        for index, row in df.iterrows():
            # 1. Limpieza de MTU para evitar errores en cambios de hora (DST)
            mtu = str(row['MTU (CET/CEST)']).replace("(CET)", "").replace("(CEST)", "").strip()
            
            # 2. FILTRO CRÍTICO: Solo aceptamos Sequence 1 (Mercado principal)
            # Esto evita duplicados en Austria (AT), Alemania (DE) y Francia (FR)
            if 'Sequence' in df.columns:
                if "Sequence 2" in str(row['Sequence']):
                    continue

            if "-" in mtu:
                try:
                    start_str, end_str = mtu.split(" - ")
                    
                    start_parts = start_str.strip().split(" ")
                    delivery_day = start_parts[0]
                    start_time = start_parts[1]
                    
                    # Manejo de seguridad para el split de la hora final
                    end_parts = end_str.strip().split(" ")
                    end_time = end_parts[1] if len(end_parts) > 1 else end_parts[0]
                    
                    raw_area = str(row['Area'])
                    area = raw_area.split("|")[1] if "|" in raw_area else raw_area
                    
                    price = row['Day-ahead Price (EUR/MWh)']
                    
                    if pd.notna(price):
                        document = {
                            "delivery_day": delivery_day,
                            "period_start": start_time,
                            "period_end": end_time,
                            "area": area,
                            "price": float(price)
                        }
                        records.append(document)

                except Exception as e:
                    # Si algo falla, imprimimos el error para saber qué fila es, 
                    # pero el programa no se detiene.
                    print(f"⚠️ Warning: Row {index} skipped due to format: {mtu}")
                    continue
                    
        return records