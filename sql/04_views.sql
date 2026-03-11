-- Enriched jobs view: joins job_postings + companies
CREATE OR REPLACE VIEW v_jobs_enriched AS
SELECT
    jp.*,
    c.industry,
    c.employee_count,
    c.employee_range,
    c.linkedin_url      AS company_linkedin_url,
    c.website_url       AS company_website_url,
    c.city              AS company_city,
    c.country           AS company_country
FROM job_postings jp
LEFT JOIN companies c ON jp.company_domain = c.domain;

-- Weekly job trend
CREATE OR REPLACE VIEW v_weekly_trends AS
SELECT
    DATE_TRUNC('week', posted_at)::DATE AS week_start,
    COUNT(*)                             AS job_count,
    SUM(CASE WHEN is_remote THEN 1 ELSE 0 END) AS remote_count
FROM job_postings
WHERE posted_at IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- Skill frequency
CREATE OR REPLACE VIEW v_skill_frequency AS
SELECT
    skill,
    COUNT(*) AS occurrences
FROM job_postings,
     UNNEST(skills_tags) AS skill
GROUP BY 1
ORDER BY 2 DESC;
