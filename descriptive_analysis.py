import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pymongo import MongoClient
import os

# 1. SETUP FOLDER
# Creem la carpeta 'analysis' si no existeix per mantenir l'ordre
output_folder = "analysis"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"📁 Created folder: {output_folder}")

# 2. DATA EXTRACTION
print("🔌 Connecting to MongoDB and fetching data...")
client = MongoClient("mongodb://admin:password123@localhost:27018/")
db = client["tfg_database"]
collection = db["prices_nordpool"]

# Extract all records to a DataFrame
data = list(collection.find({}, {"_id": 0}))
df = pd.DataFrame(data)

# 3. DATA CLEANING & TRANSFORMATION
print("🧹 Cleaning and transforming data...")
# Unifiquem data i hora en un sol objecte datetime
df['datetime'] = pd.to_datetime(df['delivery_day'] + ' ' + df['period_start'], dayfirst=True)
df = df.sort_values(by=['area', 'datetime'])

# Extraiem característiques temporals per a l'anàlisi
df['hour'] = df['datetime'].dt.hour
df['month'] = df['datetime'].dt.month
df['weekday'] = df['datetime'].dt.weekday

# 4. NULL VALUES ANALYSIS
print("❓ Checking for null values...")
null_report = df.isnull().sum().to_frame(name='null_count')
null_report['percentage'] = (null_report['null_count'] / len(df)) * 100
null_report.to_csv(os.path.join(output_folder, 'null_values_report.csv'))

# 5. BASIC METRICS PER AREA/REGION
print("📊 Calculating basic metrics...")
stats_report = df.groupby(['region', 'area'])['price'].describe()
stats_report.to_csv(os.path.join(output_folder, 'descriptive_stats_per_area.csv'))

# 6. OUTLIER DETECTION (IQR Method)
print("🚩 Detecting outliers...")
def detect_outliers_iqr(group):
    Q1 = group.quantile(0.25)
    Q3 = group.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return ((group < lower_bound) | (group > upper_bound)).sum()

outliers_count = df.groupby('area')['price'].apply(detect_outliers_iqr).reset_index()
outliers_count.columns = ['area', 'outlier_count']
outliers_count.to_csv(os.path.join(output_folder, 'outliers_report.csv'))

# 7. VISUALIZATIONS (PNGs inside 'analysis' folder)
print("📈 Generating plots inside 'analysis' folder...")

# Plot 1: Daily Mean Price Trend
daily_mean = df.groupby(df['datetime'].dt.date)['price'].mean()
plt.figure(figsize=(12, 6))
plt.plot(daily_mean.index, daily_mean.values, label='Daily Average', alpha=0.5)
plt.plot(daily_mean.rolling(window=7).mean(), label='7-Day Moving Average', color='red', linewidth=2)
plt.title('Electricity Price Trend (All Areas)')
plt.ylabel('Price (EUR/MWh)')
plt.legend()
plt.savefig(os.path.join(output_folder, 'price_trend.png'))
plt.close() # Tanquem la figura per alliberar memòria

# Plot 2: Hourly Seasonality
hourly_seasonality = df.groupby('hour')['price'].mean()
plt.figure(figsize=(10, 5))
sns.barplot(x=hourly_seasonality.index, y=hourly_seasonality.values, palette="viridis")
plt.title('Intraday Seasonality: Average Price per Hour')
plt.ylabel('Average Price (EUR/MWh)')
plt.xlabel('Hour of the Day')
plt.savefig(os.path.join(output_folder, 'hourly_seasonality.png'))
plt.close()

# Plot 3: Monthly Seasonality
monthly_seasonality = df.groupby('month')['price'].mean()
plt.figure(figsize=(10, 5))
plt.plot(monthly_seasonality.index, monthly_seasonality.values, marker='o', color='green')
plt.title('Monthly Seasonality: Average Price per Month')
plt.xticks(range(1, 13))
plt.ylabel('Average Price (EUR/MWh)')
plt.grid(True, linestyle='--', alpha=0.7)
plt.savefig(os.path.join(output_folder, 'monthly_seasonality.png'))
plt.close()

print(f"✅ Analysis complete! All files saved in: {os.path.abspath(output_folder)}")