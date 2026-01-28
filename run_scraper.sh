#!/bin/bash
# Cron wrapper for Wilson Parking Scraper
# Add to crontab: */30 * * * * /Users/bryan/wilson_parking_scraper/run_scraper.sh

cd /Users/bryan/wilson_parking_scraper

# Run scraper with aggregation at midnight
HOUR=$(date +%H)
if [ "$HOUR" = "00" ]; then
    /usr/bin/python3 scraper.py --aggregate >> scraper.log 2>&1
else
    /usr/bin/python3 scraper.py >> scraper.log 2>&1
fi
