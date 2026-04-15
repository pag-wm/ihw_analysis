SELECT 
    f.re_phys_loc_addr_county, 
    COUNT(DISTINCT f.ref_num_txt) AS facility_count,
    ROUND(SUM(a.p_quantity_generated::numeric) / 2000, 2) AS total_tons_2024
FROM 
    annual_waste_summary as a
JOIN 
    facilities as f ON a.form_registration = f.additional_id_text
GROUP BY 
    f.re_phys_loc_addr_county
ORDER BY 
    total_tons_2024 DESC
LIMIT 10;