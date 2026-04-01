PRAGMA foreign_keys = ON;

CREATE TABLE Regions (
    region_id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_name TEXT NOT NULL UNIQUE
);

CREATE TABLE BiddingZones (
    zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_code TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    region_id INTEGER NOT NULL,
    FOREIGN KEY (region_id) REFERENCES Regions(region_id)
);

CREATE TABLE Prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    delivery_day DATE NOT NULL,
    hour INTEGER NOT NULL,
    price_value REAL NOT NULL,
    FOREIGN KEY (zone_id) REFERENCES BiddingZones(zone_id)
    -- UNIQUE (zone_id, delivery_day, hour) 
    --This allow us to ensure uniqueness of price entries for each zone, day, and hour, preventing duplicates
    -- but we won't add it because there one day that we have two different prices for the same zone, day, and hour because we delayed the hour
);

CREATE TABLE Volumes (
    volume_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    delivery_day DATE NOT NULL,
    hour INTEGER NOT NULL,
    buy_volume_value REAL,
    sell_volume_value REAL,
    FOREIGN KEY (zone_id) REFERENCES BiddingZones(zone_id)
    -- UNIQUE (zone_id, delivery_day, hour)
);

CREATE TABLE Flows (
    flow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_zone_id INTEGER NOT NULL,
    to_zone_id INTEGER NOT NULL,
    delivery_day DATE NOT NULL,
    hour INTEGER NOT NULL,
    flow_value REAL NOT NULL,
    FOREIGN KEY (from_zone_id) REFERENCES BiddingZones(zone_id),
    FOREIGN KEY (to_zone_id) REFERENCES BiddingZones(zone_id)
    -- UNIQUE (from_zone_id, to_zone_id, delivery_day, hour)
);

CREATE TABLE Capacities (
    capacity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    capacity_code TEXT,
    from_zone_id INTEGER NOT NULL,
    to_zone_id INTEGER NOT NULL,
    delivery_day DATE NOT NULL,
    hour INTEGER NOT NULL,
    capacity_value REAL NOT NULL,
    FOREIGN KEY (from_zone_id) REFERENCES BiddingZones(zone_id),
    FOREIGN KEY (to_zone_id) REFERENCES BiddingZones(zone_id)
    -- UNIQUE (from_zone_id, to_zone_id, delivery_day, hour)
);