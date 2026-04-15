CREATE TABLE texas_logistics_hubs (
    hub_id SERIAL PRIMARY KEY,
    hub_name VARCHAR(255),
    hub_type VARCHAR(50), -- 'Rail Head', 'Interstate Junction', 'Port'
    latitude NUMERIC,
    longitude NUMERIC,
    is_hazmat_certified BOOLEAN DEFAULT TRUE
);

-- Example Insert based on 2026 infrastructure
INSERT INTO texas_logistics_hubs (hub_name, hub_type, latitude, longitude)
VALUES 
('Port Houston Barbours Cut', 'Port', 29.68, -95.00),
('Midlothian RailPort', 'Rail Head', 32.48, -97.03),
('I-10 & I-610 Interchange (Houston)', 'Interstate Junction', 29.77, -95.28),
('Alliance Fort Worth (BNSF Hub)', 'Rail Head', 32.96, -97.31);