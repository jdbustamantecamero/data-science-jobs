-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Companies table (must exist before job_postings FK)
CREATE TABLE IF NOT EXISTS companies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain              TEXT UNIQUE NOT NULL,
    name                TEXT,
    industry            TEXT,
    employee_count      INTEGER,
    employee_range      TEXT,
    linkedin_url        TEXT,
    website_url         TEXT,
    city                TEXT,
    country             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Job postings table
CREATE TABLE IF NOT EXISTS job_postings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              TEXT UNIQUE NOT NULL,
    title               TEXT,
    company_name        TEXT,
    company_domain      TEXT REFERENCES companies(domain) ON DELETE SET NULL,
    location_city       TEXT,
    location_state      TEXT,
    location_country    TEXT,
    is_remote           BOOLEAN,
    employment_type     TEXT,
    salary_min          NUMERIC,
    salary_max          NUMERIC,
    salary_currency     TEXT DEFAULT 'CAD',
    salary_period       TEXT,
    job_description     TEXT,
    job_apply_link      TEXT,
    employer_logo       TEXT,
    skills_tags         TEXT[],
    posted_at           TIMESTAMPTZ,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pipeline runs table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    jobs_fetched        INTEGER DEFAULT 0,
    jobs_new            INTEGER DEFAULT 0,
    jobs_skipped        INTEGER DEFAULT 0,
    companies_enriched  INTEGER DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'running',
    error_message       TEXT,
    duration_seconds    NUMERIC,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at
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
