import os
import requests
import pandas as pd
import time
from sqlalchemy import create_engine
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()
APP_TOKEN = os.getenv("TEXAS_DATA_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Dataset: Annual Waste Summary
DATASET_ID = "79s2-9ack"
BASE_URL = f"https://data.texas.gov/resource/{DATASET_ID}.json"

# --- CONFIGURATION ---
CHUNK_SIZE = 2000  # Smaller chunks are more stable for large downloads
WHERE_CLAUSE = "report_year = '2024'" 
TABLE_NAME = "annual_waste_summary"

# --- RESILIENT SESSION SETUP ---
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

def fetch_and_clean_ihw():
    if not APP_TOKEN:
        print("❌ Error: TEXAS_DATA_TOKEN not found.")
        return

    all_data = []
    offset = 0
    headers = {"X-App-Token": APP_TOKEN}
    
    print(f"🚀 Starting robust download for {TABLE_NAME}...")

    while True:
        params = {
            "$limit": CHUNK_SIZE,
            "$offset": offset,
            "$order": ":id",
            "$where": WHERE_CLAUSE
        }
        
        try:
            # Authenticated request via session with 30s timeout
            response = session.get(BASE_URL, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                break
            
            all_data.extend(data)
            offset += CHUNK_SIZE
            print(f"📥 Total rows collected: {len(all_data)}...", end="\r")
            
            time.sleep(0.1) # Be polite to the SODA API

        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
            print(f"\n⚠️ Connection hiccup at offset {offset}. Retrying...")
            time.sleep(2)
            continue 
        except Exception as e:
            print(f"\n❌ Permanent Error: {e}")
            break

    # --- DATA CLEANING & LOADING ---
    if all_data:
        print(f"\n✨ Cleaning {len(all_data)} rows...")
        df = pd.DataFrame(all_data)

        # 1. Trim whitespace from the main join key
        if 'form_registration' in df.columns:
            df['form_registration'] = df['form_registration'].astype(str).str.strip()
        
        # 2. Trim other potential keys
        for col in ['waste_code', 'epa_id']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # 3. Load to Postgres
        print(f"💾 Loading into Postgres table '{TABLE_NAME}'...")
        df.to_sql(TABLE_NAME, engine, if_exists='replace', index=False, chunksize=1000)
        print("✅ Success!")
    else:
        print("\n⚠️ No data found.")

if __name__ == "__main__":
    fetch_and_clean_ihw()