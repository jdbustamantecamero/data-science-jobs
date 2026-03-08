-- Enable RLS on all tables
ALTER TABLE job_postings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies      ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs  ENABLE ROW LEVEL SECURITY;

-- anon: read-only on all three tables (public dashboard)
CREATE POLICY "anon_select_job_postings"
    ON job_postings FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_select_companies"
    ON companies FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_select_pipeline_runs"
    ON pipeline_runs FOR SELECT
    TO anon
    USING (true);

-- service_role bypasses RLS by default in Supabase — no extra policy needed.
-- If you disabled that bypass, uncomment below:
-- CREATE POLICY "service_all_job_postings"  ON job_postings  FOR ALL TO service_role USING (true) WITH CHECK (true);
-- CREATE POLICY "service_all_companies"     ON companies     FOR ALL TO service_role USING (true) WITH CHECK (true);
-- CREATE POLICY "service_all_pipeline_runs" ON pipeline_runs FOR ALL TO service_role USING (true) WITH CHECK (true);
