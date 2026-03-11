# CLAUDE.md — Project context for Claude Code

## What this project is

Automated ETL pipeline + Streamlit dashboard for Canadian Data Scientist job postings.
Four job APIs → Supabase (PostgreSQL) → public Streamlit dashboard.

## Common commands

```bash
# Run the pipeline locally (requires .env)
python -m pipeline.run_pipeline

# Run the dashboard locally
streamlit run dashboard/app.py

# Run tests
pytest tests/
```

## Key architecture rules

- **Four job sources**: JSearch (`jsearch_client.py`), Adzuna (`adzuna_client.py`), TheirStack (`theirstack_client.py`), SerpAPI (`serpapi_client.py`). All normalise to the same dict shape before anything downstream touches them.
- **job_id prefixes**: JSearch IDs are plain. Adzuna prefixes `adzuna_`. TheirStack prefixes `theirstack_`. SerpAPI prefixes `serpapi_`. Never change this — it prevents cross-source collisions in the dedup table.
- **No Apollo**: Apollo enrichment was removed (free tier too limiting). Do not re-add it. Company records are minimal stubs (domain + name only).
- **Dedup is bulk**: `deduplication.py` issues a single `WHERE job_id = ANY(array)` query. Never replace with per-job queries.
- **Upsert dedup within batch**: `upsert_jobs()` in `supabase_client.py` dedupes by `job_id` before the upsert call to avoid Supabase error code 21000. Keep this.
- **FK constraint**: `job_postings.company_domain` references `companies.domain`. Always call `ensure_company_stubs()` before `upsert_jobs()`.
- **Cleaning happens in run_pipeline.py step 3**: `clean_description` → `extract_years_experience` → `classify_seniority` → `extract_skills`. Order matters — skills and seniority run on the cleaned description.
- **Target country**: Canada (`ca`). JSearch uses `country="ca"`, Adzuna uses `where="Canada"`, TheirStack uses `job_country_code_or=["CA"]`, SerpAPI uses `location="Canada"` (no `gl` — combining both causes 400).
- **SerpAPI pagination**: uses `next_page_token` from `serpapi_pagination` in each response — NOT `start` offset (that's regular Google Search and causes 400 on `google_jobs`).
- **SerpAPI timezone**: `posted_at` is computed from relative strings ("3 days ago") using `ZoneInfo("America/Toronto")` (EST/EDT). Only SerpAPI needs this — the other three APIs return pre-timestamped strings from their servers.
- **Skills page dark theme**: `05_Skills.py` uses injected CSS for dark navy/slate theme. Skill categories are defined in `SKILL_CATEGORIES` dict at the top of that file — update it whenever `skills_parser.SKILLS` changes.
- **Salary currency**: CAD. Both the DB column default and the pipeline fallback.

## File structure quick reference

```
pipeline/run_pipeline.py      Main entry point — wire changes here
pipeline/data_cleaner.py      HTML strip, years-of-exp regex, seniority classifier
pipeline/skills_parser.py     Keyword extraction (edit SKILLS list to add/remove skills)
pipeline/serpapi_client.py    SerpAPI: salary/location/date all parsed from raw strings; EST timezone
pipeline/supabase_client.py   All DB writes; add new upsert helpers here
pipeline/config.py            All env vars; use _require() for mandatory keys
dashboard/utils.py            All Supabase reads for dashboard; add loaders here
dashboard/pages/05_Skills.py  Dark-theme skills explorer; SKILL_CATEGORIES dict must stay in sync with skills_parser.SKILLS
sql/                          Run files 01→06 in Supabase SQL Editor in order
```

## Dashboard rules

- Dashboard pages import from `utils` (not `dashboard.utils`) — Streamlit adds `dashboard/` to sys.path for pages.
- All data loaders in `utils.py` use `@st.cache_data(ttl=3600)`.
- Env var priority: `os.environ` first, then `st.secrets`. This is set in `utils.py:get_client()`.
- Never use the service key in the dashboard. Anon key only.
- The dashboard reads from `v_jobs_enriched` (a view joining `job_postings` + `companies`).

## Seniority levels

Ordered: `Intern → Junior → Mid → Senior → Lead → Director+`

Classification priority:
1. Title keyword match (`data_cleaner._TITLE_RULES`)
2. `years_experience_min` brackets (0–2 Junior, 3–5 Mid, 6–9 Senior, 10+ Lead)
3. Default: `"Mid"`

## Adding a new job source

1. Create `pipeline/{source}_client.py` with a `fetch_jobs()` returning the standard dict shape
2. Prefix `job_id` with `{source}_`
3. Add API key to `config.py` (use `_require()`), `.env.example`, and `weekly_pipeline.yml`
4. Import and call in `run_pipeline.py` step 1, append to `raw_jobs`
5. Add tests in `tests/test_{source}_client.py`

## SQL migration pattern

New schema changes go in a new numbered file (`sql/07_...sql`). Always use `IF NOT EXISTS` / `IF EXISTS` guards so files are safe to re-run.

## GitHub Actions secrets (all required)

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`,
`JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `THEIRSTACK_API_KEY`, `SERPAPI_API_KEY`

## Timezone note

Only SerpAPI computes timestamps locally (converting "3 days ago" → absolute datetime).
It uses `ZoneInfo("America/Toronto")` for EST/EDT. The other three APIs return
pre-timestamped strings from their own servers and need no local timezone handling.
