# Data Science Jobs Pipeline

Automated, zero-cost pipeline that fetches **Data Scientist** job postings weekly from four Canadian job APIs, parses skills and seniority from descriptions, persists everything to Supabase (PostgreSQL), and serves insights on a public Streamlit dashboard.

## Architecture

```
JSearch API  ─┐
Adzuna API   ─┼─→ pipeline/ → Supabase (PostgreSQL) → Streamlit Dashboard
TheirStack   ─┤        ↑
SerpAPI      ─┘  GitHub Actions (weekly cron, Monday 06:00 UTC)
```

### Medallion ETL

| Layer | Location | What |
|---|---|---|
| **Bronze** | `job_postings.*_raw` columns | Original API values, never modified after insert |
| **Silver** | `job_postings` core columns | Cleaned, normalised, enriched |
| **Gold** | Supabase views | Pre-aggregated for dashboard consumption |

### Pipeline flow

```
1. Fetch     JSearch + Adzuna + TheirStack + SerpAPI (parallel) → combined list
2. Dedup     Bulk WHERE job_id = ANY(array) against job_postings
3. Bronze    Snapshot raw location + salary values before any cleaning
4. Silver    Strip HTML · normalise location · convert hourly salary · extract years_experience · classify seniority · extract skills
5. Stubs     Upsert company domain+name rows (ON CONFLICT DO NOTHING)
6. Upsert    job_postings with on_conflict=job_id (deduped within batch first)
7. Merge     merge_manual_enrichment() fills NULLs from job_manual_enrichment
8. Log       Update pipeline_runs: status, counts, duration
```

## Data Sources

| Source | Auth | Free tier | Notes |
|---|---|---|---|
| [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | RapidAPI key | 200 req/month | Provides employer website → domain |
| [Adzuna](https://developer.adzuna.com) | App ID + App Key | 1,000 req/month | No employer website; remote inferred from text |
| [TheirStack](https://theirstack.com) | Bearer token | Varies by plan | POST API; provides company URL and logo |
| [SerpAPI](https://serpapi.com) | API key | 100 searches/month | Google Jobs scraper; salary/location parsed from strings; posted_at converted from relative time using EST |

## Setup

### 1. Supabase

1. Create a free project at [supabase.com](https://supabase.com)
2. In the SQL Editor, run the migration files **in order**:
   - `sql/01_schema.sql`
   - `sql/02_indexes.sql`
   - `sql/03_rls_policies.sql`
   - `sql/04_views.sql`
   - `sql/05_manual_enrichment.sql`
   - `sql/06_add_seniority_experience.sql`
   - `sql/07_refresh_enriched_view.sql`
   - `sql/08_remove_apollo.sql`
   - `sql/09_add_bronze_raw_columns.sql`
   - `sql/10_update_enriched_view_with_raw.sql`
3. Copy your **Project URL**, **service_role key**, and **anon key** from Settings → API

### 2. API Keys

- **JSearch**: Subscribe at [RapidAPI JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
- **Adzuna**: Register at [developer.adzuna.com](https://developer.adzuna.com) — get App ID + App Key
- **TheirStack**: Register at [theirstack.com](https://theirstack.com) — get API key
- **SerpAPI**: Register at [serpapi.com](https://serpapi.com) — get API key

### 3. Local development

```bash
cp .env.example .env
# Fill in all values in .env

pip install -r requirements.txt

# Run the pipeline once
python -m pipeline.run_pipeline

# Run the dashboard
streamlit run dashboard/app.py

# Explore data in Jupyter
venv/bin/jupyter notebook notebooks/explore.ipynb
```

### 4. GitHub Actions

1. Push this repo to GitHub
2. Go to **Settings → Secrets → Actions** and add:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`
   - `JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`
   - `THEIRSTACK_API_KEY`, `SERPAPI_API_KEY`
3. Trigger manually via **Actions → Weekly Data Science Jobs Pipeline → Run workflow**

The pipeline also runs automatically every **Monday at 06:00 UTC**.

### 5. Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) → New app
2. Point to this repo, branch `main`, main file `dashboard/app.py`
3. Add secrets (anon key only — **never** the service key):
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`

## Running Tests

```bash
pytest tests/
```

## Project Structure

```
DataScienceJobs/
├── .github/workflows/
│   └── weekly_pipeline.yml          # Monday 06:00 UTC cron + manual trigger
├── pipeline/
│   ├── config.py                    # Centralised env var loading
│   ├── jsearch_client.py            # JSearch fetch + pagination
│   ├── adzuna_client.py             # Adzuna fetch + pagination
│   ├── theirstack_client.py         # TheirStack POST fetch + pagination
│   ├── serpapi_client.py            # SerpAPI Google Jobs; salary/location/date parsed from strings
│   ├── deduplication.py             # Bulk job_id dedup against DB
│   ├── data_cleaner.py              # HTML strip, location normalisation, salary conversion, seniority
│   ├── skills_parser.py             # Keyword extraction — 73 skills
│   ├── supabase_client.py           # Upsert helpers + pipeline run tracking
│   ├── run_pipeline.py              # Main entry point: Bronze snapshot + Silver cleaning
│   ├── backfill_data.py             # One-time: re-run all enrichment on existing rows
│   └── explore_data_quality.py      # Diagnostic report on field coverage
├── dashboard/
│   ├── app.py                       # Streamlit entry point
│   ├── utils.py                     # Cached data loaders (env → st.secrets fallback)
│   └── pages/
│       ├── 01_Overview.py           # KPIs, seniority pie, weekly trend, pipeline runs
│       ├── 02_Companies.py          # Top companies, seniority dist, employment type
│       ├── 03_Salaries.py           # Box plot, histogram, top-paying roles
│       ├── 04_Location_Remote.py    # Canada choropleth map — 4 switchable metrics
│       └── 05_Skills.py             # Dark-theme skills explorer — 73 skills, 4 categories
├── notebooks/
│   └── explore.ipynb                # Ad-hoc data exploration + column provenance table
├── sql/
│   ├── 01_schema.sql                # Tables: job_postings, companies, pipeline_runs
│   ├── 02_indexes.sql               # Performance indexes incl. GIN on skills_tags
│   ├── 03_rls_policies.sql          # anon = SELECT only; service_role = full access
│   ├── 04_views.sql                 # v_jobs_enriched, v_weekly_trends, v_skill_frequency
│   ├── 05_manual_enrichment.sql     # job_manual_enrichment table + merge function
│   ├── 06_add_seniority_experience.sql  # Adds years_experience_min + seniority columns
│   ├── 07_refresh_enriched_view.sql # Recreates view to pick up new columns
│   ├── 08_remove_apollo.sql         # Removes Apollo enrichment columns + index
│   ├── 09_add_bronze_raw_columns.sql    # Bronze layer: *_raw columns for location + salary
│   └── 10_update_enriched_view_with_raw.sql  # Exposes Bronze columns in v_jobs_enriched
├── tests/
│   ├── test_jsearch_client.py
│   ├── test_adzuna_client.py
│   ├── test_theirstack_client.py
│   ├── test_deduplication.py
│   ├── test_serpapi_client.py
│   └── test_data_cleaner.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Medallion architecture | Bronze `_raw` columns preserve original API values; Silver columns hold cleaned values; enables audit trail and re-processing without re-fetching |
| `company_domain` as join key | Normalised from employer URL; more reliable than company name which varies in casing/punctuation |
| Upsert on `job_id` | Safely refreshes salary/details if a source updates an existing posting |
| Batch dedup before upsert | One `WHERE job_id = ANY(array)` query; also dedupes within-batch to avoid Supabase error 21000 |
| `adzuna_` / `theirstack_` / `serpapi_` prefixes | Guarantees no `job_id` collision across the four sources |
| Location normalisation in Silver | Accent stripping, province inference, city alias resolution — all reversible against Bronze |
| Hourly salary → annual conversion | Rates < 250 with period=HOUR multiplied by 2080; original preserved in `_raw` columns |
| Seniority from title then years | Title keywords take precedence; years-of-experience brackets used as fallback; "Mid" as default |
| Anon key in dashboard | Read-only access even if Streamlit secrets leak; service key stays in GitHub Actions only |
| No third-party enrichment | Company records are minimal stubs (domain + name) derived directly from job APIs |
| Supabase MCP | DDL applied programmatically via `apply_migration` — no manual SQL Editor needed |
