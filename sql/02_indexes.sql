-- job_postings indexes
CREATE INDEX IF NOT EXISTS idx_job_postings_company_domain ON job_postings(company_domain);
CREATE INDEX IF NOT EXISTS idx_job_postings_posted_at      ON job_postings(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_postings_is_remote      ON job_postings(is_remote);
CREATE INDEX IF NOT EXISTS idx_job_postings_employment_type ON job_postings(employment_type);
CREATE INDEX IF NOT EXISTS idx_job_postings_location_state ON job_postings(location_state);
CREATE INDEX IF NOT EXISTS idx_job_postings_skills_tags    ON job_postings USING GIN(skills_tags);

-- companies indexes
CREATE INDEX IF NOT EXISTS idx_companies_apollo_enriched ON companies(apollo_enriched);
