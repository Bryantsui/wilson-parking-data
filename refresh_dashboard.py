#!/usr/bin/env python3
"""
Dashboard Data Generator for HK Government Carpark Data
"""

import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import glob

HKT = timezone(timedelta(hours=8))
DATA_DIR = "data"


def to_hkt(iso_string):
    """Convert ISO timestamp to HKT"""
    try:
        if '+' in iso_string:
            dt = datetime.fromisoformat(iso_string)
        else:
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.astimezone(HKT)
    except:
        return None


def load_carparks():
    """Load carpark metadata"""
    carparks = {}
    filepath = os.path.join(DATA_DIR, "carparks.csv")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                pid = row.get('park_id', '')
                carparks[pid] = {
                    'name': row.get('name_en', ''),
                    'address': row.get('address_en', ''),
                    'district': row.get('district', ''),
                    'latitude': row.get('latitude', ''),
                    'longitude': row.get('longitude', '')
                }
    return carparks


def load_all_vacancy():
    """Load all vacancy data files"""
    records = []
    pattern = os.path.join(DATA_DIR, "vacancy_*.csv")
    files = sorted(glob.glob(pattern))
    
    for filepath in files:
        with open(filepath, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                records.append(row)
    
    return records


def main():
    print("Generating dashboard data...")
    
    carparks = load_carparks()
    print(f"Loaded {len(carparks)} carparks")
    
    records = load_all_vacancy()
    print(f"Loaded {len(records)} vacancy records")
    
    if not records:
        print("No data found!")
        return
    
    # Get latest record per carpark
    latest = {}
    for row in records:
        park_id = row.get('park_id', '')
        scraped_at = row.get('scraped_at', '')
        if park_id not in latest or scraped_at > latest[park_id]['scraped_at']:
            latest[park_id] = row
    
    # Build time series
    timeseries = defaultdict(list)
    for row in records:
        park_id = row.get('park_id', '')
        try:
            hkt_time = to_hkt(row['scraped_at'])
            if not hkt_time:
                continue
            
            vacancy = row.get('private_car_vacancy', '')
            vacancy = int(vacancy) if vacancy else None
            
            timeseries[park_id].append({
                'time': hkt_time.strftime('%m-%d %H:%M'),
                'time_raw': row['scraped_at'],
                'vacancy': vacancy
            })
        except:
            pass
    
    # Build current stats
    current_stats = []
    for park_id, data in latest.items():
        cp_info = carparks.get(park_id, {})
        name = cp_info.get('name', '') or data.get('name', '')
        if not name:
            name = f"Carpark {park_id}"
        
        try:
            vacancy = data.get('private_car_vacancy', '')
            vacancy = int(vacancy) if vacancy else None
            
            # Status
            if vacancy is None:
                status = 'NO_DATA'
            elif vacancy == 0:
                status = 'FULL'
            elif vacancy <= 5:
                status = 'LOW'
            elif vacancy <= 20:
                status = 'MODERATE'
            else:
                status = 'OK'
            
            current_stats.append({
                'id': park_id,
                'name': name,
                'district': data.get('district', cp_info.get('district', '')),
                'vacancy': vacancy,
                'motorcycle_vacancy': data.get('motorcycle_vacancy', ''),
                'lgv_vacancy': data.get('lgv_vacancy', ''),
                'last_update': data.get('last_update', ''),
                'opening_status': data.get('opening_status', ''),
                'status': status
            })
        except Exception as e:
            pass
    
    # Sort by vacancy (ascending - fullest first)
    current_stats.sort(key=lambda x: (x['vacancy'] is None, x['vacancy'] if x['vacancy'] else 999))
    
    # Get last scrape time
    last_update_raw = max(row['scraped_at'] for row in records) if records else 'N/A'
    last_update_hkt = to_hkt(last_update_raw)
    last_update_display = last_update_hkt.strftime('%Y-%m-%d %H:%M HKT') if last_update_hkt else last_update_raw
    
    # Summary
    summary = {
        'total_carparks': len(current_stats),
        'full_count': sum(1 for s in current_stats if s['status'] == 'FULL'),
        'low_count': sum(1 for s in current_stats if s['status'] == 'LOW'),
        'moderate_count': sum(1 for s in current_stats if s['status'] == 'MODERATE'),
        'ok_count': sum(1 for s in current_stats if s['status'] == 'OK'),
        'data_points': len(records),
        'last_update': last_update_display,
        'last_update_utc': last_update_raw,
        'data_source': 'HK Government Open Data (DATA.GOV.HK)'
    }
    
    # Output
    dashboard_data = {
        'carparks': carparks,
        'current_stats': current_stats,
        'timeseries': {k: v for k, v in timeseries.items()},
        'summary': summary
    }
    
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(dashboard_data, f, ensure_ascii=False)
    
    print(f"\n✅ Dashboard data generated:")
    print(f"   Total carparks: {summary['total_carparks']}")
    print(f"   Full: {summary['full_count']}")
    print(f"   Low (1-5): {summary['low_count']}")
    print(f"   Moderate (6-20): {summary['moderate_count']}")
    print(f"   OK (>20): {summary['ok_count']}")
    print(f"   Last update: {last_update_display}")


if __name__ == '__main__':
    main()
