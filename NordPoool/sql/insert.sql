INSERT INTO Regions (region_name) VALUES
('Baltic'),
('CWE'),
('Nordic'),

-- DELETE FROM sqlite_sequence WHERE name='BiddingZones'; Reset auto-increment for BiddingZones
INSERT INTO BiddingZones (zone_code, country, region_id) VALUES
('EE', 'Estonia', 1),
('LT', 'Lithuania', 1),
('LV', 'Latvia', 1),
('AT', 'Austria', 2),
('BE', 'Belgium', 2),
('FR', 'France', 2),
('GER', 'Germany', 2),
('NL', 'Netherlands', 2),
('DK1', 'Denmark', 3),
('DK2', 'Denmark', 3),
('FI', 'Finland', 3),
('NO1', 'Norway', 3),
('NO2', 'Norway', 3),
('NO3', 'Norway', 3),
('NO4', 'Norway', 3),
('NO5', 'Norway', 3),
('SE1', 'Sweden', 3),
('SE2', 'Sweden', 3),
('SE3', 'Sweden', 3),
('SE4', 'Sweden', 3);

-- SQL QUERYS TO INSERT DATA INTO THE PRICE TABLE
-- 1. Row number
SELECT COUNT(*) FROM Prices;

-- 2. Visual 
SELECT *
FROM Prices
ORDER BY delivery_day, hour, zone_id
LIMIT 50;

-- 3. Null values
SELECT COUNT(*)
FROM Prices
WHERE price_value IS NULL;

--4. Out of range values (example: negative prices)
SELECT DISTINCT hour
FROM Prices
ORDER BY hour;

--5. Duplicates (example: check for duplicate entries for the same zone, day, and hour) IMPORTANT: Because we don't have unique
-- Should be 1 per year per bidding zone
SELECT zone_id, delivery_day, hour, COUNT(*) as cnt
FROM Prices
GROUP BY zone_id, delivery_day, hour
HAVING cnt > 1
ORDER BY cnt DESC;

--6. Range date
SELECT 
    MIN(delivery_day) AS start_date,
    MAX(delivery_day) AS end_date
FROM Prices;

--7. Missing dates
SELECT delivery_day, COUNT(*) as n
FROM Prices
GROUP BY delivery_day
ORDER BY delivery_day;
