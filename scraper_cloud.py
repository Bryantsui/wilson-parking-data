#!/usr/bin/env python3
"""
Wilson Parking Cloud Scraper - CSV Storage
Stores data as CSV files (one per day)
"""

import json
import csv
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://mobile-prod.wilsonparkingapp.com/"
DATA_DIR = Path(__file__).parent / "data"


def api_call(action: str, args: dict = None) -> dict:
    """Make API call to Wilson Parking"""
    payload = {
        "action": action,
        "args": {"request": args or {}}
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'WilsonParkingScraper/1.0'
        },
        method='POST'
    )
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def scrape_and_store():
    """Scrape availability and append to daily CSV"""
    now = datetime.now(timezone.utc)
    scraped_at = now.isoformat()
    date_str = now.strftime('%Y-%m-%d')
    
    print(f"Scraping at {scraped_at}...")
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # Fetch availability
    data = api_call("carpark:available-bays")
    bays = data.get('result', {}).get('bays', [])
    print(f"Got {len(bays)} carparks")
    
    # Daily CSV file
    csv_file = DATA_DIR / f"availability_{date_str}.csv"
    file_exists = csv_file.exists()
    
    # Write to CSV
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Header for new files
        if not file_exists:
            writer.writerow([
                'scraped_at', 'carpark_id', 'guest_available', 'guest_display',
                'guest_total', 'is_capped', 'monthly_available', 'monthly_total',
                'total_available', 'total_capacity', 'last_update'
            ])
        
        # Data rows
        for bay in bays:
            guest_display = bay.get('guest_available_display', '')
            is_capped = 1 if guest_display.endswith('+') else 0
            
            writer.writerow([
                scraped_at,
                bay.get('carpark_id'),
                bay.get('guest_available'),
                guest_display,
                bay.get('guest_total'),
                is_capped,
                bay.get('monthly_available'),
                bay.get('monthly_total'),
                bay.get('total_available'),
                bay.get('total'),
                bay.get('last_update')
            ])
    
    # Stats
    capped = sum(1 for b in bays if str(b.get('guest_available_display', '')).endswith('+'))
    full = sum(1 for b in bays if b.get('guest_available') == 0)
    print(f"Stats: {len(bays)} carparks, {capped} at 10+, {full} full")
    print(f"Saved to {csv_file}")


def init_carparks():
    """Save carpark metadata once"""
    print("Fetching carpark metadata...")
    
    DATA_DIR.mkdir(exist_ok=True)
    
    data = api_call("carpark:query")
    carparks = data.get('result', {}).get('carparks', [])
    
    csv_file = DATA_DIR / "carparks.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'id', 'name_en', 'name_zh', 'address_en', 'address_zh',
            'district_id', 'latitude', 'longitude', 'height_limit', 'has_ev'
        ])
        
        for cp in carparks:
            name = cp.get('name', {})
            address = cp.get('address', {})
            writer.writerow([
                cp.get('id'),
                name.get('en_us'),
                name.get('zh_hant'),
                address.get('en_us'),
                address.get('zh_hant'),
                cp.get('district_id'),
                cp.get('latitude'),
                cp.get('longitude'),
                cp.get('height_limit'),
                1 if cp.get('ev_charging') else 0
            ])
    
    print(f"Saved {len(carparks)} carparks to {csv_file}")


if __name__ == '__main__':
    import sys
    
    if '--init' in sys.argv:
        init_carparks()
    
    scrape_and_store()
