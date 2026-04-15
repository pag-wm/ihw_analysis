SELECT 
    f.reg_ent_name, 
    COUNT(DISTINCT a.waste_code) AS unique_waste_streams,
    SUM(a.p_quantity_generated::numeric) AS total_pounds
FROM 
    annual_waste_summary as a
JOIN 
    facilities as f ON a.form_registration = f.additional_id_text
WHERE 
    f.program_code = 'IHW'
GROUP BY 
    f.reg_ent_name
HAVING 
    SUM(a.p_quantity_generated::numeric) > 0
ORDER BY 
    unique_waste_streams DESC
LIMIT 15;