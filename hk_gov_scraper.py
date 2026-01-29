#!/usr/bin/env python3
"""
HK Government Open Data Carpark Scraper
========================================
This uses the official DATA.GOV.HK API which provides REAL vacancy numbers
(no capping at 10+).

API Documentation: https://data.gov.hk/en-data/dataset/hk-td-tis_3-carpark-info-vacancy
"""

import requests
import json
import csv
import os
from datetime import datetime, timezone, timedelta

# API Endpoints
INFO_API = "https://api.data.gov.hk/v1/carpark-info-vacancy?data=info&lang=en_US"
VACANCY_API = "https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US"

DATA_DIR = "data_gov"
HKT = timezone(timedelta(hours=8))


def fetch_carpark_info():
    """Fetch carpark metadata (name, address, location)"""
    print("Fetching carpark info...")
    response = requests.get(INFO_API, timeout=30)
    response.raise_for_status()
    data = response.json()
    results = data.get('results', [])
    print(f"  Got {len(results)} carparks")
    return {r['park_Id']: r for r in results}


def fetch_vacancy():
    """Fetch real-time vacancy data"""
    print("Fetching vacancy data...")
    response = requests.get(VACANCY_API, timeout=30)
    response.raise_for_status()
    data = response.json()
    results = data.get('results', [])
    print(f"  Got {len(results)} vacancy records")
    return results


def save_carparks(carparks):
    """Save carpark info to CSV"""
    filepath = os.path.join(DATA_DIR, "carparks_gov.csv")
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['park_id', 'name', 'address', 'district', 'latitude', 'longitude', 
                     'height_limit', 'opening_status', 'website', 'phone']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for pid, cp in carparks.items():
            height = ''
            if cp.get('heightLimits'):
                h = cp['heightLimits'][0]
                height = h.get('height', '')
            
            writer.writerow({
                'park_id': pid,
                'name': cp.get('name', ''),
                'address': cp.get('displayAddress', ''),
                'district': cp.get('district', ''),
                'latitude': cp.get('latitude', ''),
                'longitude': cp.get('longitude', ''),
                'height_limit': height,
                'opening_status': cp.get('opening_status', ''),
                'website': cp.get('website', ''),
                'phone': cp.get('contactNo', '')
            })
    
    print(f"  Saved {len(carparks)} carparks to {filepath}")


def scrape_vacancy(carparks):
    """Scrape and save vacancy data"""
    now_hkt = datetime.now(HKT)
    scraped_at = now_hkt.isoformat()
    
    vacancy_data = fetch_vacancy()
    
    # Prepare data
    rows = []
    stats = {'total': 0, 'with_vacancy': 0, 'full': 0}
    
    for v in vacancy_data:
        park_id = v.get('park_Id', '')
        cp_info = carparks.get(park_id, {})
        
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
            stats['with_vacancy'] += 1
            if vacancy == 0:
                stats['full'] += 1
        
        rows.append({
            'scraped_at': scraped_at,
            'park_id': park_id,
            'name': cp_info.get('name', ''),
            'district': cp_info.get('district', ''),
            'private_car_vacancy': vacancy if vacancy is not None else '',
            'motorcycle_vacancy': mc_vacancy if mc_vacancy is not None else '',
            'lgv_vacancy': lgv_vacancy if lgv_vacancy is not None else '',
            'last_update': last_update,
            'opening_status': cp_info.get('opening_status', '')
        })
    
    # Save to daily CSV
    today = now_hkt.strftime('%Y-%m-%d')
    filepath = os.path.join(DATA_DIR, f"vacancy_{today}.csv")
    
    file_exists = os.path.exists(filepath)
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        fieldnames = ['scraped_at', 'park_id', 'name', 'district', 
                     'private_car_vacancy', 'motorcycle_vacancy', 'lgv_vacancy',
                     'last_update', 'opening_status']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n📊 Scrape Results ({now_hkt.strftime('%Y-%m-%d %H:%M HKT')}):")
    print(f"   Total carparks: {stats['total']}")
    print(f"   With vacancy data: {stats['with_vacancy']}")
    print(f"   Full (0 spaces): {stats['full']}")
    print(f"   Saved to: {filepath}")
    
    return rows


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Fetch and save carpark info (once)
    carparks_file = os.path.join(DATA_DIR, "carparks_gov.csv")
    if not os.path.exists(carparks_file):
        carparks = fetch_carpark_info()
        save_carparks(carparks)
    else:
        # Load existing
        carparks = {}
        with open(carparks_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                carparks[row['park_id']] = row
        print(f"Loaded {len(carparks)} carparks from cache")
    
    # Scrape vacancy
    scrape_vacancy(carparks)


if __name__ == '__main__':
    main()
