# Nord Pool Electricity Market Database

This folder contains the SQLite database used for the Bachelor Thesis **Data-Efficient Electricity Price Forecasting Using Event-Based Market Representations**.

The database includes historical Nord Pool Day-Ahead market data used in the project, including electricity prices, volumes, flows and transmission capacities.

## Files

- `thesis_database.db` — SQLite database containing the collected Nord Pool market data.
- `README.md` — Instructions for accessing, understanding and updating the database.
- `requirements.txt` — Python dependencies required to run the data download scripts available in the GitHub repository.

The scripts used to download and update the database are available in the project GitHub repository:

https://github.com/huugoox/tfg

The data download scripts are not located in the main branch. They can be found in the `data` branch of the repository, under:

`NordPoool/data/Load from API`

## Database contents

The SQLite database contains the main Nord Pool Day-Ahead market data used in the project.

The main tables are:

- `BiddingZones` — mapping between the internal zone identifiers and the Nord Pool bidding-zone codes.
- `Prices` — Day-Ahead electricity prices.
- `Volumes` — Day-Ahead buy and sell volumes.
- `Flows` — electricity flows between bidding zones.
- `Capacities` — transmission capacities between bidding zones.

The available historical coverage differs between tables:

- `Prices`: from **2000-01-01** to **2026-09-09**
- `Volumes`: from **2015-01-01** to **2026-09-09**
- `Flows`: from **2015-01-01** to **2026-09-09**
- `Capacities`: from **2015-01-01** to **2026-09-09**

The tables use internal zone identifiers such as `zone_id`, `from_zone_id` and `to_zone_id`. These identifiers can be matched with the corresponding Nord Pool area codes through the `BiddingZones` table.

The bidding zones included in this database were selected to ensure consistency with the scope and requirements of this project.

Nord Pool also provides data for additional bidding zones that were not required for this work. These areas may nevertheless be useful for other applications and can be accessed through the Nord Pool Data API.

## Table structure

### BiddingZones

- `zone_id` — internal identifier used in the database.
- `zone_code` — Nord Pool bidding-zone code, such as `NO1`, `SE3` or `DK1`.

### Prices

- `zone_id` — bidding-zone identifier.
- `delivery_day` — delivery date.
- `hour` — delivery hour.
- `price_value` — Day-Ahead electricity price.

### Volumes

- `zone_id` — bidding-zone identifier.
- `delivery_day` — delivery date.
- `hour` — delivery hour.
- `buy_volume_value` — Day-Ahead buy volume.
- `sell_volume_value` — Day-Ahead sell volume.

### Flows

- `from_zone_id` — origin bidding zone.
- `to_zone_id` — destination bidding zone.
- `delivery_day` — delivery date.
- `hour` — delivery hour.
- `flow_value` — electricity flow from the origin zone to the destination zone.

### Capacities

- `capacity_code` — connection identifier in the format `FROM->TO`.
- `from_zone_id` — origin bidding zone.
- `to_zone_id` — destination bidding zone.
- `delivery_day` — delivery date.
- `hour` — delivery hour.
- `capacity_value` — transmission capacity from the origin zone to the destination zone.

## How to open the database with DBeaver

The database is stored in the file:

`thesis_database.db`

To open it with DBeaver:

1. Open DBeaver.
2. Go to **Database > New Database Connection**.
3. Select **SQLite**.
4. Select the file `thesis_database.db`.
5. Click **Finish** to create the connection.
6. In the left panel, expand the connection and open **Tables**.
7. To inspect a table, right-click it and select **View Data > All Rows**.

SQL queries can also be executed using the DBeaver SQL Editor.

### Example queries

Show the first 100 price records:

```sql
SELECT *
FROM Prices
LIMIT 100;
```

```sql
SELECT
    MIN(delivery_day) AS first_date,
    MAX(delivery_day) AS last_date
FROM Prices;
```
```sql
SELECT
    p.delivery_day,
    p.hour,
    b.zone_code,
    p.price_value
FROM Prices p
JOIN BiddingZones b
    ON p.zone_id = b.zone_id
ORDER BY p.delivery_day, p.hour, b.zone_code;
```

## Downloading additional Nord Pool data

Additional Nord Pool Day-Ahead data can be downloaded using the scripts available in the project GitHub repository mentioned above in the **Files** section.

The available loaders are:

- `load_prices_api.py` — downloads Day-Ahead prices.
- `load_volumes_api.py` — downloads Day-Ahead buy and sell volumes.
- `load_flows_api.py` — downloads flows between bidding zones.
- `load_capacities_api.py` — downloads transmission capacities between bidding zones.

The scripts insert the downloaded data directly into the corresponding tables of `thesis_database.db`.

### Nord Pool API access

Valid Nord Pool Data API credentials are required to download additional data.

For security reasons, the credentials are not stored in the scripts or in the repository.

The scripts read the following environment variables:

`NORDPOOL_USERNAME`

`NORDPOOL_PASSWORD`

In Windows PowerShell, they can be configured for the current session with:

```powershell
$env:NORDPOOL_USERNAME="your_username"
$env:NORDPOOL_PASSWORD="your_password"
```

After setting the credentials, the desired loader can be executed from PowerShell, for example:

```powershell
python load_prices_api.py
```

The same procedure can be used for the other loaders:

```powershell
python load_volumes_api.py
python load_flows_api.py
python load_capacities_api.py
```

### Selecting the download period

The date range to be downloaded can be configured directly inside each loader script using:

```python
START_DATE = date(2000, 1, 1)
END_DATE = date(2026, 9, 9)
```

These values can be modified according to the period that needs to be downloaded.

For example, to download only data from 2025:

```python
START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 12, 31)
```

### Resuming interrupted downloads

Each loader includes a resume option:

```python
RESUME = True
```

When `RESUME` is set to `True`, the script uses its corresponding checkpoint file and continues from the day after the last successfully processed date.

This allows long downloads to be resumed if the process is interrupted.

For example:

```text
Last processed date: 2014-08-15
Next execution starts from: 2014-08-16
```

If a specific period needs to be downloaded again, `RESUME` can temporarily be set to:

```python
RESUME = False
```

In that case, the script will use the dates defined in `START_DATE` and `END_DATE` without using the checkpoint.

Each data type uses its own checkpoint file, so prices, volumes, flows and capacities can be resumed independently.

## Requirements

Python 3 is required to run the data download scripts.

The required external packages are listed in `requirements.txt`.

They can be installed from PowerShell using:

```powershell
pip install -r requirements.txt
```

The main external dependencies are:

- `pandas`
- `requests`

SQLite support is included in Python through the standard `sqlite3` library, so no additional SQLite package is required.