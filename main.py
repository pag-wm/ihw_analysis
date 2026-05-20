from fastapi import FastAPI, Response, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Numeric
from math import radians, cos, sin, asin, sqrt
import pandas as pd
from dotenv import load_dotenv
from weasyprint import HTML
from io import BytesIO
import zipfile
import os
import urllib.request
import urllib.parse
import json

# Import local modules
from database import SessionLocal, engine
import models

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- DATABASE DEPENDENCY ---

def get_db():
    """Provides a database session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- MATH & LOGIC HELPERS ---

def haversine(lat1, lon1, lat2, lon2):
    """Calculates the distance in miles between two coordinate points."""
    if None in (lat1, lon1, lat2, lon2):
        return 999
    R = 3959.874 # Radius of Earth in miles
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1, lat2 = radians(lat1), radians(lat2)
    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2*asin(sqrt(a))
    return R * c

def geocode_address(address: str):
    """
    Geocodes an address to latitude and longitude using OpenStreetMap Nominatim.
    Uses built-in urllib to eliminate extra library dependencies.
    """
    safe_address = urllib.parse.quote(address)
    url = f"https://nominatim.openstreetmap.org/search?q={safe_address}&format=json&limit=1"
    
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "IHW_Analysis_App/1.0 (pagwm@ihw_analysis_app.com)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data:
                    return {
                        "lat": float(data[0]["lat"]),
                        "lon": float(data[0]["lon"]),
                        "display_name": data[0]["display_name"]
                    }
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None

def calculate_suitability(fac_tons, nearby_comp_tons):
    """
    Calculates suitability based on volume and competition saturation.
    REVISED: Added a 'Volume floor' requirement for high scores.
    """
    if not fac_tons or fac_tons < 10: # Minimum 10 tons to be 'suitable'
        return 15
    
    # Base score on volume (0-60 points)
    # Scaled so 1000+ tons is the target for a high score
    volume_score = min(60, (float(fac_tons) / 1000) * 60)
    
    # Competitive penalty (0-40 points)
    comp_tons = float(nearby_comp_tons or 0)
    if comp_tons == 0:
        comp_bonus = 40
    else:
        # Scale penalty: 200,000 tons of local competition wipes out the bonus
        comp_bonus = max(0, 40 - (comp_tons / 200000) * 40)
        
    final_score = int(volume_score + comp_bonus)
    return min(99, max(10, final_score))

# --- DATA SERVICES ---

def get_prospectus_data(swr_num_txt: str, radius: int):
    """Fetches all raw metrics for a facility prospectus via raw SQL."""
    query = (
        "SELECT f.*, (CAST(a.p_quantity_generated AS NUMERIC))/2000 as tons "
        "FROM nor_facilities as f JOIN annual_waste_summary as a ON a.form_registration = f.swr_num_txt "
        f"WHERE f.swr_num_txt = '{swr_num_txt}'"
    )
    df = pd.read_sql(query, engine)
    
    if df.empty:
        query_fac = f"SELECT * FROM nor_facilities WHERE swr_num_txt = '{swr_num_txt}'"
        df = pd.read_sql(query_fac, engine)
        if df.empty:
            raise HTTPException(status_code=404, detail="Facility not found")
        df['tons'] = 0

    site_data = df.iloc[0].to_dict()
    volume = float(site_data.get('tons', 0) or 0)
    lat, lon = site_data.get('lat_dec_coord_num'), site_data.get('long_dec_coord_num')

    # Geo-calculations
    sat_label, sat_color, sat_dist = get_market_saturation(lat, lon)
    shed_volume = get_feedstock_shed(lat, lon, radius)
    top_generators = get_top_generators(lat, lon, radius, swr_num_txt)

    # REVISED FINANCIAL MODELING
    # Use a variable CAPEX: \$500k for small sites, \$5M for large industrial sites
    capex = 5_000_000 if volume > 500 else 500_000
    
    landfill_rate, recovery_value = 68.00, 820.00
    disposal_cost = volume * landfill_rate
    revenue_potential = volume * recovery_value
    value_flip = disposal_cost + revenue_potential
    
    # Calculate Payback
    if value_flip > 500: # Minimum \$500 annual value to show a calculation
        payback_years = round(capex / value_flip, 1)
    else:
        payback_years = "Infinite"
        
    payback_percent = 0
    if isinstance(payback_years, float):
        # UI Progress bar: 100% means 2-year payback, 0% means 20+ year payback
        payback_percent = max(0, min(100, (1 - (payback_years / 20)) * 100))

    return {
        "site": site_data,
        "shed_volume": f"{shed_volume:,.1f}",
        "current_radius": radius,
        "top_generators": top_generators,
        "current_disposal_cost": f"-${disposal_cost:,.0f}",
        "projected_revenue": f"+${revenue_potential:,.0f}",
        "total_value_flip": f"${value_flip:,.0f}",
        "tech_name": "Chemical Recycling (Pyrolysis)",
        "payback_years": payback_years,
        "payback_percent": payback_percent,
        "comp_distance": sat_dist,
        "saturation_level": sat_label,
        "saturation_color": sat_color,
        "co2_saved": f"{volume * 1.7:,.0f}",
        "cars_removed": f"{round((volume * 1.7) / 4.6):,}",
    }

# --- ROUTES ---

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})

@app.get("/search")
async def search_facility(swr: str):
    return RedirectResponse(url=f"/facility/{swr}")

@app.get("/facility/{swr_num_txt}")
async def get_facility_view(swr_num_txt: str, request: Request, db: Session = Depends(get_db)):
    # 1. Fetch Facility
    facility = db.query(models.Facility).filter(models.Facility.swr_num_txt == swr_num_txt).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found in database.")

    # 2. Fetch and Filter Competitors
    all_comps = db.query(models.Competitor).all()
    nearby_competitors = []
    total_comp_tons = 0
    for comp in all_comps:
        dist = haversine(facility.lat_dec_coord_num, facility.long_dec_coord_num, 
                         comp.lat_dec_coord_num, comp.long_dec_coord_num)
        if dist <= 15:
            comp.distance = round(dist, 1)
            total_comp_tons += float(comp.total_tons or 0)
            nearby_competitors.append(comp)

    # 3. Get Facility Tonnage and Calculate Dynamic Suitability
    fac_tons = db.query(func.sum(cast(models.WasteSummary.p_quantity_generated, Numeric))).\
        filter(models.WasteSummary.form_registration == facility.swr_num_txt).scalar() or 0
    
    # Convert fac_tons to decimal-based tons
    suitability_score = calculate_suitability(float(fac_tons)/2000, total_comp_tons)

    # 4. Get Context
    context = get_prospectus_data(swr_num_txt, radius=50)
    context.update({
        "request": request,
        "suitability": suitability_score,
        "competitors": nearby_competitors
    })
    
    return templates.TemplateResponse(request, "prospectus.html", context)

@app.get("/address-search", response_class=HTMLResponse)
async def address_search_view(request: Request, address: str = None, radius: int = 15):
    """
    Fuzzy address lookup route. Converts addresses to coordinates, searches
    the radius for facilities, and aggregates individual waste streams by
    types, amounts, and report consistency (frequency).
    """
    if not address:
        return templates.TemplateResponse(
            request, 
            "address_view.html", 
            {"request": request, "streams": None, "address": None}
        )

    # 1. Convert Text Address to Coordinates
    loc = geocode_address(address)
    if not loc:
        return templates.TemplateResponse(
            request, 
            "address_view.html", 
            {
                "request": request, 
                "streams": [], 
                "address": address, 
                "error": "Could not geocode address. Please try a more specific address or city."
            }
        )

    lat, lon = loc["lat"], loc["lon"]

    # 2. Query Facilities and Waste Streams inside this radius
    query = f"""
        SELECT 
            f.swr_num_txt, 
            f.facility_site_name, 
            a.waste_code,
            CAST(a.p_quantity_generated AS NUMERIC) as quantity_lbs,
            a.report_year,
            (3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
             sin(radians({lat})) * sin(radians(f.lat_dec_coord_num)))) AS distance
        FROM nor_facilities f
        JOIN annual_waste_summary a ON f.swr_num_txt = a.form_registration
        WHERE f.lat_dec_coord_num IS NOT NULL AND f.long_dec_coord_num IS NOT NULL
          AND (3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
               sin(radians({lat})) * sin(radians(f.lat_dec_coord_num)))) <= {radius}
        ORDER BY distance ASC, quantity_lbs DESC;
    """
    df = pd.read_sql(query, engine)

    streams = []
    if not df.empty:
        # Group by SWR and Waste Code to figure out frequency across multi-year data
        grouped = df.groupby(['swr_num_txt', 'facility_site_name', 'distance', 'waste_code'])
        for (swr, name, dist, code), group in grouped:
            years_reported = group['report_year'].nunique()
            total_lbs = group['quantity_lbs'].sum()
            total_tons = total_lbs / 2000.0
            
            # Formulate Analytical Frequency Metrics based on historical timeline
            if years_reported > 2:
                frequency = "Continuous (Routine)"
            elif years_reported == 2:
                frequency = "Periodic (Intermittent)"
            else:
                frequency = "One-Time (Project/Spill)" if total_tons < 15 else "Batch (Cyclical)"

            # Formulate Waste Code Classification Type
            code_str = str(code).strip()
            if code_str.endswith('H') or 'H' in code_str:
                waste_type = "Hazardous Waste"
            elif code_str.endswith('1') or '1' in code_str:
                waste_type = "Class 1 Non-Hazardous Industrial"
            elif code_str.endswith('2') or '2' in code_str:
                waste_type = "Class 2 Industrial"
            else:
                waste_type = "Industrial/General Waste"

            streams.append({
                "swr": swr,
                "facility_name": name,
                "distance": round(float(dist), 1),
                "waste_code": code_str,
                "waste_type": waste_type,
                "amount_tons": round(total_tons, 2),
                "frequency": frequency,
                "years_reported": sorted(list(group['report_year'].unique()))
            })

    # Sort final aggregated streams by closest distance
    streams = sorted(streams, key=lambda x: x["distance"])

    context = {
        "request": request,
        "address": address,
        "resolved_address": loc["display_name"],
        "lat": lat,
        "lon": lon,
        "radius": radius,
        "streams": streams,
        "total_tons": round(sum(s["amount_tons"] for s in streams), 1)
    }
    return templates.TemplateResponse(request, "address_view.html", context)

@app.get("/prospectus/{swr_num_txt}/pdf")
async def export_prospectus_pdf(request: Request, swr_num_txt: str, db: Session = Depends(get_db)):
    """Generates and downloads a PDF prospectus for a specific facility."""
    facility = db.query(models.Facility).filter(models.Facility.swr_num_txt == swr_num_txt).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    # Fetch context (matching the web view logic)
    all_comps = db.query(models.Competitor).all()
    total_comp_tons = 0
    nearby_competitors = []
    for comp in all_comps:
        dist = haversine(facility.lat_dec_coord_num, facility.long_dec_coord_num, 
                         comp.lat_dec_coord_num, comp.long_dec_coord_num)
        if dist <= 15:
            comp.distance = round(dist, 1)
            total_comp_tons += float(comp.total_tons or 0)
            nearby_competitors.append(comp)

    fac_raw_tons = db.query(func.sum(cast(models.WasteSummary.p_quantity_generated, Numeric))).\
        filter(models.WasteSummary.form_registration == facility.swr_num_txt).scalar() or 0
    
    suitability_score = calculate_suitability(float(fac_raw_tons)/2000, total_comp_tons)
    context = get_prospectus_data(swr_num_txt, radius=50)
    context.update({
        "request": request,
        "suitability": suitability_score,
        "competitors": nearby_competitors,
        "is_pdf": True,  # Flag to hide PDF download link in the generated PDF
    })

    # Render to HTML string and convert via WeasyPrint
    template = templates.get_template("prospectus.html")
    html_string = template.render(context)
    pdf_bytes = HTML(string=html_string, base_url=str(request.base_url)).write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Prospectus_{swr_num_txt}.pdf"}
    )

@app.get("/county/{county_name}", response_class=HTMLResponse)
async def get_county_view(request: Request, county_name: str):
    facilities = get_county_facilities(county_name)
    context = {"request": request, "county_name": county_name, "facilities": facilities, "total_count": len(facilities)}
    return templates.TemplateResponse(request, "county_view.html", context)

# --- DATABASE HELPERS ---

def get_market_saturation(site_lat, site_lon):
    if not site_lat or not site_lon:
        return "Unknown", "#888", "N/A"
    query = f"""
    SELECT company_name, permit_type,
           (3959 * acos(cos(radians({site_lat})) * cos(radians(lat_dec_coord_num)) * cos(radians(long_dec_coord_num) - radians({site_lon})) + 
           sin(radians({site_lat})) * sin(radians(lat_dec_coord_num)))) AS dist
    FROM competitor_locations
    ORDER BY dist ASC LIMIT 1;
    """
    res = pd.read_sql(query, engine)
    if res.empty: return "Opportunity", "#00ff88", "N/A"
    dist = round(res.iloc[0]['dist'], 1)
    if dist < 15: return "Low (Saturated)", "#ff4d4d", f"{dist} Mi"
    return "Moderate", "#ffcc00", f"{dist} Mi"

def get_feedstock_shed(lat, lon, radius=50):
    if not lat or not lon: return 0
    query = f"""
        SELECT SUM(CAST(a.p_quantity_generated AS NUMERIC)) / 2000 as shed_tons
        FROM nor_facilities as f
        JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
        WHERE (3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
               sin(radians({lat})) * sin(radians(f.lat_dec_coord_num)))) <= {radius};
    """
    res = pd.read_sql(query, engine)
    return round(res.iloc[0]['shed_tons'] or 0, 1)

def get_top_generators(lat, lon, radius, current_swr):
    if not lat or not lon: return []
    query = f"""
    SELECT facility_site_name as company_name,
           SUM(CAST(a.p_quantity_generated AS NUMERIC)) / 2000 as annual_tons,
           ROUND((3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
           sin(radians({lat})) * sin(radians(f.lat_dec_coord_num))))::numeric, 1) AS distance
    FROM nor_facilities as f
    JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
    WHERE f.swr_num_txt != '{current_swr}'
      AND (3959 * acos(cos(radians({lat})) * cos(radians(f.lat_dec_coord_num)) * cos(radians(f.long_dec_coord_num) - radians({lon})) + 
          sin(radians({lat})) * sin(radians(f.lat_dec_coord_num)))) <= {radius}
    GROUP BY facility_site_name, f.lat_dec_coord_num, f.long_dec_coord_num
    ORDER BY annual_tons DESC LIMIT 5;
    """
    return pd.read_sql(query, engine).to_dict(orient="records")

def get_county_facilities(county_name: str):
    query = f"""
    SELECT f.swr_num_txt, f.facility_site_name, 
           SUM(CAST(a.p_quantity_generated AS NUMERIC))/2000 as total_tons
    FROM nor_facilities as f
    JOIN annual_waste_summary as a ON f.swr_num_txt = a.form_registration
    WHERE UPPER(f.site_county_name) = UPPER('{county_name}')
    GROUP BY f.swr_num_txt, f.facility_site_name
    HAVING SUM(CAST(a.p_quantity_generated AS NUMERIC)) > 0
    ORDER BY total_tons DESC;
    """
    return pd.read_sql(query, engine).to_dict(orient="records")