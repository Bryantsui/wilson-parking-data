#!/usr/bin/env python3
"""
Wilson Parking Scraper (Cloud Version)
======================================
Scrapes Wilson Parking API for real-time availability.
Note: Data is capped at "10+" for available spaces >= 10.
"""

import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import os

# Wilson Parking API
API_BASE_URL = "https://mobile-prod.wilsonparkingapp.com/"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "okhttp/4.9.0"
}

DATA_DIR = "data_wilson"
CARPARKS_FILE = os.path.join(DATA_DIR, "carparks.csv")
# Backup carparks file location
CARPARKS_BACKUP = "data/carparks_wilson.csv"
HKT = timezone(timedelta(hours=8))


def call_api(action, args={}):
    """Call Wilson Parking API"""
    payload = {"action": action, "args": args}
    response = requests.post(API_BASE_URL, headers=HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_district(address):
    """Extract district from address string"""
    if not address or not isinstance(address, str):
        return '', ''
    
    address_lower = address.lower()
    
    # Region detection
    if 'kowloon' in address_lower or any(x in address_lower for x in ['kwun tong', 'mong kok', 'tsim sha tsui', 'yau ma tei', 'sham shui po', 'wong tai sin', 'kowloon bay', 'kowloon city', 'kowloon tong', 'diamond hill', 'lok fu', 'ngau tau kok', 'san po kong', 'to kwa wan', 'hung hom', 'cheung sha wan', 'lai chi kok', 'mei foo']):
        region = 'Kowloon'
    elif any(x in address_lower for x in ['new territories', 'sha tin', 'tai po', 'yuen long', 'tuen mun', 'tsuen wan', 'kwai chung', 'tseung kwan o', 'ma on shan', 'sai kung', 'fanling', 'sheung shui', 'tin shui wai', 'tung chung', 'lantau']):
        region = 'New Territories'
    elif any(x in address_lower for x in ['hong kong', 'central', 'wan chai', 'causeway bay', 'north point', 'quarry bay', 'tai koo', 'shau kei wan', 'chai wan', 'kennedy town', 'sai ying pun', 'sheung wan', 'admiralty', 'tin hau', 'fortress hill', 'aberdeen', 'repulse bay', 'stanley', 'happy valley', 'mid-levels']):
        region = 'Hong Kong Island'
    else:
        region = ''
    
    # District detection
    district_map = {
        'Central': ['central', 'admiralty', 'sheung wan', 'mid-levels'],
        'Wan Chai': ['wan chai', 'causeway bay', 'happy valley', 'tin hau', 'fortress hill'],
        'Eastern': ['north point', 'quarry bay', 'tai koo', 'shau kei wan', 'chai wan', 'sai wan ho'],
        'Southern': ['aberdeen', 'repulse bay', 'stanley', 'ap lei chau', 'wong chuk hang'],
        'Yau Tsim Mong': ['tsim sha tsui', 'yau ma tei', 'mong kok', 'jordan', 'tai kok tsui'],
        'Sham Shui Po': ['sham shui po', 'cheung sha wan', 'lai chi kok', 'mei foo'],
        'Kowloon City': ['kowloon city', 'kowloon tong', 'ho man tin', 'hung hom', 'to kwa wan', 'ma tau wai'],
        'Wong Tai Sin': ['wong tai sin', 'diamond hill', 'lok fu', 'tsz wan shan', 'san po kong'],
        'Kwun Tong': ['kwun tong', 'ngau tau kok', 'kowloon bay', 'lam tin', 'yau tong', 'sau mau ping'],
        'Kwai Tsing': ['kwai chung', 'tsing yi', 'kwai fong'],
        'Tsuen Wan': ['tsuen wan'],
        'Tuen Mun': ['tuen mun'],
        'Yuen Long': ['yuen long', 'tin shui wai'],
        'North': ['fanling', 'sheung shui'],
        'Tai Po': ['tai po'],
        'Sha Tin': ['sha tin', 'ma on shan', 'fo tan'],
        'Sai Kung': ['sai kung', 'tseung kwan o', 'hang hau', 'po lam'],
        'Islands': ['tung chung', 'lantau', 'discovery bay'],
    }
    
    district = ''
    for dist_name, keywords in district_map.items():
        if any(kw in address_lower for kw in keywords):
            district = dist_name
            break
    
    return region, district


def load_carparks():
    """Load carparks from CSV with district extraction"""
    carparks = {}
    
    # Try main file first, then backup
    for filepath in [CARPARKS_FILE, CARPARKS_BACKUP]:
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath)
                # Handle different column names
                id_col = 'id' if 'id' in df.columns else 'carpark_id'
                name_col = 'name_en' if 'name_en' in df.columns else 'name'
                
                for _, row in df.iterrows():
                    cp_id = str(row[id_col])
                    address = row.get('address_en', '')
                    region, district = extract_district(address)
                    
                    carparks[cp_id] = {
                        'id': cp_id,
                        'name_en': row.get(name_col, row.get('name', '')),
                        'code': row.get('code', ''),
                        'address_en': address,
                        'region': region,
                        'district': district,
                    }
                print(f"Loaded {len(carparks)} Wilson carparks from {filepath}")
                break
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
                continue
    
    return carparks


def scrape_availability():
    """Scrape real-time availability from Wilson API"""
    now_hkt = datetime.now(HKT)
    scraped_at = now_hkt.isoformat()
    print(f"Scraping Wilson at {scraped_at}...")
    
    # Fetch availability
    response = call_api("carpark:available-bays", {"request": {}})
    
    # Handle response structure - Wilson API returns result.bays
    if 'result' in response:
        result = response['result']
        if 'bays' in result:
            availability_data = result['bays']
        elif 'data' in result:
            availability_data = result['data']
        else:
            print(f"Result keys: {list(result.keys())}")
            availability_data = []
    elif 'bays' in response:
        availability_data = response['bays']
    else:
        print(f"Unexpected response structure: {list(response.keys())}")
        availability_data = []
    
    print(f"Got {len(availability_data)} Wilson carparks")
    
    # Load carpark names
    carparks = load_carparks()
    
    # Process data
    rows = []
    stats = {'total': 0, 'capped': 0, 'full': 0}
    
    for item in availability_data:
        carpark_id = item.get('carpark_id', '')
        cp_info = carparks.get(carpark_id, {})
        
        guest_available = item.get('guest_available', 0)
        guest_display = item.get('guest_available_display', str(guest_available))
        
        stats['total'] += 1
        if guest_display == '10+':
            stats['capped'] += 1
        if guest_available == 0:
            stats['full'] += 1
        
        rows.append({
            'scraped_at': scraped_at,
            'carpark_id': carpark_id,
            'name': cp_info.get('name_en', ''),
            'guest_available': guest_available,
            'guest_available_display': guest_display,
            'guest_total': item.get('guest_total', ''),
            'monthly_available': item.get('monthly_available', ''),
            'monthly_is_full': item.get('monthly_is_full', ''),
            'monthly_total': item.get('monthly_total', ''),
            'total': item.get('total', ''),
            'total_available': item.get('total_available', ''),
            'last_update': item.get('last_update', ''),
        })
    
    df = pd.DataFrame(rows)
    
    # Save to daily CSV
    today = now_hkt.strftime('%Y-%m-%d')
    today_file = os.path.join(DATA_DIR, f"availability_{today}.csv")
    
    if not os.path.exists(today_file):
        df.to_csv(today_file, index=False)
    else:
        df.to_csv(today_file, mode='a', header=False, index=False)
    
    print(f"\n📊 Wilson Scrape Results:")
    print(f"   Total: {stats['total']} carparks")
    print(f"   Capped (10+): {stats['capped']}")
    print(f"   Full (0): {stats['full']}")
    print(f"   Saved to: {today_file}")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Copy carparks file to data_wilson if not exists
    if not os.path.exists(CARPARKS_FILE) and os.path.exists(CARPARKS_BACKUP):
        import shutil
        shutil.copy(CARPARKS_BACKUP, CARPARKS_FILE)
        print(f"Copied carparks from {CARPARKS_BACKUP}")
    
    scrape_availability()
