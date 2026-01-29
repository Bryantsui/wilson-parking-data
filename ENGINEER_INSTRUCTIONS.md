# HK Carpark Vacancy Scraper - Engineer Instructions

## Overview

This document describes how to scrape real-time parking vacancy data from the Hong Kong Government Open Data API (DATA.GOV.HK).

**Data Source:** Transport Department, HKSAR Government  
**Update Frequency:** Real-time (carparks update every few minutes)  
**Recommended Scrape Interval:** Every 5 minutes  
**Total Carparks:** ~542

---

## API Endpoints

### 1. Carpark Info (Metadata) - Run Once Daily

```
GET https://api.data.gov.hk/v1/carpark-info-vacancy?data=info&lang=en_US
```

**Response Example:**
```json
{
  "results": [
    {
      "park_Id": "tdc17p3",
      "name": "West Gate Open Car Park",
      "displayAddress": "Project Site Office, WKCD, Kowloon",
      "district": "Yau Tsim Mong",
      "latitude": 22.30314788,
      "longitude": 114.15550327,
      "contactNo": "22000367",
      "website": "https://www.westk.hk/en/visit/parking",
      "opening_status": "OPEN",
      "heightLimits": [
        {
          "height": 2.45,
          "remark": "Height Limit: 2.45m\nHourly Rate: $25/hr weekdays..."
        }
      ],
      "renditionUrls": {
        "carpark_photo": "http://resource.data.one.gov.hk/td/carpark/tdc17p3.jpg"
      },
      "lang": "en_US"
    }
  ]
}
```

### 2. Real-Time Vacancy - Scrape Every 5 Minutes

```
GET https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US
```

**Response Example:**
```json
{
  "results": [
    {
      "park_Id": "27",
      "privateCar": [
        {
          "vacancy_type": "A",
          "vacancy": 34,
          "vacancyDIS": 2,
          "lastupdate": "2026-01-29 14:22:30"
        }
      ],
      "motorCycle": [
        {
          "vacancy_type": "A",
          "vacancy": 5,
          "lastupdate": "2026-01-29 14:22:30"
        }
      ],
      "LGV": [
        {
          "vacancy_type": "A",
          "vacancy": 10,
          "lastupdate": "2026-01-29 14:22:30"
        }
      ]
    }
  ]
}
```

---

## Data Fields Reference

### Carpark Info Fields

| Field | Type | Description |
|-------|------|-------------|
| `park_Id` | string | Unique identifier (e.g., "27", "tdc17p3") |
| `name` | string | Carpark name in English |
| `displayAddress` | string | Full street address |
| `district` | string | HK District (18 districts) |
| `latitude` | float | GPS latitude |
| `longitude` | float | GPS longitude |
| `contactNo` | string | Phone number |
| `website` | string | Website URL |
| `opening_status` | string | "OPEN" or "CLOSED" |
| `heightLimits` | array | Height restrictions and parking rates |
| `renditionUrls.carpark_photo` | string | Photo URL |

### Vacancy Fields

| Field | Type | Description |
|-------|------|-------------|
| `park_Id` | string | Links to carpark info |
| `privateCar` | array | Private car vacancy data |
| `motorCycle` | array | Motorcycle vacancy data |
| `LGV` | array | Light Goods Vehicle vacancy |
| `HGV` | array | Heavy Goods Vehicle vacancy |
| `coach` | array | Bus/Coach vacancy |

### Vacancy Sub-fields (inside each vehicle type)

| Field | Type | Description |
|-------|------|-------------|
| `vacancy` | int | **Number of available spaces** |
| `vacancy_type` | string | "A" = Available, "N" = No info, "F" = Full |
| `vacancyDIS` | int | Disability parking spaces available |
| `lastupdate` | string | Timestamp from carpark system (HKT) |

---

## Sample Python Scraper

```python
#!/usr/bin/env python3
"""
HK Carpark Vacancy Scraper
Scrapes every 5 minutes and stores to database/CSV
"""

import requests
import json
from datetime import datetime, timezone, timedelta
import time

# API Endpoints
INFO_API = "https://api.data.gov.hk/v1/carpark-info-vacancy?data=info&lang=en_US"
VACANCY_API = "https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US"

# Hong Kong Timezone
HKT = timezone(timedelta(hours=8))


def fetch_carpark_info():
    """Fetch carpark metadata (run once daily)"""
    response = requests.get(INFO_API, timeout=30)
    response.raise_for_status()
    return response.json().get('results', [])


def fetch_vacancy():
    """Fetch real-time vacancy (run every 5 minutes)"""
    response = requests.get(VACANCY_API, timeout=30)
    response.raise_for_status()
    return response.json().get('results', [])


def parse_vacancy(vacancy_data):
    """Parse vacancy response into flat records"""
    records = []
    scraped_at = datetime.now(HKT).isoformat()
    
    for v in vacancy_data:
        park_id = v.get('park_Id', '')
        
        # Extract private car vacancy
        private_car = v.get('privateCar', [{}])
        pc = private_car[0] if isinstance(private_car, list) and private_car else {}
        
        # Extract motorcycle vacancy
        motorcycle = v.get('motorCycle', [{}])
        mc = motorcycle[0] if isinstance(motorcycle, list) and motorcycle else {}
        
        # Extract LGV vacancy
        lgv = v.get('LGV', [{}])
        lgv_data = lgv[0] if isinstance(lgv, list) and lgv else {}
        
        records.append({
            'scraped_at': scraped_at,
            'park_id': park_id,
            'private_car_vacancy': pc.get('vacancy'),
            'private_car_vacancy_type': pc.get('vacancy_type'),
            'private_car_disability': pc.get('vacancyDIS'),
            'private_car_lastupdate': pc.get('lastupdate'),
            'motorcycle_vacancy': mc.get('vacancy'),
            'lgv_vacancy': lgv_data.get('vacancy'),
        })
    
    return records


def main():
    """Main scraping loop"""
    print("Starting HK Carpark Vacancy Scraper...")
    print(f"Scraping {VACANCY_API}")
    print("Interval: Every 5 minutes")
    print("-" * 50)
    
    while True:
        try:
            # Fetch vacancy data
            vacancy_data = fetch_vacancy()
            records = parse_vacancy(vacancy_data)
            
            # Calculate stats
            total = len(records)
            full = sum(1 for r in records if r['private_car_vacancy'] == 0)
            low = sum(1 for r in records if r['private_car_vacancy'] and 0 < r['private_car_vacancy'] <= 5)
            
            now = datetime.now(HKT).strftime('%Y-%m-%d %H:%M:%S HKT')
            print(f"[{now}] Scraped {total} carparks | Full: {full} | Low: {low}")
            
            # TODO: Save records to your database here
            # save_to_database(records)
            
        except Exception as e:
            print(f"Error: {e}")
        
        # Wait 5 minutes
        time.sleep(300)


if __name__ == '__main__':
    main()
```

---

## cURL Examples

### Fetch Vacancy Data
```bash
curl -s "https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US" | jq .
```

### Fetch Carpark Info
```bash
curl -s "https://api.data.gov.hk/v1/carpark-info-vacancy?data=info&lang=en_US" | jq .
```

### Quick Test (First 3 Carparks)
```bash
curl -s "https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US" | jq '.results[:3]'
```

---

## Database Schema (Suggested)

### PostgreSQL / MySQL

```sql
-- Carpark metadata table (update daily)
CREATE TABLE carparks (
    park_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255),
    address TEXT,
    district VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    phone VARCHAR(50),
    website VARCHAR(500),
    opening_status VARCHAR(20),
    height_limit DECIMAL(4, 2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vacancy records table (insert every 5 minutes)
CREATE TABLE vacancy_records (
    id BIGSERIAL PRIMARY KEY,
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL,
    park_id VARCHAR(50) NOT NULL,
    private_car_vacancy INTEGER,
    private_car_vacancy_type VARCHAR(5),
    private_car_disability INTEGER,
    private_car_lastupdate TIMESTAMP,
    motorcycle_vacancy INTEGER,
    lgv_vacancy INTEGER,
    
    INDEX idx_scraped_at (scraped_at),
    INDEX idx_park_id (park_id),
    INDEX idx_park_scraped (park_id, scraped_at)
);

-- Create hypertable if using TimescaleDB (recommended for time-series)
-- SELECT create_hypertable('vacancy_records', 'scraped_at');
```

---

## Deployment Options

### Option 1: Cron Job (Simple)
```bash
# Add to crontab -e
*/5 * * * * /usr/bin/python3 /path/to/scraper.py >> /var/log/carpark_scraper.log 2>&1
```

### Option 2: Systemd Service (Recommended)
```ini
# /etc/systemd/system/carpark-scraper.service
[Unit]
Description=HK Carpark Vacancy Scraper
After=network.target

[Service]
Type=simple
User=scraper
WorkingDirectory=/opt/carpark-scraper
ExecStart=/usr/bin/python3 scraper.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option 3: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY scraper.py .
CMD ["python", "scraper.py"]
```

### Option 4: Kubernetes CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: carpark-scraper
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scraper
            image: your-registry/carpark-scraper:latest
          restartPolicy: OnFailure
```

---

## Rate Limiting & Best Practices

1. **No Authentication Required** - API is public
2. **No Rate Limit Documented** - But be respectful (5 min interval is fine)
3. **Timeout**: Set 30 second timeout for requests
4. **Retry Logic**: Implement exponential backoff on failures
5. **Data Validation**: Some carparks may have null vacancy values

---

## Data Volume Estimates

| Interval | Records/Day | Records/Month | Storage (CSV) |
|----------|-------------|---------------|---------------|
| 5 min | 156,096 | 4.7M | ~500 MB |
| 10 min | 78,048 | 2.3M | ~250 MB |
| 30 min | 26,016 | 780K | ~85 MB |

---

## Contact

- **API Documentation**: https://data.gov.hk/en-data/dataset/hk-td-tis_5-real-time-parking-vacancy-data
- **Data Provider**: Transport Department, HKSAR Government
- **Data License**: Open Government License

---

## Quick Start

```bash
# Test the API
curl -s "https://api.data.gov.hk/v1/carpark-info-vacancy?data=vacancy&lang=en_US" | head -c 500

# Expected output: JSON with vacancy data
# {"results": [{"park_Id": "27", "privateCar": [{"vacancy": 34, ...}], ...}]}
```

**The API returns real vacancy numbers (no capping) - values like 34, 75, 349 are actual available spaces.**
