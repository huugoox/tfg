from numpy import average

from db_client import DbClient

# Initialize connection
db_client = DbClient()
db = db_client.db
collection = db["prices_nordpool"]

print("\n📊 --- DATABASE STATUS REPORT ---")
print("-" * 35)

# 1. Total count
total_records = collection.count_documents({})
print(f"Total records in database: {total_records}")

# 2. Aggregation: Group by area to see counts and average prices
# This shows you have data from multiple zones (NO1, NO2, etc.)
pipeline = [
    {
        "$group": {
            "_id": "$area", 
            "record_count": {"$sum": 1}, 
            #"avg_price": {"$avg": "$price"}
        }
    },
    {
        "$sort": {"_id": 1}  # Sort alphabetically
    }
]

print("\n📍 Breakdown by Area:")
results = list(collection.aggregate(pipeline))

if not results:
    print("No data found. Make sure you have run main.py first.")
else:
    for res in results:
        area_name = res['_id']
        count = res['record_count']
        # average = round(res['avg_price'], 2)
        # print(f" - Zone {area_name:5}: {count:6} records | Avg Price: {average:6} EUR/MWh")
        print(f" - Zone {area_name:5}: {count:6} records")

# 3. Time range check
if total_records > 0:
    first_doc = collection.find_one(sort=[("delivery_day", 1)])
    last_doc = collection.find_one(sort=[("delivery_day", -1)])
    print(f"\n📅 Data Period: from {first_doc['delivery_day']} to {last_doc['delivery_day']}")

print("-" * 35)
print("✅ Status check complete.")