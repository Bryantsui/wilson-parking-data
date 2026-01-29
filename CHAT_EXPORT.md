# Wilson Parking API Discovery & Data Collection Setup

**Date:** January 28, 2026  
**Duration:** ~1 hour  
**Outcome:** Successfully discovered private API and set up automated 24/7 data collection

---

## 📋 Executive Summary

Successfully reverse-engineered the Wilson Parking Hong Kong mobile app to discover their private API endpoints. Set up an automated data collection system running on GitHub Actions that scrapes parking availability every 30 minutes.

**Repository:** https://github.com/Bryantsui/wilson-parking-data

---

## 🎯 Objective

Find the private API of the Wilson Parking app to collect parking availability data in this format:
```json
{
  "carpark_id": "00000000-0000-0000-000000000128",
  "guest_available": 3,
  "guest_available_display": "3",
  "guest_total": 130,
  "last_update": "2026-01-28T07:24:32Z",
  "monthly_available": 0,
  "monthly_is_full": true,
  "total_available": 3
}
```

---

## 🔧 Tools & Methods Used

### Hardware
- Android phone: OPPO CPH2671 (Android 16)
- MacBook connected via USB

### Software
- **ADB (Android Debug Bridge)** - Connect to phone
- **mitmproxy** - HTTPS traffic interception (attempted)
- **apktool** - APK decompilation
- **GitHub CLI** - Repository creation
- **GitHub Actions** - Automated scheduling

### Approach

1. **Initial Attempt: MITM Proxy** (Failed due to certificate pinning)
   - Set up mitmproxy on port 8080
   - Pushed CA certificate to phone via ADB
   - Configured system-wide proxy
   - ❌ Android 16 doesn't trust user certificates for apps

2. **Alternative: Frida** (Considered but not needed)
   - Would have bypassed SSL pinning by hooking certificate validation
   - Requires root access (phone wasn't rooted)

3. **Successful Method: APK Reverse Engineering**
   - Pulled APK from phone: `adb pull /data/app/.../base.apk`
   - Decompiled with apktool: `apktool d base.apk`
   - Searched smali code for API patterns
   - Found API URL and request format

---

## 🔍 API Discovery Process

### Step 1: Extract APK
```bash
adb shell pm path com.wilsonparking
adb pull /data/app/.../base.apk /tmp/wilson_apk/
```

### Step 2: Decompile
```bash
apktool d base.apk -o decompiled/
```

### Step 3: Search for API endpoints
```bash
strings classes*.dex | grep -iE "https?://"
```

**Found:**
- `https://mobile-prod.wilsonparkingapp.com/` (Production API)
- `https://app.wilsonparkingapp.com.hk/`

### Step 4: Find API operations
```bash
grep -rh "const-string.*\"[a-z-]+:[a-z-]+\"" --include="*.smali"
```

**Discovered operations:**
- `carpark:available-bays`
- `carpark:query`
- `carpark:available-ev-bays`
- `bookmark:list`
- `user:profile-get`
- And 30+ more

### Step 5: Determine request format
Found `action` and `args` keys in the code, tested combinations until successful.

---

## 📡 API Documentation

### Base URL
```
POST https://mobile-prod.wilsonparkingapp.com/
```

### Headers
```
Content-Type: application/json
Accept: application/json
User-Agent: okhttp/4.9.0
```

### Request Format
```json
{
  "action": "carpark:available-bays",
  "args": {
    "request": {}
  }
}
```

### Example cURL
```bash
curl -s "https://mobile-prod.wilsonparkingapp.com/" -X POST \
  -H "Content-Type: application/json" \
  -d '{"action":"carpark:available-bays","args":{"request":{}}}'
```

---

## 📊 Available API Endpoints

### Public (No Authentication Required)

| Endpoint | Description | Data Points |
|----------|-------------|-------------|
| `carpark:available-bays` | Real-time parking availability | guest_available (capped at 10), monthly_available, total |
| `carpark:query` | Carpark master data | Name, address, lat/lng, pricing, services, photos |
| `carpark:available-ev-bays` | EV charger availability | Exact counts (not capped!) for fast/medium/super-fast chargers |
| `carpark:carousel` | Featured carparks | 8 highlighted locations |
| `campaign-banner:fetch` | Promotional banners | Marketing campaigns |
| `news:weather` | Current weather | Temperature, conditions |
| `landmark:query` | Nearby landmarks | Restaurants, attractions |

### Requires Authentication

| Endpoint | Description |
|----------|-------------|
| `bookmark:list` | User's saved carparks |
| `user:profile-get` | User profile |
| `user:car-list` | Registered vehicles |
| `order:create` | Create booking |
| `order:pay` | Process payment |

---

## ⚠️ Data Limitations

### Availability Truncation
The API has a truncation config that **caps guest_available at 10**:

```json
{
  "display_as": "10+",
  "min": 10,
  "truncate_to": 10
}
```

| Actual Availability | What API Returns |
|---------------------|------------------|
| 0-9 spots | ✅ Exact count |
| 10+ spots | ⚠️ Returns "10" (displays "10+") |

**Implication:** Precise utilization data only available during high-demand periods (< 10 spots).

### EV Chargers - NOT Capped
The `carpark:available-ev-bays` endpoint returns **exact counts** for EV chargers.

---

## 🚀 Data Collection System

### Architecture
```
GitHub Actions (scheduler)
    ↓ Every 30 minutes
Python Script (scraper_cloud.py)
    ↓ API call
CSV Files (data/availability_YYYY-MM-DD.csv)
    ↓ Git commit
GitHub Repository (storage)
```

### Files Created

| File | Purpose |
|------|---------|
| `scraper_cloud.py` | Main scraper script |
| `analyze.py` | Data analysis utilities |
| `schema.sql` | Database schema (for local analysis) |
| `.github/workflows/scrape.yml` | GitHub Actions workflow |
| `data/carparks.csv` | Carpark metadata |
| `data/availability_*.csv` | Daily availability snapshots |

### GitHub Actions Workflow
```yaml
name: Scrape Wilson Parking
on:
  schedule:
    - cron: '0,30 * * * *'  # Every 30 minutes
  workflow_dispatch:  # Manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python scraper_cloud.py
      - run: |
          git add data/
          git commit -m "Data update"
          git push
```

### Storage Estimates (1 Month)
- Scrapes: 48/day × 30 days = 1,440 total
- Records: 271 carparks × 1,440 = ~390,000 rows
- File size: ~60 MB total

---

## 🔐 Why Frida Was Considered

### The Problem: Certificate Pinning on Modern Android

Starting with Android 7 (Nougat), Google changed certificate trust:

| Certificate Type | Browser | Apps |
|------------------|---------|------|
| System CA | ✅ Trusted | ✅ Trusted |
| User-installed CA | ✅ Trusted | ❌ Not trusted |

When we installed the mitmproxy certificate, apps ignored it.

### What Frida Does
Frida is a dynamic instrumentation toolkit that can:
1. Inject code into running apps at runtime
2. Hook certificate validation functions
3. Force the app to trust any certificate

### Why We Didn't Need It
Found a shortcut: instead of intercepting live traffic, we:
1. Pulled the APK from the phone
2. Decompiled it to examine the code
3. Found the API format by analyzing strings
4. Called the API directly

---

## 📈 Analysis Commands

```bash
cd /Users/bryan/wilson_parking_scraper

# Current status
python3 analyze.py --status

# High-demand analysis (where exact data exists)
python3 analyze.py --demand

# Specific carpark profile
python3 analyze.py --profile "Tsuen Wan"

# Data quality report
python3 analyze.py --quality

# Export to CSV
python3 analyze.py --export parking_data.csv --days 30
```

---

## 🔗 Resources

- **GitHub Repository:** https://github.com/Bryantsui/wilson-parking-data
- **Actions Dashboard:** https://github.com/Bryantsui/wilson-parking-data/actions
- **Data Files:** https://github.com/Bryantsui/wilson-parking-data/tree/main/data

---

## ⏹️ Stop Collection (After 1 Month)

```bash
gh workflow disable scrape.yml --repo Bryantsui/wilson-parking-data
```

Or: GitHub → Actions → Scrape Wilson Parking → ⋯ → Disable workflow

---

## 📝 Key Learnings

1. **Modern Android security** makes MITM interception difficult without root
2. **APK reverse engineering** is often faster than traffic interception
3. **Skygear** backend uses action/args JSON format
4. **API truncation** is common for competitive/privacy reasons
5. **GitHub Actions** provides free 24/7 scheduling for data collection

---

*Document generated: January 28, 2026*
