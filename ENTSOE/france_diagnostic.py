from ENTSOE.db_client import DbClient
import pandas as pd

db = DbClient().db
collection = db["prices_nordpool"]

pipeline = [
    {"$match": {"area": "FR"}},
    {"$group": {
        "_id": "$delivery_day",
        "count": {"$sum": 1}
    }},
    {"$match": {"count": {"$gt": 96}}}, 
    {"$sort": {"_id": 1}}
]

duplicates = list(collection.aggregate(pipeline))

if duplicates:
    print(f"🔎 Found {len(duplicates)} days with duplicate records in France.")
    for d in duplicates[:]:
        print(f"📅 Date {d['_id']} has {d['count']} records (should be 96).")
else:
    print("✅ No duplicates found per day. France might have a different resolution.")