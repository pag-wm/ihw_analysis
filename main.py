from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv
from weasyprint import HTML
from io import BytesIO
import os
import zipfile

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
engine = create_engine(os.getenv("DATABASE_URL"))

# --- SHARED SERVICE LOGIC ---

def get_prospectus_data(swr_num: str, radius: int):
    """The 'Brain' of the app: Fetches all data and performs calculations."""
    query = (
        "SELECT f.*, (a.p_quantity_generated::numeric)/2000 as tons "
        "FROM nor_facilities as f JOIN annual_waste_summary as a ON a.form_registration = f.swr_num_txt "
        f"WHERE f.swr_num_txt = '{swr_num}'"
    )
    df = pd.read_sql(query, engine)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Facility not found")

    site_data = df.iloc[0].to_dict()
    volume = site_data.get('tons', 0) or 0
    lat, lon = site_data['lat_dec_coord_num'], site_data['long_dec_coord_num']

    # Sub-calculations
    sat_label, sat_color, sat_dist = get_market_saturation(lat, lon)
    shed_volume = get_feedstock_shed(lat, lon, radius)
    top_generators = get_top_generators(lat, lon, radius, swr_num)

    # Financials (Centralized Constants)
    landfill_rate, recovery_value, capex = 68.00, 820.00, 5_000_000
    disposal_cost = volume * landfill_rate
    revenue_potential = volume * recovery_value
    value_flip = disposal_cost + revenue_potential
    
    payback_years = round(capex / value_flip, 1) if value_flip > 0 else "N/A"
    payback_percent = min(100, (1 / (float(payback_years) / 10)) * 10) if value_flip > 0 else 0

    # ESG
    total_co2_saved = volume * 1.7
    
    return {
        "site": site_data,
        "shed_volume": f"{shed_volume:,.1f}",
        "current_radius": radius,
        "top_generators": top_generators,
        "score": 84.2,
        "profit": f"${2400000:,.0f}", # Placeholder as requested
        "current_disposal_cost": f"-${disposal_cost:,.0f}",
        "projected_revenue": f"+${revenue_potential:,.0f}",
        "total_value_flip": f"${value_flip:,.0f}",
        "tech_name": "Chemical Recycling (Pyrolysis)",
        "payback_years": payback_years,
        "payback_percent": 100 - payback_percent,
        "comp_distance": sat_dist,
        "saturation_level": sat_label,
        "saturation_color": sat_color,
        "co2_saved": f"{total_co2_saved:,.0f}",
        "cars_removed": f"{round(total_co2_saved / 4.6):,}",
    }

# --- ROUTES ---

@app.get("/prospectus/{swr_num}", response_class=HTMLResponse)
async def get_prospectus(request: Request, swr_num: str, radius: int = 50):
    context = get_prospectus_data(swr_num, radius)
    context["request"] = request # Template needs the request object
    return templates.TemplateResponse(request=request, name="prospectus.html", context=context)

@app.get("/prospectus/{swr_num}/pdf")
async def export_prospectus_pdf(request: Request, swr_num: str, radius: int = 50):
    context = get_prospectus_data(swr_num, radius)
    context["request"] = request
    
    # Render HTML to string
    response = templates.TemplateResponse(name="prospectus.html", context=context)
    html_string = response.body.decode()

    # Convert to PDF
    pdf_file = HTML(string=html_string, base_url=str(request.base_url)).write_pdf()

    return Response(
        content=pdf_file,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Prospectus_{swr_num}.pdf"}
    )

@app.get("/county/{county_name}", response_class=HTMLResponse)
async def get_county_view(request: Request, county_name: str):
    facilities = get_county_facilities(county_name)
    
    return templates.TemplateResponse(
        request=request,
        name="county_view.html",
        context={
            "county_name": county_name,
            "facilities": facilities,
            "total_count": len(facilities)
        }
    )

@app.get("/county/{county_name}/export-all")
async def export_all_county_pdfs(request: Request, county_name: str):
    facilities = get_county_facilities(county_name)
    
    # Create an in-memory ZIP file
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for fac in facilities:
            swr = fac['swr_num_txt']
            # Re-use your existing logic to generate the PDF
            context = get_prospectus_data(swr, radius=50)
            context["request"] = request
            
            response = templates.TemplateResponse(name="prospectus.html", context=context)
            html_string = response.body.decode()
            
            pdf_bytes = HTML(string=html_string, base_url=str(request.base_url)).write_pdf()
            
            # Add to ZIP
            zip_file.writestr(f"Prospectus_{swr}.pdf", pdf_bytes)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={county_name}_Prospectuses.zip"}
    )
    
# --- HELPER FUNCTIONS (Market Sat, Feedstock Shed, etc.) ---

def get_market_saturation(site_lat, site_lon, proposed_tech="Recycling"):
    query = f"""
    SELECT comp_name as name, comp_type as type,
           (3959 * acos(cos(radians({site_lat})) * cos(radians(latitude)) * cos(radians(longitude) - radians({site_lon})) + 
           sin(radians({site_lat})) * sin(radians(latitude)))) AS dist
    FROM competitor_locations
    ORDER BY dist ASC LIMIT 1;
    """
    res = pd.read_sql(query, engine)
    
    if res.empty:
        return "Opportunity", "Green", "0 Miles"

    nearest = res.iloc[0]
    dist = round(nearest['dist'], 1)
    
    # Logic: If the nearest site is a landfill, they are a 'partner' for waste diversion, not a tech competitor
    if "Landfill" in nearest['type'] or "Disposal" in nearest['type']:
        return "High (Disruption Opportunity)", "#00ff88", dist
    elif dist < 15:
        return "Low (Saturated)", "#ff4d4d", dist
    else:
        return "Moderate", "#ffcc00", dist

def get_feedstock_shed(lat, lon, radius=50):
    query = f"""
        SELECT 
            SUM(a.p_quantity_generated::numeric) / 2000 as shed_tons,
            COUNT(DISTINCT f.swr_num_txt) as generator_count
        FROM nor_facilities as f
        JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
        WHERE 
            (3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
            sin(radians({lat})) * sin(radians(f.lat_dec_coord_num)))) <= {radius};
    """
    res = pd.read_sql(query, engine)
    return round(res.iloc[0]['shed_tons'] or 0, 1)

def get_top_generators(lat, lon, radius, current_swr):
    query = f"""
    SELECT coalesce(f.facility_site_name, f.swr_num_txt) as company_name,
           SUM(a.p_quantity_generated::numeric) / 2000 as annual_tons,
           ROUND((3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
           sin(radians({lat})) * sin(radians(f.lat_dec_coord_num))))::numeric, 1) AS distance
    FROM nor_facilities as f
    JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
    WHERE f.swr_num_txt != '{current_swr}'
      AND (3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
          sin(radians({lat})) * sin(radians(f.lat_dec_coord_num)))) <= {radius}
    GROUP BY coalesce(f.facility_site_name, f.swr_num_txt), f.lat_dec_coord_num, f.long_dec_coord_num
    ORDER BY annual_tons DESC
    LIMIT 5;
    """
    return pd.read_sql(query, engine).to_dict(orient="records")

def get_county_facilities(county_name: str):
    query = f"""
    SELECT f.swr_num_txt, f.facility_site_name, 
           SUM(a.p_quantity_generated::numeric)/2000 as total_tons
    FROM nor_facilities as f
    JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
    WHERE UPPER(f.site_county_name) = UPPER('{county_name}')
    GROUP BY f.swr_num_txt, f.facility_site_name
    HAVING SUM(a.p_quantity_generated::numeric) > 0
    ORDER BY total_tons DESC;
    """
    return pd.read_sql(query, engine).to_dict(orient="records")