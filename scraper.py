#!/usr/bin/env python3
"""
Wilson Parking Availability Scraper
Collects parking data every 30 minutes for utilization analysis
"""

import json
import sqlite3
import urllib.request
import argparse
from datetime import datetime
from pathlib import Path

API_URL = "https://mobile-prod.wilsonparkingapp.com/"
DB_PATH = Path(__file__).parent / "wilson_parking.db"


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


def init_carparks(conn: sqlite3.Connection):
    """Fetch and store carpark metadata"""
    print("Fetching carpark metadata...")
    
    data = api_call("carpark:query")
    carparks = data.get('result', {}).get('carparks', [])
    
    cursor = conn.cursor()
    for cp in carparks:
        name = cp.get('name', {})
        address = cp.get('address', {})
        
        cursor.execute('''
            INSERT OR REPLACE INTO carparks 
            (id, name_en, name_zh, address_en, address_zh, district_id, 
             latitude, longitude, height_limit, has_ev_charging, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            cp.get('id'),
            name.get('en_us'),
            name.get('zh_hant'),
            address.get('en_us'),
            address.get('zh_hant'),
            cp.get('district_id'),
            cp.get('latitude'),
            cp.get('longitude'),
            cp.get('height_limit'),
            bool(cp.get('ev_charging'))
        ))
    
    conn.commit()
    print(f"Stored {len(carparks)} carparks")


def scrape_availability(conn: sqlite3.Connection):
    """Scrape current availability and store"""
    scraped_at = datetime.utcnow().isoformat() + 'Z'
    
    print(f"Scraping availability at {scraped_at}...")
    
    data = api_call("carpark:available-bays")
    result = data.get('result', {})
    bays = result.get('bays', [])
    
    cursor = conn.cursor()
    inserted = 0
    
    for bay in bays:
        carpark_id = bay.get('carpark_id')
        guest_avail = bay.get('guest_available')
        guest_display = bay.get('guest_available_display', '')
        
        # Detect if capped at 10
        is_capped = guest_display.endswith('+') if guest_display else False
        
        cursor.execute('''
            INSERT INTO availability_snapshots 
            (carpark_id, scraped_at, last_update, 
             guest_available, guest_available_display, guest_total, guest_is_capped,
             monthly_available, monthly_total, monthly_is_full,
             total_available, total_capacity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            carpark_id,
            scraped_at,
            bay.get('last_update'),
            guest_avail,
            guest_display,
            bay.get('guest_total'),
            is_capped,
            bay.get('monthly_available'),
            bay.get('monthly_total'),
            bay.get('monthly_is_full'),
            bay.get('total_available'),
            bay.get('total')
        ))
        inserted += 1
        
        # Update carpark totals if available
        if bay.get('guest_total') or bay.get('monthly_total'):
            cursor.execute('''
                UPDATE carparks 
                SET guest_total = COALESCE(?, guest_total),
                    monthly_total = COALESCE(?, monthly_total),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (bay.get('guest_total'), bay.get('monthly_total'), carpark_id))
    
    conn.commit()
    print(f"Inserted {inserted} availability records")
    
    # Quick stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN guest_is_capped = 1 THEN 1 ELSE 0 END) as capped,
            SUM(CASE WHEN guest_available = 0 THEN 1 ELSE 0 END) as full
        FROM availability_snapshots 
        WHERE scraped_at = ?
    ''', (scraped_at,))
    
    row = cursor.fetchone()
    print(f"Stats: {row[0]} carparks, {row[1]} showing 10+, {row[2]} completely full")


def aggregate_hourly(conn: sqlite3.Connection):
    """Aggregate data into hourly stats for faster queries"""
    print("Aggregating hourly stats...")
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO daily_stats 
        (carpark_id, date, hour, min_guest_available, max_guest_available, 
         avg_guest_available, samples_at_capacity, total_samples, 
         avg_utilization_pct, peak_utilization_pct)
        SELECT 
            carpark_id,
            DATE(scraped_at) as date,
            CAST(strftime('%H', scraped_at) AS INTEGER) as hour,
            MIN(guest_available),
            MAX(guest_available),
            AVG(guest_available),
            SUM(CASE WHEN guest_is_capped = 1 THEN 1 ELSE 0 END),
            COUNT(*),
            AVG(CASE WHEN guest_total > 0 THEN 
                (guest_total - guest_available) * 100.0 / guest_total 
                ELSE NULL END),
            MAX(CASE WHEN guest_total > 0 THEN 
                (guest_total - guest_available) * 100.0 / guest_total 
                ELSE NULL END)
        FROM availability_snapshots
        WHERE DATE(scraped_at) = DATE('now')
        GROUP BY carpark_id, DATE(scraped_at), CAST(strftime('%H', scraped_at) AS INTEGER)
    ''')
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Wilson Parking Scraper')
    parser.add_argument('--init', action='store_true', help='Initialize carpark metadata')
    parser.add_argument('--aggregate', action='store_true', help='Run hourly aggregation')
    parser.add_argument('--db', type=str, default=str(DB_PATH), help='Database path')
    args = parser.parse_args()
    
    conn = sqlite3.connect(args.db)
    
    try:
        if args.init:
            init_carparks(conn)
        
        scrape_availability(conn)
        
        if args.aggregate:
            aggregate_hourly(conn)
            
    finally:
        conn.close()


if __name__ == '__main__':
    main()
