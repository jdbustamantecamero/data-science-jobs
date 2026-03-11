-- Recreate v_jobs_enriched to pick up columns added after initial creation:
-- seniority, years_experience_min (added in 06_add_seniority_experience.sql)
--
-- PostgreSQL freezes SELECT * at view creation time, so new base-table columns
-- are invisible to the view until it is recreated.
--
-- DROP + CREATE is required because CREATE OR REPLACE cannot reorder columns.
-- The view has no dependents so dropping it is safe (no data is lost).

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
    c.linkedin_url      AS company_linkedin_url,
    c.website_url       AS company_website_url,
    c.city              AS company_city,
    c.country           AS company_country
FROM job_postings jp
LEFT JOIN companies c ON jp.company_domain = c.domain;
