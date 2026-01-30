#!/usr/bin/env python3
"""
Geocode Wilson Parking carparks using OpenStreetMap Nominatim API
Extracts actual district names from lat/lon coordinates
"""

import pandas as pd
import requests
import time
import os

CARPARKS_FILE = "data_wilson/carparks.csv"
OUTPUT_FILE = "data_wilson/carparks_geocoded.csv"

def reverse_geocode(lat, lon):
    """Get district from coordinates using Nominatim API"""
    if pd.isna(lat) or pd.isna(lon):
        return '', ''
    
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
        headers = {'User-Agent': 'HKCarparkMonitor/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        address = data.get('address', {})
        
        # Extract district - try different fields
        district = address.get('suburb', '')  # Usually "Kwai Tsing District"
        if district:
            # Clean up - remove "District" suffix and Chinese characters
            district = district.split(' District')[0].strip()
            # Remove Chinese characters if present
            district = ''.join(c for c in district if ord(c) < 128).strip()
        
        # Fallback to town
        if not district:
            district = address.get('town', '')
            if district:
                district = ''.join(c for c in district if ord(c) < 128).strip()
        
        # Get region
        region = address.get('region', '')
        if region:
            region = ''.join(c for c in region if ord(c) < 128).strip()
        
        return region, district
        
    except Exception as e:
        print(f"  Error geocoding ({lat}, {lon}): {e}")
        return '', ''


def main():
    print("Loading Wilson carparks...")
    df = pd.read_csv(CARPARKS_FILE)
    print(f"Found {len(df)} carparks")
    
    # Add new columns
    df['region'] = ''
    df['district'] = ''
    
    print("\nGeocoding carparks (this may take a few minutes due to API rate limits)...")
    
    for idx, row in df.iterrows():
        lat = row.get('latitude')
        lon = row.get('longitude')
        name = row.get('name_en', row.get('id', ''))
        
        if pd.notna(lat) and pd.notna(lon):
            region, district = reverse_geocode(lat, lon)
            df.at[idx, 'region'] = region
            df.at[idx, 'district'] = district
            print(f"  [{idx+1}/{len(df)}] {name}: {district}, {region}")
            
            # Rate limit: Nominatim requires max 1 request per second
            time.sleep(1.1)
        else:
            print(f"  [{idx+1}/{len(df)}] {name}: No coordinates")
    
    # Save updated CSV
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to {OUTPUT_FILE}")
    
    # Also update the main carparks file
    df.to_csv(CARPARKS_FILE, index=False)
    print(f"Updated {CARPARKS_FILE}")
    
    # Show summary
    print("\n=== District Summary ===")
    district_counts = df['district'].value_counts()
    for district, count in district_counts.head(20).items():
        if district:
            print(f"  {district}: {count}")


if __name__ == "__main__":
    main()
