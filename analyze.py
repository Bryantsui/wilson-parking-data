#!/usr/bin/env python3
"""
Wilson Parking Data Analysis Utilities
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "wilson_parking.db"


def current_status(conn: sqlite3.Connection, limit: int = 20):
    """Show current availability status"""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("CURRENT PARKING AVAILABILITY")
    print("="*80)
    
    cursor.execute('''
        SELECT 
            c.name_en,
            a.guest_available,
            a.guest_available_display,
            a.guest_total,
            CASE 
                WHEN a.guest_total > 0 THEN 
                    ROUND((a.guest_total - a.guest_available) * 100.0 / a.guest_total, 1)
                ELSE 0 
            END as utilization_pct,
            a.guest_is_capped,
            a.scraped_at
        FROM availability_snapshots a
        JOIN carparks c ON a.carpark_id = c.id
        WHERE a.scraped_at = (SELECT MAX(scraped_at) FROM availability_snapshots)
        ORDER BY utilization_pct DESC
        LIMIT ?
    ''', (limit,))
    
    print(f"\n{'Carpark':<40} {'Avail':>6} {'Total':>6} {'Util%':>7} {'Status':<10}")
    print("-"*80)
    
    for row in cursor.fetchall():
        name = (row[0] or 'Unknown')[:38]
        status = "CAPPED" if row[5] else ("FULL" if row[1] == 0 else "OK")
        print(f"{name:<40} {row[2]:>6} {row[3]:>6} {row[4]:>6.1f}% {status:<10}")


def high_demand_analysis(conn: sqlite3.Connection, days: int = 7):
    """Analyze high-demand periods (when we have exact data)"""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print(f"HIGH DEMAND PERIODS (Last {days} days) - Exact data only")
    print("="*80)
    
    cursor.execute('''
        SELECT 
            c.name_en,
            strftime('%w', a.scraped_at) as day_of_week,
            strftime('%H', a.scraped_at) as hour,
            COUNT(*) as observations,
            AVG(a.guest_available) as avg_available,
            MIN(a.guest_available) as min_available,
            AVG(CASE WHEN a.guest_total > 0 THEN 
                (a.guest_total - a.guest_available) * 100.0 / a.guest_total 
                ELSE NULL END) as avg_utilization
        FROM availability_snapshots a
        JOIN carparks c ON a.carpark_id = c.id
        WHERE a.guest_is_capped = 0 
          AND a.guest_available < 10
          AND a.scraped_at > datetime('now', ?)
        GROUP BY c.name_en, day_of_week, hour
        HAVING observations >= 2
        ORDER BY avg_utilization DESC
        LIMIT 30
    ''', (f'-{days} days',))
    
    days_map = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    
    print(f"\n{'Carpark':<35} {'Day':<4} {'Hour':<5} {'Obs':>4} {'Avg':>5} {'Min':>4} {'Util%':>7}")
    print("-"*80)
    
    for row in cursor.fetchall():
        name = (row[0] or 'Unknown')[:33]
        day = days_map[int(row[1])]
        print(f"{name:<35} {day:<4} {row[2]}:00 {row[3]:>4} {row[4]:>5.1f} {row[5]:>4} {row[6]:>6.1f}%")


def carpark_profile(conn: sqlite3.Connection, carpark_name: str):
    """Show detailed profile for a specific carpark"""
    cursor = conn.cursor()
    
    # Find carpark
    cursor.execute('''
        SELECT id, name_en, address_en, guest_total, monthly_total
        FROM carparks 
        WHERE name_en LIKE ?
        LIMIT 1
    ''', (f'%{carpark_name}%',))
    
    carpark = cursor.fetchone()
    if not carpark:
        print(f"Carpark '{carpark_name}' not found")
        return
    
    carpark_id, name, address, guest_total, monthly_total = carpark
    
    print("\n" + "="*80)
    print(f"CARPARK PROFILE: {name}")
    print("="*80)
    print(f"Address: {address}")
    print(f"Guest Capacity: {guest_total}, Monthly Capacity: {monthly_total}")
    
    # Hourly pattern
    print("\n--- Hourly Availability Pattern (Last 7 days) ---")
    cursor.execute('''
        SELECT 
            strftime('%H', scraped_at) as hour,
            COUNT(*) as samples,
            AVG(guest_available) as avg_avail,
            MIN(guest_available) as min_avail,
            SUM(CASE WHEN guest_is_capped = 1 THEN 1 ELSE 0 END) as capped_count,
            SUM(CASE WHEN guest_available = 0 THEN 1 ELSE 0 END) as full_count
        FROM availability_snapshots
        WHERE carpark_id = ?
          AND scraped_at > datetime('now', '-7 days')
        GROUP BY hour
        ORDER BY hour
    ''', (carpark_id,))
    
    print(f"\n{'Hour':<6} {'Samples':>8} {'Avg Avail':>10} {'Min':>5} {'Times 10+':>10} {'Times Full':>11}")
    print("-"*60)
    
    for row in cursor.fetchall():
        print(f"{row[0]}:00  {row[1]:>8} {row[2]:>10.1f} {row[3]:>5} {row[4]:>10} {row[5]:>11}")


def data_quality(conn: sqlite3.Connection):
    """Show data collection statistics"""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("DATA QUALITY REPORT")
    print("="*80)
    
    cursor.execute('''
        SELECT 
            DATE(scraped_at) as date,
            COUNT(DISTINCT scraped_at) as scrapes,
            COUNT(*) as records,
            SUM(CASE WHEN guest_is_capped = 1 THEN 1 ELSE 0 END) as capped,
            SUM(CASE WHEN guest_available = 0 THEN 1 ELSE 0 END) as full
        FROM availability_snapshots
        GROUP BY date
        ORDER BY date DESC
        LIMIT 14
    ''')
    
    print(f"\n{'Date':<12} {'Scrapes':>8} {'Records':>10} {'Capped (10+)':>13} {'Full':>8}")
    print("-"*60)
    
    for row in cursor.fetchall():
        print(f"{row[0]:<12} {row[1]:>8} {row[2]:>10} {row[3]:>13} {row[4]:>8}")
    
    # Coverage gaps
    print("\n--- Data Coverage ---")
    cursor.execute('''
        SELECT MIN(scraped_at), MAX(scraped_at), COUNT(DISTINCT scraped_at)
        FROM availability_snapshots
    ''')
    first, last, total = cursor.fetchone()
    print(f"First scrape: {first}")
    print(f"Last scrape: {last}")
    print(f"Total scrape events: {total}")


def export_csv(conn: sqlite3.Connection, output_file: str, days: int = 7):
    """Export recent data to CSV for external analysis"""
    import csv
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            a.scraped_at,
            c.name_en,
            c.address_en,
            a.guest_available,
            a.guest_available_display,
            a.guest_total,
            a.guest_is_capped,
            a.monthly_available,
            a.monthly_total,
            a.total_available,
            a.total_capacity
        FROM availability_snapshots a
        JOIN carparks c ON a.carpark_id = c.id
        WHERE a.scraped_at > datetime('now', ?)
        ORDER BY a.scraped_at, c.name_en
    ''', (f'-{days} days',))
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'scraped_at', 'carpark_name', 'address', 
            'guest_available', 'guest_display', 'guest_total', 'is_capped',
            'monthly_available', 'monthly_total',
            'total_available', 'total_capacity'
        ])
        writer.writerows(cursor.fetchall())
    
    print(f"Exported to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Wilson Parking Analysis')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--demand', action='store_true', help='High demand analysis')
    parser.add_argument('--profile', type=str, help='Carpark profile by name')
    parser.add_argument('--quality', action='store_true', help='Data quality report')
    parser.add_argument('--export', type=str, help='Export to CSV file')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze')
    parser.add_argument('--db', type=str, default=str(DB_PATH), help='Database path')
    args = parser.parse_args()
    
    conn = sqlite3.connect(args.db)
    
    try:
        if args.status:
            current_status(conn)
        elif args.demand:
            high_demand_analysis(conn, args.days)
        elif args.profile:
            carpark_profile(conn, args.profile)
        elif args.quality:
            data_quality(conn)
        elif args.export:
            export_csv(conn, args.export, args.days)
        else:
            # Default: show status
            current_status(conn)
            
    finally:
        conn.close()


if __name__ == '__main__':
    main()
