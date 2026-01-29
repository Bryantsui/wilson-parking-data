#!/usr/bin/env python3
"""
HK Carpark Vacancy Scraper (Cloud Version)
==========================================
Uses the official HK Government Open Data API.
Runs on GitHub Actions every 30 minutes.
"""

import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import os

# HK Government Open Data API
INFO_API = "https://api.data.gov.hk/v1/carpark-info-vacancy?data=info&lang=en_US"
VACANCY_API = "https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US"

DATA_DIR = "data"
CARPARKS_FILE = os.path.join(DATA_DIR, "carparks.csv")
HKT = timezone(timedelta(hours=8))


def fetch_carpark_info():
    """Fetch carpark metadata"""
    print("Fetching carpark info from DATA.GOV.HK...")
    response = requests.get(INFO_API, timeout=30)
    response.raise_for_status()
    data = response.json()
    results = data.get('results', [])
    print(f"Got {len(results)} carparks")
    return {r['park_Id']: r for r in results}


def fetch_and_save_carparks():
    """Save carpark metadata to CSV"""
    carparks = fetch_carpark_info()
    
    rows = []
    for pid, cp in carparks.items():
        height = ''
        if cp.get('heightLimits'):
            h = cp['heightLimits'][0]
            height = h.get('height', '')
        
        rows.append({
            'park_id': pid,
            'name_en': cp.get('name', ''),
            'address_en': cp.get('displayAddress', ''),
            'district': cp.get('district', ''),
            'latitude': cp.get('latitude', ''),
            'longitude': cp.get('longitude', ''),
            'height_limit': height,
            'opening_status': cp.get('opening_status', ''),
            'website': cp.get('website', ''),
            'phone': cp.get('contactNo', '')
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(CARPARKS_FILE, index=False)
    print(f"Saved {len(rows)} carparks to {CARPARKS_FILE}")
    return carparks


def load_carparks():
    """Load carparks from CSV"""
    carparks = {}
    if os.path.exists(CARPARKS_FILE):
        df = pd.read_csv(CARPARKS_FILE)
        for _, row in df.iterrows():
            carparks[str(row['park_id'])] = row.to_dict()
    return carparks


def scrape_availability():
    """Scrape real-time vacancy data"""
    now_hkt = datetime.now(HKT)
    scraped_at = now_hkt.isoformat()
    print(f"Scraping at {scraped_at}...")
    
    # Fetch vacancy
    response = requests.get(VACANCY_API, timeout=30)
    response.raise_for_status()
    data = response.json()
    vacancy_data = data.get('results', [])
    print(f"Got {len(vacancy_data)} vacancy records")
    
    # Load carpark names
    carparks = load_carparks()
    
    # Process data
    rows = []
    stats = {'total': 0, 'full': 0, 'low': 0}
    
    for v in vacancy_data:
        park_id = v.get('park_Id', '')
        cp_info = carparks.get(str(park_id), {})
        
        # Get private car vacancy
        private_car = v.get('privateCar', [{}])
        if isinstance(private_car, list) and private_car:
            pc = private_car[0]
        else:
            pc = private_car if isinstance(private_car, dict) else {}
        
        vacancy = pc.get('vacancy')
        last_update = pc.get('lastupdate', '')
        
        # Get motorcycle vacancy
        motorcycle = v.get('motorCycle', [{}])
        if isinstance(motorcycle, list) and motorcycle:
            mc = motorcycle[0]
        else:
            mc = motorcycle if isinstance(motorcycle, dict) else {}
        mc_vacancy = mc.get('vacancy')
        
        # Get LGV vacancy
        lgv = v.get('LGV', [{}])
        if isinstance(lgv, list) and lgv:
            lgv_data = lgv[0]
        else:
            lgv_data = lgv if isinstance(lgv, dict) else {}
        lgv_vacancy = lgv_data.get('vacancy')
        
        if vacancy is not None:
            stats['total'] += 1
            if vacancy == 0:
                stats['full'] += 1
            elif vacancy <= 5:
                stats['low'] += 1
        
        rows.append({
            'scraped_at': scraped_at,
            'park_id': park_id,
            'name': cp_info.get('name_en', ''),
            'district': cp_info.get('district', ''),
            'private_car_vacancy': vacancy if vacancy is not None else '',
            'motorcycle_vacancy': mc_vacancy if mc_vacancy is not None else '',
            'lgv_vacancy': lgv_vacancy if lgv_vacancy is not None else '',
            'last_update': last_update,
            'opening_status': cp_info.get('opening_status', '')
        })
    
    df = pd.DataFrame(rows)
    
    # Save to daily CSV
    today = now_hkt.strftime('%Y-%m-%d')
    today_file = os.path.join(DATA_DIR, f"vacancy_{today}.csv")
    
    if not os.path.exists(today_file):
        df.to_csv(today_file, index=False)
    else:
        df.to_csv(today_file, mode='a', header=False, index=False)
    
    print(f"\n📊 Scrape Results:")
    print(f"   Total: {stats['total']} carparks")
    print(f"   Full (0): {stats['full']}")
    print(f"   Low (1-5): {stats['low']}")
    print(f"   Saved to: {today_file}")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Refresh carpark metadata if not exists or if it's Monday (weekly refresh)
    now = datetime.now(HKT)
    if not os.path.exists(CARPARKS_FILE) or now.weekday() == 0:
        fetch_and_save_carparks()
    
    scrape_availability()
