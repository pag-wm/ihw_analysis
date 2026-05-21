import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Force load the .env file into system environment variables immediately
load_dotenv()

# 1. Fetch the live environment variable injected by Cloud Run
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Add an explicit defensive fallback/error trap
if not DATABASE_URL:
    raise ValueError("CRITICAL ERROR: The DATABASE_URL environment variable is completely empty!")

if "[DATABASE_NAME]" in DATABASE_URL:
    raise ValueError(f"CRITICAL ERROR: Code is reading a placeholder string! Current string value is: {DATABASE_URL}")

# 3. Create the engine dynamically
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency function to provide a database session for FastAPI routes.
    Ensures the connection is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()