-- ============================================================
-- 04_views.sql — Gold layer views for DataScienceJobs
-- ============================================================
-- Existing installs: run migration 07 and 10 to recreate views
-- if they were created with SELECT jp.* (which freezes columns).
-- Fresh installs: this file is the canonical view definition.
-- ============================================================

-- ── v_jobs_enriched ───────────────────────────────────────────────────────────
-- Primary dashboard view: job_postings joined with companies.
-- Exposes both Silver (cleaned) and Bronze (_raw) columns side by side.
DROP VIEW IF EXISTS v_jobs_enriched;
CREATE VIEW v_jobs_enriched AS
SELECT
    jp.id,
    jp.job_id,
    jp.title,
    jp.company_name,
    jp.company_domain,

    -- Silver: cleaned location
    jp.location_city,
    jp.location_state,
    jp.location_country,
    -- Bronze: original API location
    jp.location_city_raw,
    jp.location_state_raw,
    jp.location_country_raw,

    jp.is_remote,
    jp.employment_type,

    -- Silver: cleaned salary
    jp.salary_min,
    jp.salary_max,
    jp.salary_currency,
    jp.salary_period,
    -- Bronze: original API salary
    jp.salary_min_raw,
    jp.salary_max_raw,
    jp.salary_period_raw,

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

    -- From companies table
    c.industry,
    c.employee_count,
    c.employee_range,
    c.linkedin_url  AS company_linkedin_url,
    c.website_url   AS company_website_url,
    c.city          AS company_city,
    c.country       AS company_country
FROM job_postings jp
LEFT JOIN companies c ON jp.company_domain = c.domain;

-- ── v_weekly_trends ───────────────────────────────────────────────────────────
-- Gold: weekly job volume + remote count. Read by dashboard Overview page.
CREATE OR REPLACE VIEW v_weekly_trends AS
SELECT
    DATE_TRUNC('week', posted_at)::DATE          AS week_start,
    COUNT(*)                                      AS job_count,
    SUM(CASE WHEN is_remote THEN 1 ELSE 0 END)   AS remote_count
FROM job_postings
WHERE posted_at IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- ── v_skill_frequency ────────────────────────────────────────────────────────
-- Gold: skill mention counts across all postings. Read by Skills page.
CREATE OR REPLACE VIEW v_skill_frequency AS
SELECT
    skill,
    COUNT(*) AS occurrences
FROM job_postings,
     UNNEST(skills_tags) AS skill
GROUP BY 1
ORDER BY 2 DESC;

-- ── v_province_stats ─────────────────────────────────────────────────────────
-- Gold: pre-aggregated province metrics for the Location choropleth map.
CREATE OR REPLACE VIEW v_province_stats AS
SELECT
    location_state                                               AS province,
    COUNT(*)                                                     AS job_count,
    ROUND(
        100.0 * SUM(CASE WHEN is_remote THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*) FILTER (WHERE is_remote IS NOT NULL), 0),
    1)                                                           AS remote_rate,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE seniority IN ('Senior','Lead','Director+'))
        / NULLIF(COUNT(*), 0),
    1)                                                           AS senior_rate,
    ROUND(AVG(salary_min) FILTER (WHERE salary_min IS NOT NULL), 0) AS avg_salary,
    MODE() WITHIN GROUP (ORDER BY seniority)                    AS dominant_seniority
FROM job_postings
WHERE location_state IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC;
