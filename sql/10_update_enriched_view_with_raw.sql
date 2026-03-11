-- UPGRADE SCRIPT: safe to skip on fresh installs (01_schema.sql + 04_views.sql already include these changes).

-- Add Bronze (_raw) columns to v_jobs_enriched.
-- Raw columns capture original API values before pipeline cleaning.

DROP VIEW IF EXISTS v_jobs_enriched;
CREATE VIEW v_jobs_enriched AS
SELECT
    jp.id,
    jp.job_id,
    jp.title,
    jp.company_name,
    jp.company_domain,
    -- Silver (cleaned)
    jp.location_city,
    jp.location_state,
    jp.location_country,
    -- Bronze (raw API values)
    jp.location_city_raw,
    jp.location_state_raw,
    jp.location_country_raw,
    jp.is_remote,
    jp.employment_type,
    -- Silver (cleaned)
    jp.salary_min,
    jp.salary_max,
    jp.salary_currency,
    jp.salary_period,
    -- Bronze (raw API values)
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
    c.industry,
    c.employee_count,
    c.employee_range,
    c.linkedin_url  AS company_linkedin_url,
    c.website_url   AS company_website_url,
    c.city          AS company_city,
    c.country       AS company_country
FROM job_postings jp
LEFT JOIN companies c ON jp.company_domain = c.domain;
