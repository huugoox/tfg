import pandas as pd

# Works for ENTSO-E price files
class Extractor:
    def __init__(self, file_path):
        self.file_path = file_path

    def process_entsoe_file(self):
        print(f"📂 Reading file {self.file_path}...")
        
        # Detect if the file is CSV or Excel
        if self.file_path.endswith('.csv'):
            # Using sep=None with the python engine allows pandas to guess the separator
            df = pd.read_csv(self.file_path, sep=None, engine='python') 
        else:
            df = pd.read_excel(self.file_path)
        
        records = []
        print("⚙️ Processing and cleaning data...")
        
        for index, row in df.iterrows():
            # Extract MTU and clean timezone suffixes to avoid split errors
            mtu = str(row['MTU (CET/CEST)']).replace("(CET)", "").replace("(CEST)", "").strip()
            
            if "-" in mtu:
                try:
                    # Split the time range: "DD/MM/YYYY HH:MM - DD/MM/YYYY HH:MM"
                    start_str, end_str = mtu.split(" - ")
                    
                    # Split date and time for start and end
                    start_parts = start_str.strip().split(" ")
                    delivery_day = start_parts[0]
                    start_time = start_parts[1]
                    
                    end_parts = end_str.strip().split(" ")
                    end_time = end_parts[1]
                    
                    # Clean the Area name (handle pipes if present)
                    raw_area = str(row['Area'])
                    area = raw_area.split("|")[1] if "|" in raw_area else raw_area
                    
                    # Target the specific price column
                    price = row['Day-ahead Price (EUR/MWh)']
                    
                    # Only append if price data is valid
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
                    # Skip problematic rows and continue
                    continue
                    
        return records