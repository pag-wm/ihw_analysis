import os
import requests
import pandas as pd
import time
from sqlalchemy import create_engine
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

# --- SETTING UP A RESILIENT SESSION ---
session = requests.Session()
# Retry 5 times, back off exponentially (1s, 2s, 4s, 8s, 16s)
# status_forcelist handles server-side blips (429, 500, 502, 503, 504)
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# --- DATASET REGISTRY WITH DYNAMIC $WHERE CLAUSES ---
# Value format: (dataset_id, where_condition)
# Set the where condition to None or "" to fetch all records.
# shipping - https://data.texas.gov/dataset/Texas-Commission-on-Environmental-Quality-Waste-Sh/yuba-pjk3/about_data
# contacts - https://data.texas.gov/dataset/Texas-Commission-on-Environmental-Quality-NOR-Bill/azdq-v4ap/about_data
# annual - https://data.texas.gov/dataset/Texas-Commission-on-Environmental-Quality-Annual-W/79s2-9ack/about_data
# facilities - https://data.texas.gov/dataset/Texas-Commission-on-Environmental-Quality-NOR-Faci/v287-9kbw/about_data
# waste - https://data.texas.gov/dataset/Texas-Commission-on-Environmental-Quality-NOR-Wast/bwem-j8ee/about_data

DATASETS = {
    "shipping": ("yuba-pjk3", None), 
    "contacts": ("azdq-v4ap", None), # Fetch all contacts
    "annual_waste_summary": ("79s2-9ack", "date_extract_y(report_year) = 2024"),
    "nor_facilities": ("v287-9kbw", None),
    "waste_lookup": ("bwem-j8ee", None),
}

headers = {"X-App-Token": os.getenv("TEXAS_DATA_TOKEN")}

def clean_and_load_facilities(df):
    """Trims whitespace and parses coordinates safely to numeric formats."""
    # Trim whitespace from the main join key
    if 'form_registration' in df.columns:
        df['form_registration'] = df['form_registration'].astype(str).str.strip()
    
    # Trim other potential keys
    for col in ['waste_code', 'epa_id']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Standardize the join key
    if 'swr_num_txt' in df.columns:
        df['swr_num_txt'] = df['swr_num_txt'].astype(str).str.strip()

    # Convert the coordinate columns
    coord_cols = ['lat_dec_coord_num', 'long_dec_coord_num']

    for col in coord_cols:
        if col in df.columns:
            print(f"🛠 Converting {col} to numeric...")
            # 'coerce' turns bad data into NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')

    initial_count = len(df)
    # Check if BOTH columns exist in the dataframe before trying to dropna
    if all(col in df.columns for col in coord_cols):
        df = df.dropna(subset=coord_cols)
    else:
        print(f"Skipping coordinate cleaning: Columns not found in this table.")
    print(f"🗑 Dropped {initial_count - len(df)} rows with invalid/missing coordinates.")

    return df

def fetch_and_sql(name, dataset_id, where_condition=None):
    """
    Fetches Socrata datasets in chunks and loads them into PostgreSQL.
    Supports dynamic $where filters to reduce bandwidth and database footprint.
    """
    url = f"https://data.texas.gov/resource/{dataset_id}.json"
    print(f"\n📥 Fetching {name} (ID: {dataset_id})...")
    if where_condition:
        print(f"🔍 Applying Filter: $where=\"{where_condition}\"")
    
    all_rows = []
    offset = 0
    chunk_size = 2000

    while True:
        params = {
            "$limit": chunk_size,
            "$offset": offset,
            "$order": ":id",
        }
        
        # Inject the $where clause only if a valid condition is passed
        if where_condition and where_condition.strip():
            params["$where"] = where_condition

        try:
            r = session.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            
            if not data:
                break
                
            all_rows.extend(data)
            offset += chunk_size
            print(f"   Collected {len(all_rows)} rows...", end="\r")
            
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as e:
            print(f"\n⚠️ Connection flickered. Retrying offset {offset}...")
            time.sleep(2) # Extra breather before retry
            continue # Try the same offset again

    if all_rows:
        df = pd.DataFrame(all_rows)

        # Clean coordinates and keys
        df = clean_and_load_facilities(df)

        df.to_sql(name, engine, if_exists='replace', index=False, chunksize=1000)
        print(f"\n✅ {name} loaded into Postgres (Total: {len(df)} rows).")
    else:
        print(f"\n⚠️ No records found matching the criteria for {name}.")

if __name__ == "__main__":
    for name, config in DATASETS.items():
        # Support both the new tuple format and fallback strings seamlessly
        if isinstance(config, tuple):
            d_id, where_cond = config
        else:
            d_id, where_cond = config, None
            
        fetch_and_sql(name, d_id, where_cond)