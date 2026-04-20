import pandas as pd
import glob
import requests
import io
import warnings

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Week 1
# Combine history data
sold_files = glob.glob('Files/raw/CRMLSSold*.csv')
listing_files = glob.glob('Files/raw/CRMLSListing*.csv')

# 1. Sold data processing
sold_list = []
for f in sold_files:
    df = pd.read_csv(f, low_memory=False)
    sold_list.append(df)

combined_sold = pd.concat(sold_list, ignore_index=True)
combined_sold = combined_sold[combined_sold['PropertyType'] == 'Residential']

# 2. List data processing
listing_list = []
for f in listing_files:
    df = pd.read_csv(f, low_memory=False)
    listing_list.append(df)

combined_listings = pd.concat(listing_list, ignore_index=True)
combined_listings = combined_listings[combined_listings['PropertyType'] == 'Residential']

print(f"Success!Sold: {len(combined_sold)} rows，Listings: {len(combined_listings)} rows。")


# ==========================================
# Week 2-3: 获取房贷利率并融合

print("\n fetching mortgage rates from FRED...")
url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
response = requests.get(url, verify=False)
mortgage = pd.read_csv(io.StringIO(response.text), parse_dates=['observation_date'])
mortgage.columns = ['date', 'rate_30yr_fixed']


# compute monthly average rates
mortgage['year_month'] = mortgage['date'].dt.to_period('M')
mortgage_monthly = mortgage.groupby('year_month')['rate_30yr_fixed'].mean().reset_index()

print("combined interests into data...")
# Isolate combined_sold and combined_listings
combined_sold['year_month'] = pd.to_datetime(combined_sold['CloseDate']).dt.to_period('M')
combined_listings['year_month'] = pd.to_datetime(combined_listings['ListingContractDate']).dt.to_period('M')

# Merge
sold_with_rates = combined_sold.merge(mortgage_monthly, on='year_month', how='left')
listings_with_rates = combined_listings.merge(mortgage_monthly, on='year_month', how='left')

# Step 5 – Validate the merge
# Check for any unmatched rows (rate should not be null)
print(sold_with_rates['rate_30yr_fixed'].isnull().sum())
print(listings_with_rates['rate_30yr_fixed'].isnull().sum())


# Saved the enrich datasets
sold_with_rates.to_csv('CRMLSSold_Enriched.csv', index=False)
listings_with_rates.to_csv('CRMLSListing_Enriched.csv', index=False)

print("\nProcess completed. Enriched datasets saved as 'CRMLSSold_Enriched.csv' and 'CRMLSListing_Enriched.csv'.")

