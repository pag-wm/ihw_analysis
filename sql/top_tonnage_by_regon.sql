SELECT 
    CASE 
        WHEN f.site_county_name IN ('HARRIS', 'GALVESTON', 'BRAZORIA', 'CHAMBERS') THEN 'Houston Area'
        WHEN f.site_county_name IN ('JEFFERSON', 'ORANGE', 'HARDIN') THEN 'Beaumont/Port Arthur'
        WHEN f.site_county_name IN ('NUECES', 'SAN PATRICIO', 'KLEBERG') THEN 'Corpus Christi'
        WHEN f.site_county_name IN ('DALLAS', 'TARRANT', 'COLLIN', 'DENTON') THEN 'DFW Metroplex'
        WHEN f.site_county_name IN ('MIDLAND', 'ECTOR', 'HOWARD') THEN 'Permian Basin'
        ELSE 'Other/Rural Texas'
    END AS industrial_region,
    COUNT(DISTINCT f.swr_num_txt) AS facility_count,
    ROUND(SUM(a.p_quantity_generated::numeric) / 2000, 2) AS total_tons_2024
FROM 
    annual_waste_summary a
JOIN 
    nor_facilities f ON a.form_registration = f.swr_num_txt
GROUP BY 
    industrial_region
ORDER BY 
    total_tons_2024 DESC;