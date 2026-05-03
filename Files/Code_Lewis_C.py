import pandas as pd
import glob
import requests
import io
import warnings

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Week 1
# Combine history data
sold_files = glob.glob('raw/CRMLSSold*.csv')
listing_files = glob.glob('raw/CRMLSListing*.csv')

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
# Week 2-3

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

<<<<<<< HEAD
=======
#Week 4-5
import numpy as np

#Convert date fields to datetime)
df = pd.read_csv('CRMLSSold_Enriched.csv', low_memory=False)
df.head()


print("Week 4-5: Data Cleaning and Preparation")

# 读取上一步 (Week 2-3) 跑出来的 Enriched 融合数据集

initial_row_count = len(df)
print(f"(Before cleaning Row Count): {initial_row_count}")

# 1. Convert date fields to datetime)
date_columns = ['CloseDate', 'PurchaseContractDate', 'ListingContractDate', 'ContractStatusChangeDate']

for col in date_columns:
    if col in df.columns:
        # errors='coerce' sets invalid parsing to NaT, which we can easily identify and handle later
        df[col] = pd.to_datetime(df[col], errors='coerce')

print("\n Data Type Confirmations:")
print(df[date_columns].dtypes)

# 2. check ClosePrice <= 0, LivingArea <= 0, DaysOnMarket < 0,
# ensure numeric columns are actually numeric (sometimes they can be read as object due to bad data)
num_cols = ['ClosePrice', 'LivingArea', 'DaysOnMarket', 'BedroomsTotal', 'BathroomsTotalInteger']
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# flag invalide numeric values, ClosePrice <= 0, LivingArea <= 0, DaysOnMarket < 0
df['invalid_numeric_flag'] = (
    (df['ClosePrice'] <= 0) | 
    (df['LivingArea'] <= 0) | 
    (df['DaysOnMarket'] < 0) | 
    (df['BedroomsTotal'] < 0) | 
    (df['BathroomsTotalInteger'] < 0)
)

# 3. Date Consistency Checks

# Logic：ListingContractDate <= PurchaseContractDate <= CloseDate

# listing time later than close time
df['listing_after_close_flag'] = df['ListingContractDate'] > df['CloseDate']
# purchase contract date later than close date
df['purchase_after_close_flag'] = df['PurchaseContractDate'] > df['CloseDate']
# listing time later than purchase contract date (negative timeline)
df['negative_timeline_flag'] = df['ListingContractDate'] > df['PurchaseContractDate']


# 4. Geographic Data Checks)

# Missing coordinates
df['missing_coord_flag'] = df['Latitude'].isnull() | df['Longitude'].isnull()
# Zero coordinates (Cali does not have any valid properties at (0,0))
df['zero_coord_flag'] = (df['Latitude'] == 0) | (df['Longitude'] == 0)
# longtitude > 0, which is not possible for California (all longitudes should be negative in the Western Hemisphere)
df['positive_lon_flag'] = df['Longitude'] > 0
# Out-of-state coordinates: California roughly between latitudes 32-43 and longitudes -125 to -114, anything outside this box is likely an error for a California property
df['out_of_state_flag'] = (
    (df['Latitude'] < 32) | (df['Latitude'] > 43) | 
    (df['Longitude'] < -125) | (df['Longitude'] > -114)
)

# ==========================================
# 5. Print summary of data quality issues found

print("\n=== Date-Consistency Flag Counts ===")
print(f"listing_after_close_flag: {df['listing_after_close_flag'].sum()} ")
print(f"purchase_after_close_flag: {df['purchase_after_close_flag'].sum()} ")
print(f"negative_timeline_flag: {df['negative_timeline_flag'].sum()}")

print("\n=== Geographic Data Quality Summary ===")
print(f"missing_coord_flag: {df['missing_coord_flag'].sum()} ")
print(f"zero_coord_flag: {df['zero_coord_flag'].sum()} ")
print(f"positive_lon_flag: {df['positive_lon_flag'].sum()} ")
print(f"out_of_state_flag: {df['out_of_state_flag'].sum()} ")

# 6. Analysis-ready dataset
# filter out all rows that have any of the flags set to True, meaning we only keep rows that are clean across all our checks
clean_df = df[
    ~(df['invalid_numeric_flag']) &
    ~(df['listing_after_close_flag']) &
    ~(df['purchase_after_close_flag']) &
    ~(df['negative_timeline_flag']) &
    ~(df['missing_coord_flag']) &
    ~(df['zero_coord_flag']) &
    ~(df['positive_lon_flag']) &
    ~(df['out_of_state_flag'])
].copy()

# drop the flag columns as they are no longer needed in the clean dataset
cols_to_drop = [col for col in clean_df.columns if 'flag' in col]
clean_df.drop(columns=cols_to_drop, inplace=True)

final_row_count = len(clean_df)
print("\n cleaning...")
print(f"After Row Count: {final_row_count}")
print(f"Total removed rows: {initial_row_count - final_row_count}")

# Save the clean dataset
clean_df.to_csv('CRMLSSold_Cleaned.csv', index=False)
print("\nAnalysis-ready clean dataset saved as 'CRMLSSold_Cleaned.csv'! Deliverable achieved.")
