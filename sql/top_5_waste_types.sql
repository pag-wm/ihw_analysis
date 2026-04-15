SELECT 
    w.wst_desc_txt,
    ROUND(SUM(a.p_quantity_generated::numeric) / 2000, 2) AS total_tons,
    COUNT(DISTINCT a.form_registration) AS facility_count
FROM 
    annual_waste_summary as a
JOIN 
    nor_facilities as f ON a.form_registration = f.swr_num_txt
JOIN 
    waste_lookup as w ON a.form_registration = w.swr_num_txt 
    AND a.waste_code = w.tx_wst_cd
WHERE 
    f.site_county_name IN ('HARRIS', 'GALVESTON', 'BRAZORIA', 'CHAMBERS')
GROUP BY 
    w.wst_desc_txt
ORDER BY 
    total_tons DESC
LIMIT 5;