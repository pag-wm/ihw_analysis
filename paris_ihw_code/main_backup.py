from fastapi import FastAPI, Query
from sqlalchemy import create_engine
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Waste Stream Repository API")
engine = create_engine(os.getenv("DATABASE_URL"))

def calculate_logistics_impact(volume_tons, distance_miles):
    # 2026 Specialized Hazmat Trucking Estimates
    pickup_fee = 250.00         # Per load
    rate_per_mile = 4.50        # Specialized industrial rate
    tons_per_load = 20          # Average bulk tanker/roll-off capacity
    
    num_loads = (volume_tons / tons_per_load)
    total_logistics_cost = (num_loads * pickup_fee) + (num_loads * distance_miles * rate_per_mile)
    
    return round(total_logistics_cost, 2)

def calculate_logistics_bonus(site_lat, site_lon):
    # This query finds the distance to the nearest logistics hub in miles
    query = f"""
    SELECT hub_name, hub_type,
           (3959 * acos(cos(radians({site_lat})) * cos(radians(latitude)) * cos(radians(longitude) - radians({site_lon})) + 
           sin(radians({site_lat})) * sin(radians(latitude)))) AS distance
    FROM texas_logistics_hubs
    ORDER BY distance ASC
    LIMIT 1;
    """
    res = pd.read_sql(query, engine)
    
    if res.empty: return 0
    
    dist = res['distance'][0]
    
    # Logic: Closer is better
    if dist < 2: return 30  # "Golden Site"
    if dist < 5: return 20  # "Prime Site"
    if dist < 10: return 10 # "Accessible"
    return -10              # "Logistics Desert"

def get_land_suitability(county_name):
    # This function looks up the region for a county and returns the score
    query = f"""
    SELECT suitability_bonus 
    FROM texas_land_values 
    WHERE counties_included ILIKE '%%{county_name}%%'
    """
    res = pd.read_sql(query, engine)
    
    # Default to a middle-ground score if county not explicitly listed
    return res['suitability_bonus'][0] if not res.empty else 50

def get_master_suitability_report(county_name, lat, lon):
    # 1. Get Feedstock Density (from your Annual Summary table)
    density = get_feedstock_density(lat, lon) # 0-100
    
    # 2. Get Land Cost (from our new 'texas_land_values' table)
    land_score = get_land_suitability(county_name) # 0-100
    
    # 3. Get Logistics Bonus (from 'texas_logistics_hubs')
    logistics_bonus = calculate_logistics_bonus(lat, lon) # -10 to +30
    
    # 4. Final Weighted Calculation
    final_score = (density * 0.40) + (land_score * 0.25) + (logistics_bonus + 50) * 0.35
    
    return {
        "county": county_name,
        "suitability_index": round(min(final_score, 100), 1),
        "summary": f"Strong logistics (+{logistics_bonus}) but high land cost." if land_score < 30 else "High ROI due to low land cost."
    }

@app.get("/v1/analytics/suitability")
def get_suitability_score(lat: float, lon: float):
    # 1. Query for tonnage within a 50-mile radius (Feedstock Density)
    # 2. Lookup land value from a 'texas_land_values' table
    # 3. Calculate workforce score based on local unemployment/manufacturing data
    
    density_score = calculate_density_score(lat, lon) # 0-100
    land_score = lookup_land_score(lat, lon) # 0-100 (inverse of cost)
    
    total_score = (density_score * 0.40) + (land_score * 0.15) # ...and so on
    
    return {
        "score": round(total_score, 1),
        "primary_advantage": "High feedstock density",
        "primary_risk": "High land acquisition cost"
    }

@app.get("/")
def root():
    return {"message": "Welcome to the Waste Stream Repository API"}

@app.get("/v1/summary/by-county")
def get_county_summary(county: str = None):
    """Returns total tonnage and site counts by county."""
    query = """
    SELECT f.site_county_name as county_name, 
           COUNT(DISTINCT f.swr_num_txt) as site_count,
           SUM(a.p_quantity_generated::numeric) / 2000 as total_tons
    FROM annual_waste_summary as a
    JOIN nor_facilities f ON a.form_registration = f.swr_num_txt
    """
    
    if county:
        query += f" WHERE f.site_county_name = '{county.upper()}'"
    
    query += " GROUP BY f.site_county_name ORDER BY total_tons DESC"
    
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/v1/streams/search")
def search_streams(description: str = Query(..., min_length=3)):
    """Search for waste streams by keyword (e.g., 'acid', 'solvent')."""
    query = f"""
    SELECT w.wst_desc_txt, f.facility_site_name, f.site_city_name, 
           a.p_quantity_generated as pounds
    FROM waste_lookup as w
    JOIN annual_waste_summary as a ON w.swr_num_txt = a.form_registration 
         AND w.tx_wst_cd = a.waste_code
    JOIN nor_facilities as f ON a.form_registration = f.swr_num_txt
    WHERE w.wst_desc_txt ILIKE '%%{description}%%'
    LIMIT 100
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/v1/roi/project")
def project_roi(swr_id: str, tech_id: str):
    # 1. Fetch Tonnage for the specific stream from Postgres
    stream_data = pd.read_sql(f"SELECT SUM(p_quantity_generated::numeric)/2000 as tons FROM annual_waste_summary WHERE form_registration='{swr_id}'", engine)
    volume = stream_data['tons'][0] or 0

    # 2. Fetch Tech Constants (Normally from your 'recycling_technologies' table)
    # Mock data for demonstration:
    tech = {"opex": 400, "recovery": 0.80, "price": 900, "tipping_fee": 65, "capex": 5000000}

    # 3. Calculate Annual Net Profit
    revenue = (volume * tech['recovery'] * tech['price']) + (volume * tech['tipping_fee'])
    costs = (volume * tech['opex'])
    annual_profit = revenue - costs
    
    payback_period = tech['capex'] / annual_profit if annual_profit > 0 else "Never"

    return {
        "swr_id": swr_id,
        "projected_annual_profit": round(annual_profit, 2),
        "payback_years": round(payback_period, 2) if isinstance(payback_period, float) else payback_period,
        "volume_processed_tons": volume
    }
