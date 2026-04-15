-- This query sums all tonnage from facilities within 50 miles of the target coordinates
SELECT 
    SUM(a.p_quantity_generated::numeric) / 2000 as total_shed_tons,
    COUNT(DISTINCT f.swr_num_txt) as generator_count
FROM nor_facilities as f
JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
WHERE 
    (3959 * acos(cos(radians(:target_lat)) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians(:target_lon)) + 
    sin(radians(:target_lat)) * sin(radians(f.lat_dec_coord_num)))) <= 50;