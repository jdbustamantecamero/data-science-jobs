-- Manual enrichment table: mirrors job_postings columns.
-- Populated by hand (CSV import, direct SQL, etc.).
-- job_id is the join key back to job_postings.
CREATE TABLE IF NOT EXISTS job_manual_enrichment (
    job_id              TEXT PRIMARY KEY,
    title               TEXT,
    company_name        TEXT,
    company_domain      TEXT,
    location_city       TEXT,
    location_state      TEXT,
    location_country    TEXT,
    is_remote           BOOLEAN,
    employment_type     TEXT,
    salary_min          NUMERIC,
    salary_max          NUMERIC,
    salary_currency     TEXT,
    salary_period       TEXT,
    job_description     TEXT,
    job_apply_link      TEXT,
    employer_logo       TEXT,
    skills_tags         TEXT[],
    posted_at           TIMESTAMPTZ,
    notes               TEXT,          -- free-form annotation field
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER job_manual_enrichment_updated_at
    BEFORE UPDATE ON job_manual_enrichment
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS
ALTER TABLE job_manual_enrichment ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_job_manual_enrichment"
    ON job_manual_enrichment FOR SELECT
    TO anon
    USING (true);

-- Stored function: fill NULLs in job_postings from job_manual_enrichment.
-- Only updates rows whose job_id is in p_job_ids, and only overwrites NULLs.
-- Returns the number of rows updated.
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
        title            = COALESCE(jp.title,            me.title),
        company_name     = COALESCE(jp.company_name,     me.company_name),
        company_domain   = COALESCE(jp.company_domain,   me.company_domain),
        location_city    = COALESCE(jp.location_city,    me.location_city),
        location_state   = COALESCE(jp.location_state,   me.location_state),
        location_country = COALESCE(jp.location_country, me.location_country),
        is_remote        = COALESCE(jp.is_remote,        me.is_remote),
        employment_type  = COALESCE(jp.employment_type,  me.employment_type),
        salary_min       = COALESCE(jp.salary_min,       me.salary_min),
        salary_max       = COALESCE(jp.salary_max,       me.salary_max),
        salary_currency  = COALESCE(jp.salary_currency,  me.salary_currency),
        salary_period    = COALESCE(jp.salary_period,    me.salary_period),
        job_description  = COALESCE(jp.job_description,  me.job_description),
        job_apply_link   = COALESCE(jp.job_apply_link,   me.job_apply_link),
        employer_logo    = COALESCE(jp.employer_logo,    me.employer_logo),
        skills_tags      = CASE
                               WHEN jp.skills_tags IS NULL OR jp.skills_tags = '{}'
                               THEN me.skills_tags
                               ELSE jp.skills_tags
                           END,
        posted_at        = COALESCE(jp.posted_at,        me.posted_at)
    FROM job_manual_enrichment me
    WHERE jp.job_id = me.job_id
      AND jp.job_id = ANY(p_job_ids);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$;
