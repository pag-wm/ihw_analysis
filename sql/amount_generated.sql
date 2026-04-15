SELECT f.swr_num_txt, f.facility_site_name, SUM(a.p_quantity_generated::numeric)/2000 as tons
FROM nor_facilities as f
JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
GROUP BY f.swr_num_txt, f.facility_site_name
ORDER BY tons DESC
LIMIT 10;