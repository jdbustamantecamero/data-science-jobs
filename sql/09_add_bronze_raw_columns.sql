-- Bronze layer: store original API values before pipeline cleaning.
-- These columns are written once at insert time and never updated.
-- Silver columns (location_city, location_state, etc.) hold the cleaned values.

ALTER TABLE job_postings
    ADD COLUMN IF NOT EXISTS location_city_raw    TEXT,
    ADD COLUMN IF NOT EXISTS location_state_raw   TEXT,
    ADD COLUMN IF NOT EXISTS location_country_raw TEXT,
    ADD COLUMN IF NOT EXISTS salary_min_raw       NUMERIC,
    ADD COLUMN IF NOT EXISTS salary_max_raw       NUMERIC,
    ADD COLUMN IF NOT EXISTS salary_period_raw    TEXT;

-- Backfill existing rows: raw = current cleaned value as baseline
-- (true originals are gone; this marks the starting point)
UPDATE job_postings SET
    location_city_raw    = location_city,
    location_state_raw   = location_state,
    location_country_raw = location_country,
    salary_min_raw       = salary_min,
    salary_max_raw       = salary_max,
    salary_period_raw    = salary_period
WHERE location_city_raw IS NULL;
