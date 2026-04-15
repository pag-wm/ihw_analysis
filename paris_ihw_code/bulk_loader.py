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
# Retry 5 times, back off exponentially (0.3s, 0.6s, 1.2s...)
# status_forcelist handles server-side blips (500, 502, 503, 504)
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

DATASETS = {
    "nor_facilities": "v287-9kbw",
    #"waste_lookup": "bwem-j8ee",
}

headers = {"X-App-Token": os.getenv("TEXAS_DATA_TOKEN")}

def clean_and_load_facilities(df):
    # Standardize the join key first
    if 'swr_num_txt' in df.columns:
        df['swr_num_txt'] = df['swr_num_txt'].astype(str).str.strip()

    # Define the coordinate columns
    coord_cols = ['lat_dec_coord_num', 'long_dec_coord_num']

    for col in coord_cols:
        if col in df.columns:
            print(f"🛠 Converting {col} to numeric...")
            # 'coerce' turns bad data into NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Optional: Drop rows where coordinates are missing to keep the map clean
    initial_count = len(df)
    df = df.dropna(subset=coord_cols)
    print(f"🗑 Dropped {initial_count - len(df)} rows with invalid/missing coordinates.")

    return df

def fetch_and_sql(name, dataset_id):
    url = f"https://data.texas.gov/resource/{dataset_id}.json"
    print(f"\n📥 Fetching {name}...")
    
    all_rows = []
    offset = 0
    chunk_size = 2000 # Lowered slightly to reduce chance of IncompleteRead

    while True:
        params = {"$limit": chunk_size, "$offset": offset, "$order": ":id"}
        try:
            # Using the session with retries instead of direct requests.get
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
            time.sleep(2) # Extra breather
            continue # Try the same offset again

    if all_rows:
        df = pd.DataFrame(all_rows)

        # Clean coordinates and keys
        df = clean_and_load_facilities(df)

        df.to_sql(name, engine, if_exists='replace', index=False, chunksize=1000)
        print(f"\n✅ {name} loaded into Postgres.")

if __name__ == "__main__":
    for name, d_id in DATASETS.items():
        fetch_and_sql(name, d_id)