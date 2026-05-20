-- 1. Wipe the old table and start fresh
DROP TABLE IF EXISTS competitor_locations CASCADE;

-- 2. Create the table with the full schema (matching models.py)
CREATE TABLE competitor_locations (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    permit_type VARCHAR(100), -- 'Incineration', 'Landfill', 'Recycling', 'Storage'
    lat_dec_coord_num DOUBLE PRECISION NOT NULL,
    long_dec_coord_num DOUBLE PRECISION NOT NULL,
    county_name VARCHAR(100),
    swr_num VARCHAR(20),
    total_tons NUMERIC,
    suitability_score INTEGER -- 1 to 100
);

-- 3. Create a spatial index to keep the radius search fast for the demo
CREATE INDEX idx_comp_geo ON competitor_locations (lat_dec_coord_num, long_dec_coord_num);

-- 4. Insert rich sample data for major Texas regions
INSERT INTO competitor_locations 
(company_name, permit_type, lat_dec_coord_num, long_dec_coord_num, county_name, swr_num, total_tons, suitability_score)
VALUES 
-- HARRIS COUNTY (Houston Hub)
('Gulf Coast Recycling Solutions', 'Recycling', 29.7604, -95.3698, 'HARRIS', 'COMP001', 45000.50, 88),
('Bayou City Industrial Services', 'Storage', 29.7355, -95.2644, 'HARRIS', 'COMP002', 12500.00, 72),
('Ship Channel Environmental', 'Landfill', 29.7212, -95.1255, 'HARRIS', 'COMP003', 250000.00, 95),
('Pasadena Waste Recovery', 'Recycling', 29.6911, -95.2091, 'HARRIS', 'COMP004', 8500.00, 64),

-- JEFFERSON COUNTY (Beaumont/Port Arthur)
('Golden Triangle Disposal', 'Landfill', 30.0802, -94.1266, 'JEFFERSON', 'COMP005', 185000.75, 91),
('Sabine Pass Remediation', 'Incineration', 29.7915, -93.8895, 'JEFFERSON', 'COMP006', 42000.00, 85),
('Mid-County Resource Recovery', 'Recycling', 29.9850, -93.9910, 'JEFFERSON', 'COMP007', 15000.25, 78),

-- DALLAS / TARRANT COUNTY (North Texas)
('North Texas Waste Management', 'Landfill', 32.7767, -96.7970, 'DALLAS', 'COMP008', 300000.00, 98),
('Metroplex Recovery Corp', 'Recycling', 32.7555, -97.3308, 'TARRANT', 'COMP009', 55000.00, 82),
('Irving Industrial Disposal', 'Storage', 32.8140, -96.9489, 'DALLAS', 'COMP010', 9200.50, 55),

-- NUECES COUNTY (Corpus Christi)
('Coastal Bend Environmental', 'Landfill', 27.8006, -97.3964, 'NUECES', 'COMP011', 110000.00, 89),
('Refinery Row Services', 'Incineration', 27.8200, -97.4500, 'NUECES', 'COMP012', 38000.00, 76);

-- 5. Final check to ensure data is correct
SELECT company_name, county_name, total_tons, suitability_score FROM competitor_locations;