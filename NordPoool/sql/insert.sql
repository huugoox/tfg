INSERT INTO Regions (region_name) VALUES
('Baltic'),
('CWE'),
('Nordic'),

INSERT INTO BiddingZones (zone_code, country, region_id) VALUES

-- Baltic (region_id = 1)
('EE', 'Estonia', 1),
('LT', 'Lithuania', 1),
('LV', 'Latvia', 1),

-- CWE (region_id = 2)
('AT', 'Austria', 2),
('BE', 'Belgium', 2),
('FR', 'France', 2),
('GER', 'Germany', 2),
('NL', 'Netherlands', 2),
('PL', 'Poland', 2),

-- Nordic (region_id = 3)
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