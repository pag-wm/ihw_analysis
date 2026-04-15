import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def plot_regional_tonnage():
    query = """
    SELECT 
        f.site_county_name as county_name, 
        SUM(a.p_quantity_generated::numeric) / 2000 AS tons
    FROM annual_waste_summary as a
    JOIN nor_facilities as f ON a.form_registration = f.swr_num_txt
    GROUP BY f.site_county_name
    ORDER BY tons DESC
    LIMIT 15;
    """
    df = pd.read_sql(query, engine)

    plt.figure(figsize=(12, 8))
    sns.set_theme(style="whitegrid")
    
    # Create the horizontal bar chart
    ax = sns.barplot(
        x="tons", 
        y="county_name", 
        data=df, 
        hue="county_name",  # Assign y variable to hue
        palette="Reds_r", 
        legend=False        # Hide the redundant legend
    )    
    plt.title('Top 15 Texas Counties by IHW Tonnage (2024)', fontsize=16)
    plt.xlabel('Total Tons Generated', fontsize=12)
    plt.ylabel('County', fontsize=12)
    
    # Add labels to the end of each bar
    for p in ax.patches:
        ax.annotate(f'{p.get_width():,.0f} tons', 
                   (p.get_width(), p.get_y() + p.get_height() / 2),
                   xytext=(5, 0), textcoords='offset points', ha='left', va='center')

    plt.tight_layout()
    plt.savefig('regional_tonnage_bar.png', dpi=300)
    print("✅ Regional tonnage chart saved as 'regional_tonnage_bar.png'")

if __name__ == "__main__":
    plot_regional_tonnage()