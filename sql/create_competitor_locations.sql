CREATE TABLE competitor_locations (
    comp_id SERIAL PRIMARY KEY,
    comp_name VARCHAR(255),
    comp_type VARCHAR(100), -- 'Incineration', 'Landfill', 'Recycling', 'Storage'
    latitude NUMERIC,
    longitude NUMERIC,
    swr_num VARCHAR(20)
);

-- Seeding with major Texas commercial incumbents
INSERT INTO competitor_locations (comp_name, comp_type, latitude, longitude, swr_num)
VALUES 
('Veolia ES Technical Solutions', 'Incineration/Disposal', 29.851, -93.985, '50212'),
('Clean Harbors Deer Park', 'Incineration', 29.722, -95.123, '50089'),
('Safety-Kleen Systems (Houston)', 'Solvent Recycling', 29.805, -95.335, '31043'),
('Waste Management (Skyline)', 'Landfill', 32.658, -96.657, '30048'),
('US Ecology (Texas)', 'Landfill/Treatment', 27.675, -97.746, '50052'),
('ExxonMobil Advanced Recycling', 'Advanced Recycling', 29.736, -95.011, '30812');