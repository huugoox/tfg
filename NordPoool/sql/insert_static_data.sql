INSERT INTO Regions (region_name) VALUES
('Baltic'),
('Nordic'),

-- DELETE FROM sqlite_sequence WHERE name='BiddingZones'; Reset auto-increment for BiddingZones
INSERT INTO BiddingZones (zone_code, country, region_id) VALUES
('EE', 'Estonia', 1),
('LT', 'Lithuania', 1),
('LV', 'Latvia', 1),
('DK1', 'Denmark', 2),
('DK2', 'Denmark', 2),
('FI', 'Finland', 2),
('NO1', 'Norway', 2),
('NO2', 'Norway', 2),
('NO3', 'Norway', 2),
('NO4', 'Norway', 2),
('NO5', 'Norway', 2),
('SE1', 'Sweden', 2),
('SE2', 'Sweden', 2),
('SE3', 'Sweden', 2),
('SE4', 'Sweden', 2);
