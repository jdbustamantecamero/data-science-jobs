-- Migration: add years_experience_min and seniority to job_postings
-- Run once in Supabase SQL Editor after 01–05.

ALTER TABLE job_postings
    ADD COLUMN IF NOT EXISTS years_experience_min INTEGER,
    ADD COLUMN IF NOT EXISTS seniority             TEXT;

-- Also add to manual enrichment table so it can override pipeline values
ALTER TABLE job_manual_enrichment
    ADD COLUMN IF NOT EXISTS years_experience_min INTEGER,
    ADD COLUMN IF NOT EXISTS seniority             TEXT;

-- Index for seniority filter on dashboard
CREATE INDEX IF NOT EXISTS idx_job_postings_seniority
    ON job_postings(seniority);

-- Update the merge function to include the two new columns
CREATE OR REPLACE FUNCTION merge_manual_enrichment(p_job_ids TEXT[])
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    UPDATE job_postings jp
    SET
        title                = COALESCE(jp.title,                me.title),
        company_name         = COALESCE(jp.company_name,         me.company_name),
        company_domain       = COALESCE(jp.company_domain,       me.company_domain),
        location_city        = COALESCE(jp.location_city,        me.location_city),
        location_state       = COALESCE(jp.location_state,       me.location_state),
        location_country     = COALESCE(jp.location_country,     me.location_country),
        is_remote            = COALESCE(jp.is_remote,            me.is_remote),
        employment_type      = COALESCE(jp.employment_type,      me.employment_type),
        salary_min           = COALESCE(jp.salary_min,           me.salary_min),
        salary_max           = COALESCE(jp.salary_max,           me.salary_max),
        salary_currency      = COALESCE(jp.salary_currency,      me.salary_currency),
        salary_period        = COALESCE(jp.salary_period,        me.salary_period),
        job_description      = COALESCE(jp.job_description,      me.job_description),
        job_apply_link       = COALESCE(jp.job_apply_link,       me.job_apply_link),
        employer_logo        = COALESCE(jp.employer_logo,        me.employer_logo),
        skills_tags          = CASE
                                   WHEN jp.skills_tags IS NULL OR jp.skills_tags = '{}'
                                   THEN me.skills_tags
                                   ELSE jp.skills_tags
                               END,
        posted_at            = COALESCE(jp.posted_at,            me.posted_at),
        years_experience_min = COALESCE(jp.years_experience_min, me.years_experience_min),
        seniority            = COALESCE(jp.seniority,            me.seniority)
    FROM job_manual_enrichment me
    WHERE jp.job_id = me.job_id
      AND jp.job_id = ANY(p_job_ids);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$;
