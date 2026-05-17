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

#Week 4-5
import numpy as np

#Convert date fields to datetime)
df = pd.read_csv('CRMLSSold_Enriched.csv', low_memory=False)
df.head()

print("Week 4-5: Data Cleaning and Preparation")

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


#Week 6 Feature Engineering and Market Metrics

# %%
import pandas as pd
df = pd.read_csv('CRMLSSold_Cleaned.csv', low_memory=False)

date_cols = ['CloseDate', 'PurchaseContractDate', 'ListingContractDate']
for col in date_cols:
    df[col] = pd.to_datetime(df[col], errors='coerce')

df['Price_Ratio'] = df['ClosePrice'] / df['OriginalListPrice']
df['Price_Per_SqFt'] = df['ClosePrice'] / df['LivingArea']
df['Days on Market'] = df['DaysOnMarket']
df['Year'] = df['CloseDate'].dt.year
df['Month'] = df['CloseDate'].dt.month
df['YrMo'] = df['CloseDate'].dt.strftime('%Y-%m')

df['Listing_to_Contract_Days'] = (df['PurchaseContractDate'] - df['ListingContractDate']).dt.days
df['Contract_to_Close_Days'] = (df['CloseDate'] - df['PurchaseContractDate']).dt.days

#Sample output table
engineered_cols = ['ClosePrice', 'OriginalListPrice', 'Price_Ratio', 'Price_Per_SqFt', 
                   'YrMo', 'Listing_to_Contract_Days', 'Contract_to_Close_Days']
print(df[engineered_cols].sample(n=5, random_state=42))

# Segment Analysis
print("\n Segment Analysis")

metrics_to_summarize = ['ClosePrice', 'Price_Per_SqFt', 'Price_Ratio', 'Listing_to_Contract_Days']

# Segment property type (PropertyType)
print("\n Grouped by PropertyType:")
summary_by_type = df.groupby('PropertyType')[metrics_to_summarize].mean().round(2)
print(summary_by_type)

# Test Mean - CountyOrParish column exists before grouping, as not all datasets may have this column. If it does exist, we can do the grouping; if not, we skip this part.
if 'CountyOrParish' in df.columns:
    print("\n Check: Grouped by CountyOrParish:")
    summary_by_county = df.groupby('CountyOrParish')[metrics_to_summarize].mean().round(2)
    
    print(summary_by_county.sample(n=5, random_state=42))

else:
    print("\n Current dataset does not contain 'CountyOrParish' column, skipping county-level segmentation.")


# Prepare tableau Ready dataset
df.to_csv('CRMLSSold_Master_Engineered.csv', index=False)
print("\nFull dataset with engineered features saved as 'CRMLSSold_Master_Engineered.csv'!")



# %%
# Week 7 Outlier Detection and Data Quality
import pandas as pd

df = pd.read_csv('CRMLSSold_Master_Engineered.csv', low_memory=False)

# ensure the three key columns we want to check for outliers are numeric, 
# if they are not, convert them 
# (this is a common issue where sometimes numeric columns can be read as object due to bad data)
target_cols = ['ClosePrice', 'LivingArea', 'DaysOnMarket']
for col in target_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

#calculate length & median 
initial_row_count = len(df)
initial_medians = df[target_cols].median()

# define flag_outliers for the first doc
def flag_outliers(series):
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    # if value is less than lower_bound or greater than upper_bound, it's an outlier
    return (series < lower_bound) | (series > upper_bound)

print("\n Scanning for outliers in ClosePrice, LivingArea, and DaysOnMarket...")

for col in target_cols:
    flag_col_name = f'{col}_Outlier_Flag'
    df[flag_col_name] = flag_outliers(df[col])
    outlier_count = df[flag_col_name].sum()
    print(f"[{col}] outliers: {outlier_count} rows")


# Doc 1: Flagged version - 
# we keep all data but add flags to indicate which rows are outliers in any of the three key columns. 
# This allows for flexible filtering later on if needed, 
# while preserving the full dataset for any analyses that might want to consider outliers.
df.to_csv('CRMLSSold_W7_Flagged.csv', index=False)
print("\n Flagged dataset saved as 'CRMLSSold_W7_Flagged.csv'")

# Create a clean dataset by filtering out all rows 
# that are flagged as outliers in any of the three key columns.
clean_df = df[
    ~(df['ClosePrice_Outlier_Flag']) &
    ~(df['LivingArea_Outlier_Flag']) &
    ~(df['DaysOnMarket_Outlier_Flag'])
].copy()

# Doc 2 Tableau-ready version
# we filter out all rows that are flagged as outliers in any of the three key columns,
clean_df.to_csv('CRMLSSold_W7_Filtered.csv', index=False)
print("Clean dataset saved as 'CRMLSSold_W7_Filtered.csv'")

#Writtenn comparison report
print('written comparison report...')
final_row_count = len(clean_df)
final_medians = clean_df[target_cols].median()

print("\n" + "="*50)
print(" Week 7: Written Comparison")
print("="*50)

print(f"\n Dataset Size")
print(f"Initial Row Counts: {initial_row_count}")
print(f"Filtered Row Counts: {final_row_count}")
print(f"Total Outliers Removed:   {initial_row_count - final_row_count} rows ({(initial_row_count - final_row_count)/initial_row_count*100:.2f}%)")

print(f"\n Median Values")
comparison_df = pd.DataFrame({
    'Before Filtering': initial_medians,
    'After Filtering': final_medians
})

comparison_df['% Change'] = ((comparison_df['After Filtering'] - comparison_df['Before Filtering']) / comparison_df['Before Filtering'] * 100).round(2).astype(str) + '%'

print(comparison_df)
# %%
