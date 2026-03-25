from pymongo import MongoClient

class DbClient:
    def __init__(self, uri="mongodb://admin:password123@localhost:27018/?authSource=admin", db_name="tfg_database"):
        # This runs when the class is initialized: it connects us to MongoDB
        print("🔌 Connecting to the database...")
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
    
    def insert_prices(self, records):
        # This function receives the cleaned data and injects it into MongoDB
        if records:
            collection = self.db["prices_nordpool"]
            collection.insert_many(records)
            print(f"✅ Success! {len(records)} records have been saved to the database.")
        else:
            print("⚠️ No data to insert.")