-- ============================================================
-- 04_views.sql — Gold Layer Views for Dashboards
-- ============================================================
-- Refreshes the enriched job view with full Bronze/Silver columns.
-- ============================================================

DROP VIEW IF EXISTS v_jobs_enriched;
CREATE VIEW v_jobs_enriched AS
SELECT
    jp.id,
    jp.job_id,
    
    -- Silver (Cleaned)
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

    -- Bronze (Raw API values)
    jp.title_raw,
    jp.company_name_raw,
    jp.company_domain_raw,
    jp.location_city_raw,
    jp.location_state_raw,
    jp.location_country_raw,
    jp.is_remote_raw,
    jp.employment_type_raw,
    jp.salary_min_raw,
    jp.salary_max_raw,
    jp.salary_currency_raw,
    jp.salary_period_raw,
    jp.job_description_raw,
    jp.job_apply_link_raw,
    jp.employer_logo_raw,
    jp.posted_at_raw,

    -- Metadata
    jp.fetched_at,
    jp.created_at,
    jp.updated_at,

    -- Company Metadata (LEFT JOIN)
    c.industry,
    c.employee_count,
    c.employee_range,
    c.linkedin_url  AS company_linkedin_url,
    c.website_url   AS company_website_url,
    c.city          AS company_city,
    c.country       AS company_country

FROM job_postings jp
LEFT JOIN companies c ON jp.company_domain = c.domain;

-- ── v_province_stats (Gold) ──────────────────────────────────────────────────
-- Pre-aggregated metrics for the Location map.
CREATE OR REPLACE VIEW v_province_stats AS
SELECT
    location_state AS province,
    COUNT(*) AS job_count,
    ROUND(AVG(salary_min) FILTER (WHERE salary_min > 0), 0) AS avg_salary,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_remote = True) / COUNT(*), 1) AS remote_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE seniority IN ('Senior', 'Lead', 'Director+')) / COUNT(*), 1) AS senior_rate
FROM job_postings
WHERE location_state IS NOT NULL
GROUP BY location_state;
