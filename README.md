# Wilson Parking Data Collection System

## Overview
This system collects parking availability data from Wilson Parking HK every 30 minutes for utilization analysis.

## ⚠️ Data Limitation
The API **truncates availability to 10** when there are more spots available:
- Values < 10: Exact count available
- Values ≥ 10: Shows as "10" (displayed as "10+")

This means you get precise data only during **high-demand periods**.

## Database Schema
Uses SQLite for simplicity. See `schema.sql` for details.

## Files
- `schema.sql` - Database schema
- `scraper.py` - Main scraper script
- `analyze.py` - Analysis utilities
- `run_scraper.sh` - Cron wrapper script

## Setup

```bash
# 1. Create database
sqlite3 wilson_parking.db < schema.sql

# 2. Initial carpark metadata fetch
python3 scraper.py --init

# 3. Test scrape
python3 scraper.py

# 4. Setup cron (every 30 minutes)
crontab -e
# Add: */30 * * * * /Users/bryan/wilson_parking_scraper/run_scraper.sh
```

## API Endpoints Used
- `carpark:available-bays` - Real-time availability
- `carpark:query` - Carpark metadata (name, address, etc.)
