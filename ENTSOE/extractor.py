import pandas as pd

class Extractor:
    def __init__(self, file_path):
        """
        Initializes the Extractor with the path to the ENTSO-E data file.
        """
        self.file_path = file_path

    def process_entsoe_file(self):
        """
        Reads, cleans, and transforms the raw Excel/CSV price data.
        Returns a list of dictionaries ready for MongoDB ingestion.
        """
        print(f"📂 Reading file {self.file_path}...")
        
        # Region mapping based on Nord Pool market structure
        # Baltic: Estonia, Lithuania, Latvia
        # CWE: Central Western Europe
        # Nordic: Scandinavian zones and Denmark
        region_map = {
            "EE": "Baltic", "LT": "Baltic", "LV": "Baltic",
            "AT": "CWE", "BE": "CWE", "FR": "CWE", "GER": "CWE", "NL": "CWE", "PL": "CWE",
            "DK1": "Nordic", "DK2": "Nordic", "FI": "Nordic", 
            "NO1": "Nordic", "NO2": "Nordic", "NO3": "Nordic", "NO4": "Nordic", "NO5": "Nordic",
            "SE1": "Nordic", "SE2": "Nordic", "SE3": "Nordic", "SE4": "Nordic"
        }
        
        # Determine file type and read data into a pandas DataFrame
        if self.file_path.endswith('.csv'):
            # sep=None allows pandas to automatically detect delimiters (comma, semicolon, etc.)
            df = pd.read_csv(self.file_path, sep=None, engine='python') 
        else:
            df = pd.read_excel(self.file_path)
        
        records = []
        print("⚙️ Processing and cleaning data with Region Mapping...")
        
        for index, row in df.iterrows():
            # 1. Clean MTU strings to avoid errors during Daylight Saving Time (DST) transitions.
            # We remove time zone suffixes like (CET) or (CEST).
            mtu = str(row['MTU (CET/CEST)']).replace("(CET)", "").replace("(CEST)", "").strip()
            
            # 2. SEQUENCE FILTER: Only accept "Sequence 1" (main auction).
            # This prevents duplicate records in countries with multiple auctions (AT, DE, FR).
            if 'Sequence' in df.columns:
                if "Sequence 2" in str(row['Sequence']):
                    continue

            # Check if the row contains a valid time range
            if "-" in mtu:
                try:
                    # Split the time range: "DD/MM/YYYY HH:MM - DD/MM/YYYY HH:MM"
                    start_str, end_str = mtu.split(" - ")
                    
                    # Extract date and start time from the first part
                    start_parts = start_str.strip().split(" ")
                    delivery_day = start_parts[0]
                    start_time = start_parts[1]
                    
                    # Extract end time from the second part
                    end_parts = end_str.strip().split(" ")
                    end_time = end_parts[1] if len(end_parts) > 1 else end_parts[0]
                    
                    # 3. AREA CLEANING & REGION ASSIGNMENT
                    # Clean the area name (e.g., "BZN|NO1" becomes "NO1")
                    raw_area = str(row['Area'])
                    area = raw_area.split("|")[1] if "|" in raw_area else raw_area
                    
                    # Assign the region from the map; default to "Other" if not found
                    region = region_map.get(area, "Other")
                    
                    # Target the Day-ahead price column
                    price = row['Day-ahead Price (EUR/MWh)']
                    
                    # 4. DATA PACKAGING
                    # Only append the record if the price value exists (not NaN)
                    if pd.notna(price):
                        document = {
                            "delivery_day": delivery_day,
                            "period_start": start_time,
                            "period_end": end_time,
                            "area": area,
                            "region": region,
                            "price": float(price)
                        }
                        records.append(document)

                except Exception as e:
                    # Log the error and skip the problematic row to keep the process running
                    print(f"⚠️ Warning: Row {index} skipped due to format: {mtu}")
                    continue
                    
        return records