from sqlalchemy import Column, Integer, String, Float, Numeric, Boolean
from database import Base

class Facility(Base):
    """
    Maps to the TCEQ Notice of Registration (NOR) facilities table.
    """
    __tablename__ = 'nor_facilities'
    
    # We map 'swr_num' to the underlying 'swr_num_txt' column to match 
    # the join logic used in the raw SQL queries.
    swr_num_txt = Column(String, primary_key=True)
    facility_site_name = Column(String)
    site_county_name = Column(String)
    lat_dec_coord_num = Column(Float)
    long_dec_coord_num = Column(Float)

class WasteSummary(Base):
    """
    Maps to the Annual Waste Summary table for volume analysis.
    """
    __tablename__ = 'annual_waste_summary'
    
    id = Column(Integer, primary_key=True)
    form_registration = Column(String) # Links to nor_facilities.swr_num_txt
    p_quantity_generated = Column(String) # Often imported as text, cast to Numeric in queries
    report_year = Column(String)

class Competitor(Base):
    """
    Maps to our custom competitor tracking table used for market saturation analysis.
    """
    __tablename__ = 'competitor_locations'
    
    id = Column(Integer, primary_key=True)
    company_name = Column(String)
    permit_type = Column(String)
    lat_dec_coord_num = Column(Float)
    long_dec_coord_num = Column(Float)
    county_name = Column(String)
    swr_num = Column(String)
    total_tons = Column(Numeric)
    suitability_score = Column(Integer)