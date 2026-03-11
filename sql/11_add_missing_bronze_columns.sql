-- UPGRADE SCRIPT: Add missing Bronze layer columns to ensure 100% raw capture.
-- Every field coming from the APIs should have a corresponding _raw column.

ALTER TABLE job_postings
    ADD COLUMN IF NOT EXISTS title_raw           TEXT,
    ADD COLUMN IF NOT EXISTS company_name_raw    TEXT,
    ADD COLUMN IF NOT EXISTS company_domain_raw  TEXT,
    ADD COLUMN IF NOT EXISTS is_remote_raw       BOOLEAN,
    ADD COLUMN IF NOT EXISTS employment_type_raw TEXT,
    ADD COLUMN IF NOT EXISTS salary_currency_raw TEXT,
    ADD COLUMN IF NOT EXISTS job_description_raw TEXT,
    ADD COLUMN IF NOT EXISTS job_apply_link_raw  TEXT,
    ADD COLUMN IF NOT EXISTS employer_logo_raw   TEXT,
    ADD COLUMN IF NOT EXISTS posted_at_raw       TEXT;

-- Backfill existing rows: raw = current silver value (starting baseline)
UPDATE job_postings SET
    title_raw           = title,
    company_name_raw    = company_name,
    company_domain_raw  = company_domain,
    is_remote_raw       = is_remote,
    employment_type_raw = employment_type,
    salary_currency_raw = salary_currency,
    job_description_raw = job_description,
    job_apply_link_raw  = job_apply_link,
    employer_logo_raw   = employer_logo,
    posted_at_raw       = CAST(posted_at AS TEXT)
WHERE title_raw IS NULL;
