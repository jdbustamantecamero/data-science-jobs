-- ============================================================
-- 01_schema.sql — Canonical schema for DataScienceJobs
-- ============================================================
-- Run this on a fresh Supabase project before any other file.
-- Existing installs: safe to re-run (all guards use IF NOT EXISTS).
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── companies ─────────────────────────────────────────────────────────────────
-- Minimal stubs: domain + name only.
CREATE TABLE IF NOT EXISTS companies (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain         TEXT UNIQUE NOT NULL,
    name           TEXT,
    industry       TEXT,
    employee_count INTEGER,
    employee_range TEXT,
    linkedin_url   TEXT,
    website_url    TEXT,
    city           TEXT,
    country        TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── job_postings ──────────────────────────────────────────────────────────────
-- Medallion layout:
--   🥉 Bronze (*_raw) — original API values, written once, never updated
--   🥈 Silver          — cleaned / normalised values used by the dashboard
CREATE TABLE IF NOT EXISTS job_postings (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id               TEXT UNIQUE NOT NULL,
    
    -- Core Identity
    title                TEXT,
    title_raw            TEXT,
    company_name         TEXT,
    company_name_raw     TEXT,
    company_domain       TEXT REFERENCES companies(domain) ON DELETE SET NULL,
    company_domain_raw   TEXT,

    -- Location (Silver & Bronze)
    location_city        TEXT,
    location_city_raw    TEXT,
    location_state       TEXT,
    location_state_raw   TEXT,
    location_country     TEXT,
    location_country_raw TEXT,
    is_remote            BOOLEAN,
    is_remote_raw        BOOLEAN,

    -- Employment
    employment_type      TEXT,
    employment_type_raw  TEXT,

    -- Salary (Silver & Bronze)
    salary_min           NUMERIC,
    salary_min_raw       NUMERIC,
    salary_max           NUMERIC,
    salary_max_raw       NUMERIC,
    salary_currency      TEXT DEFAULT 'CAD',
    salary_currency_raw  TEXT,
    salary_period        TEXT,
    salary_period_raw    TEXT,

    -- Description & Assets
    job_description      TEXT,
    job_description_raw  TEXT,
    job_apply_link       TEXT,
    job_apply_link_raw   TEXT,
    employer_logo        TEXT,
    employer_logo_raw    TEXT,
    skills_tags          TEXT[],

    -- Pipeline-derived Enrichment
    seniority            TEXT,
    years_experience_min INTEGER,

    -- Timestamps
    posted_at            TIMESTAMPTZ,
    posted_at_raw        TEXT,
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── pipeline_runs ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    jobs_fetched     INTEGER DEFAULT 0,
    jobs_new         INTEGER DEFAULT 0,
    jobs_skipped     INTEGER DEFAULT 0,
    companies_enriched INTEGER DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'running',
    error_message    TEXT,
    duration_seconds NUMERIC,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER job_postings_updated_at
    BEFORE UPDATE ON job_postings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
