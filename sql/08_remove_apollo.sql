-- Remove Apollo enrichment artifacts.
-- Apollo was removed from the pipeline (free tier: 50 enrichments/month —
-- too limiting for weekly runs across hundreds of jobs).
-- Company records are now minimal stubs: domain + name only.
--
-- Safe to re-run: all statements use IF EXISTS guards.

-- Drop index first (must precede column drop)
DROP INDEX IF EXISTS idx_companies_apollo_enriched;

-- Drop columns from companies table
ALTER TABLE companies
    DROP COLUMN IF EXISTS apollo_enriched,
    DROP COLUMN IF EXISTS apollo_enriched_at;

-- Recreate v_jobs_enriched without apollo_enriched
DROP VIEW IF EXISTS v_jobs_enriched;
CREATE VIEW v_jobs_enriched AS
SELECT
    jp.id,
    jp.job_id,
    jp.title,
    jp.company_name,
    jp.company_domain,
    jp.location_city,
    jp.location_state,
    jp.location_country,
    jp.is_remote,
    jp.employment_type,
    jp.salary_min,
    jp.salary_max,
    jp.salary_currency,
    jp.salary_period,
    jp.job_description,
    jp.job_apply_link,
    jp.employer_logo,
    jp.skills_tags,
    jp.seniority,
    jp.years_experience_min,
    jp.posted_at,
    jp.fetched_at,
    jp.created_at,
    jp.updated_at,
    c.industry,
    c.employee_count,
    c.employee_range,
    c.linkedin_url  AS company_linkedin_url,
    c.website_url   AS company_website_url,
    c.city          AS company_city,
    c.country       AS company_country
FROM job_postings jp
LEFT JOIN companies c ON jp.company_domain = c.domain;
