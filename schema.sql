-- Wilson Parking Data Schema
-- Designed for utilization analysis with 30-minute scrapes

-- Carpark metadata (static, update occasionally)
CREATE TABLE IF NOT EXISTS carparks (
    id TEXT PRIMARY KEY,
    name_en TEXT,
    name_zh TEXT,
    address_en TEXT,
    address_zh TEXT,
    district_id TEXT,
    latitude REAL,
    longitude REAL,
    height_limit TEXT,
    has_ev_charging BOOLEAN,
    guest_total INTEGER,        -- Total guest parking spaces
    monthly_total INTEGER,      -- Total monthly spaces
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Availability snapshots (main data table)
CREATE TABLE IF NOT EXISTS availability_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carpark_id TEXT NOT NULL,
    scraped_at TIMESTAMP NOT NULL,           -- When we scraped
    last_update TIMESTAMP,                   -- API's last_update field
    
    -- Guest parking (hourly)
    guest_available INTEGER,                 -- Actual count (capped at 10)
    guest_available_display TEXT,            -- Display value ("10+", "5", etc.)
    guest_total INTEGER,
    guest_is_capped BOOLEAN,                 -- True if showing "10+"
    
    -- Monthly parking
    monthly_available INTEGER,
    monthly_total INTEGER,
    monthly_is_full BOOLEAN,
    
    -- Calculated fields
    total_available INTEGER,
    total_capacity INTEGER,
    
    FOREIGN KEY (carpark_id) REFERENCES carparks(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_snapshots_carpark_time 
    ON availability_snapshots(carpark_id, scraped_at);

CREATE INDEX IF NOT EXISTS idx_snapshots_time 
    ON availability_snapshots(scraped_at);

CREATE INDEX IF NOT EXISTS idx_snapshots_guest_available 
    ON availability_snapshots(guest_available);

-- Daily aggregates (for faster analysis)
CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carpark_id TEXT NOT NULL,
    date DATE NOT NULL,
    hour INTEGER NOT NULL,              -- 0-23
    
    -- Guest parking stats
    min_guest_available INTEGER,
    max_guest_available INTEGER,
    avg_guest_available REAL,
    samples_at_capacity INTEGER,        -- Count of "10+" readings
    total_samples INTEGER,
    
    -- Utilization (only meaningful when not capped)
    avg_utilization_pct REAL,
    peak_utilization_pct REAL,
    
    UNIQUE(carpark_id, date, hour),
    FOREIGN KEY (carpark_id) REFERENCES carparks(id)
);

-- Views for analysis
CREATE VIEW IF NOT EXISTS v_current_availability AS
SELECT 
    c.name_en,
    c.address_en,
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
ORDER BY utilization_pct DESC;

-- High demand periods (when data is precise)
CREATE VIEW IF NOT EXISTS v_high_demand_periods AS
SELECT 
    c.name_en,
    a.carpark_id,
    DATE(a.scraped_at) as date,
    strftime('%H', a.scraped_at) as hour,
    a.guest_available,
    a.guest_total,
    ROUND((a.guest_total - a.guest_available) * 100.0 / a.guest_total, 1) as utilization_pct
FROM availability_snapshots a
JOIN carparks c ON a.carpark_id = c.id
WHERE a.guest_is_capped = 0  -- Only exact counts
  AND a.guest_available < 10
ORDER BY utilization_pct DESC;
