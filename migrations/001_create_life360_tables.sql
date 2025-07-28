-- Life360 Integration Database Tables
-- Migration: 001_create_life360_tables.sql
-- Created: $(date)

-- ============================================
-- Life360 Circle Configuration Table
-- ============================================
CREATE TABLE IF NOT EXISTS life360_circles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_id TEXT UNIQUE NOT NULL,  -- Life360's circle ID from API
    circle_name TEXT NOT NULL,       -- Human readable name "Smith Family"
    is_active BOOLEAN DEFAULT true,  -- Enable/disable tracking
    
    -- API configuration
    polling_interval INTEGER DEFAULT 30,  -- Minutes between polls
    working_hours_start TIME DEFAULT '08:00'::TIME,
    working_hours_end TIME DEFAULT '18:00'::TIME,
    timezone TEXT DEFAULT 'Asia/Dhaka',
    
    -- Audit fields
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================ 
-- Raw Location Data Table
-- ============================================
CREATE TABLE IF NOT EXISTS raw_location_feed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Life360 identifiers
    circle_id TEXT NOT NULL,
    member_id TEXT NOT NULL,         -- Life360's member ID
    member_name TEXT,                -- "John Smith" from Life360
    
    -- Optional link to your company users
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    
    -- GPS data
    latitude DECIMAL(9,6),           -- Precise coordinates
    longitude DECIMAL(9,6),
    accuracy INTEGER,                -- GPS accuracy in meters
    
    -- Location context from Life360
    place_name TEXT,                 -- "Home", "Office", etc.
    address TEXT,                    -- Full address if available
    
    -- Movement data
    speed DECIMAL(5,2),              -- Current speed
    is_driving BOOLEAN DEFAULT false,
    battery_level INTEGER,
    is_charging BOOLEAN DEFAULT false,
    
    -- Timing
    timestamp TIMESTAMPTZ,           -- When Life360 recorded this
    ingestion_time TIMESTAMPTZ DEFAULT now(),  -- When we stored it
    
    -- Raw API response for debugging
    raw_data JSONB,
    
    -- Processing tracking
    processing_status TEXT DEFAULT 'pending',
    error_message TEXT,
    
    -- Data quality constraints
    CONSTRAINT valid_coordinates CHECK (
        (latitude IS NULL AND longitude IS NULL) OR 
        (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
    ),
    CONSTRAINT valid_battery CHECK (
        battery_level IS NULL OR (battery_level >= 0 AND battery_level <= 100)
    ),
    CONSTRAINT valid_accuracy CHECK (
        accuracy IS NULL OR accuracy >= 0
    )
);

-- ============================================
-- User-Member Mapping Table (Optional)
-- ============================================
CREATE TABLE IF NOT EXISTS life360_user_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    life360_member_id TEXT NOT NULL,
    life360_member_name TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    -- Ensure one-to-one mapping
    UNIQUE(user_id, life360_member_id)
);

-- ============================================
-- Triggers for Updated Timestamps
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to circles table
DROP TRIGGER IF EXISTS update_life360_circles_updated_at ON life360_circles;
CREATE TRIGGER update_life360_circles_updated_at 
    BEFORE UPDATE ON life360_circles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Performance Indexes
-- ============================================

-- Circle queries
CREATE INDEX IF NOT EXISTS idx_life360_circles_active 
    ON life360_circles(is_active) WHERE is_active = true;

-- Location queries by member and time
CREATE INDEX IF NOT EXISTS idx_location_member_time 
    ON raw_location_feed(member_id, timestamp DESC);

-- Location queries by circle
CREATE INDEX IF NOT EXISTS idx_location_circle_time 
    ON raw_location_feed(circle_id, timestamp DESC);

-- User-linked locations
CREATE INDEX IF NOT EXISTS idx_location_user_time 
    ON raw_location_feed(user_id, timestamp DESC) 
    WHERE user_id IS NOT NULL;

-- Processing status queries
CREATE INDEX IF NOT EXISTS idx_location_processing 
    ON raw_location_feed(processing_status, ingestion_time) 
    WHERE processing_status != 'completed';

-- Recent data queries
CREATE INDEX IF NOT EXISTS idx_location_recent 
    ON raw_location_feed(ingestion_time DESC);

-- Geographic queries (if needed later)
CREATE INDEX IF NOT EXISTS idx_location_coords 
    ON raw_location_feed(latitude, longitude) 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- ============================================
-- Row Level Security (RLS)
-- ============================================
ALTER TABLE life360_circles ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_location_feed ENABLE ROW LEVEL SECURITY;
ALTER TABLE life360_user_mapping ENABLE ROW LEVEL SECURITY;

-- Policies (adjust based on your auth requirements)
CREATE POLICY "Authenticated users can view circles" ON life360_circles
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "Authenticated users can view locations" ON raw_location_feed
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "Users can view their own mappings" ON life360_user_mapping
    FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- Service role can do everything (for API operations)
CREATE POLICY "Service role full access circles" ON life360_circles
    FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access locations" ON raw_location_feed
    FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access mappings" ON life360_user_mapping
    FOR ALL TO service_role USING (true);

-- ============================================
-- Table Comments for Documentation
-- ============================================
COMMENT ON TABLE life360_circles IS 'Configuration for Life360 family circles to track';
COMMENT ON TABLE raw_location_feed IS 'Raw location data received from Life360 API';
COMMENT ON TABLE life360_user_mapping IS 'Maps company users to Life360 family members';

COMMENT ON COLUMN life360_circles.circle_id IS 'Life360 API circle identifier';
COMMENT ON COLUMN life360_circles.polling_interval IS 'Minutes between API polls';
COMMENT ON COLUMN raw_location_feed.user_id IS 'Optional link to company user account';
COMMENT ON COLUMN raw_location_feed.raw_data IS 'Complete Life360 API response for debugging';
COMMENT ON COLUMN raw_location_feed.timestamp IS 'When Life360 recorded the location';
COMMENT ON COLUMN raw_location_feed.ingestion_time IS 'When we stored the data';