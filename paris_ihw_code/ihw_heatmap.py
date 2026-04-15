import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def generate_bounded_heatmap():
    print("🌍 Loading Texas boundary and IHW data...")
    
    # 1. Get Texas Boundary
    # We download a low-res version of US States and filter for Texas
    usa = gpd.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_1_states_provinces.zip")
    texas = usa[usa['name'] == 'Texas']

    counties_url = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_county_5m.zip"
    counties = gpd.read_file(counties_url)

    # 2. Fetch IHW Data
    query = """
        SELECT 
            f.lat_dec_coord_num as latitude, 
            f.long_dec_coord_num as longitude, 
            COUNT(DISTINCT a.waste_code) as stream_count
        FROM 
            annual_waste_summary as a
        JOIN 
            nor_facilities as f ON a.form_registration = f.swr_num_txt
        GROUP BY 
            f.lat_dec_coord_num, f.long_dec_coord_num;
        """
    df = pd.read_sql(query, engine)

    # Convert our Pandas DataFrame to a GeoDataFrame
    # This turns lat/long strings into actual geometric points
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326"
    )

    # 3. Plotting
    fig, ax = plt.subplots(figsize=(15, 12))

    # Layer 1: The Texas Base Map
    texas.plot(ax=ax, color='whitesmoke', edgecolor='darkgrey', zorder=1)
    # 48 is the FIPS code for Texas
    tx_counties = counties[counties['STATEFP'] == '48']
    tx_counties.plot(ax=ax, color='whitesmoke', edgecolor='lightgrey', linewidth=0.5)

    # Layer 2: The Data Points
    # We use 'stream_count' to determine the color (cmap) and size (s)
    scatter = ax.scatter(
        df.longitude, 
        df.latitude, 
        c=df.stream_count, 
        s=df.stream_count * 10, 
        cmap='YlOrRd', 
        alpha=0.7, 
        edgecolor='black', 
        linewidth=0.5,
        zorder=2
    )

    # Add styling
    plt.colorbar(scatter, ax=ax, label='Waste Stream Complexity (Unique Codes)', fraction=0.03, pad=0.04)
    plt.title('Texas IHW Production Density with State Boundaries (2024)', fontsize=18)
    
    # Zoom into Texas bounds
    ax.set_xlim([-107, -93])
    ax.set_ylim([25, 37])
    
    # Remove axis for a "clean" map look
    ax.axis('off')

    # Label Major Hubs
    plt.text(-95.3, 29.7, ' Houston', fontsize=10, fontweight='bold')
    plt.text(-97.7, 30.2, ' Austin', fontsize=10)
    plt.text(-96.8, 32.7, ' Dallas', fontsize=10)

    output_name = "image/texas_ihw_bounded_map.png"
    plt.savefig(output_name, dpi=300, bbox_inches='tight')
    print(f"✅ Bounded heatmap saved as {output_name}")

if __name__ == "__main__":
    generate_bounded_heatmap()