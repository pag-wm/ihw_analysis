CREATE TABLE texas_land_values (
    region_id SERIAL PRIMARY KEY,
    region_name VARCHAR(100),
    avg_price_per_acre NUMERIC,
    suitability_bonus INT, -- 0 to 100 (Higher is cheaper)
    counties_included TEXT -- For reference
);

INSERT INTO texas_land_values (region_name, avg_price_per_acre, suitability_bonus, counties_included)
VALUES 
('Gulf Coast', 11502, 15, 'Harris, Galveston, Brazoria, Chambers, Jefferson'),
('Northeast', 9313, 30, 'Dallas, Tarrant, Collin, Denton'),
('Central Texas', 7911, 45, 'Travis, Williamson, Hays, Bexar'),
('South Texas', 6107, 60, 'Nueces, Webb, Hidalgo'),
('West Texas', 2878, 85, 'Midland, Ector, Howard'),
('Panhandle', 1832, 100, 'Potter, Randall, Lubbock');