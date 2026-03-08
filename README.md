# Data Science Jobs Pipeline

Automated, zero-cost pipeline that fetches **Data Scientist** job postings weekly from three Canadian job APIs, parses skills and seniority from descriptions, persists everything to Supabase (PostgreSQL), and serves insights on a public Streamlit dashboard.

## Architecture

```
JSearch API  ─┐
Adzuna API   ─┼─→ pipeline/ → Supabase (PostgreSQL) → Streamlit Dashboard
TheirStack   ─┘        ↑
                GitHub Actions (weekly cron, Monday 06:00 UTC)
```

## Data Sources

| Source | Auth | Free tier | Notes |
|---|---|---|---|
| [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | RapidAPI key | 200 req/month | Provides employer website → domain |
| [Adzuna](https://developer.adzuna.com) | App ID + App Key | 1,000 req/month | No employer website; remote inferred from text |
| [TheirStack](https://theirstack.com) | Bearer token | Varies by plan | POST API; provides company URL and logo |

## Setup

### 1. Supabase

1. Create a free project at [supabase.com](https://supabase.com)
2. In the SQL Editor, run the files **in order**:
   - `sql/01_schema.sql`
   - `sql/02_indexes.sql`
   - `sql/03_rls_policies.sql`
   - `sql/04_views.sql`
   - `sql/05_manual_enrichment.sql`
   - `sql/06_add_seniority_experience.sql`
3. Copy your **Project URL**, **service_role key**, and **anon key** from Settings → API

### 2. API Keys

- **JSearch**: Subscribe at [RapidAPI JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
- **Adzuna**: Register at [developer.adzuna.com](https://developer.adzuna.com) — get App ID + App Key
- **TheirStack**: Register at [theirstack.com](https://theirstack.com) — get API key

### 3. Local development

```bash
cp .env.example .env
# Fill in all six values in .env

pip install -r requirements.txt

# Run the pipeline once
python -m pipeline.run_pipeline

# Run the dashboard
streamlit run dashboard/app.py
```

### 4. GitHub Actions

1. Push this repo to GitHub
2. Go to **Settings → Secrets → Actions** and add:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `SUPABASE_ANON_KEY`
   - `JSEARCH_API_KEY`
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
   - `THEIRSTACK_API_KEY`
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
│   └── weekly_pipeline.yml      # Monday 06:00 UTC cron + manual trigger
├── pipeline/
│   ├── config.py                # Centralised env var loading
│   ├── jsearch_client.py        # JSearch fetch + pagination
│   ├── adzuna_client.py         # Adzuna fetch + pagination
│   ├── theirstack_client.py     # TheirStack POST fetch + pagination
│   ├── deduplication.py         # Bulk job_id dedup against DB
│   ├── data_cleaner.py          # HTML strip, years-of-exp regex, seniority classifier
│   ├── skills_parser.py         # Keyword extraction from descriptions
│   ├── supabase_client.py       # Upsert helpers + pipeline run tracking
│   └── run_pipeline.py          # Main entry point
├── dashboard/
│   ├── app.py                   # Streamlit entry point
│   ├── utils.py                 # Cached data loaders (env → st.secrets fallback)
│   └── pages/
│       ├── 01_Overview.py       # KPIs, seniority pie, weekly trend, pipeline runs
│       ├── 02_Companies.py      # Top companies, seniority dist, employment type, table
│       ├── 03_Salaries.py       # Box plot, histogram, top-paying roles
│       ├── 04_Location_Remote.py# Remote pie, provinces bar, cities
│       └── 05_Skills.py         # Top 30 skills, co-occurrence heatmap, trend
├── sql/
│   ├── 01_schema.sql            # Tables: job_postings, companies, pipeline_runs
│   ├── 02_indexes.sql           # Performance indexes incl. GIN on skills_tags
│   ├── 03_rls_policies.sql      # anon = SELECT only; service_role = full access
│   ├── 04_views.sql             # v_jobs_enriched, v_weekly_trends, v_skill_frequency
│   ├── 05_manual_enrichment.sql # job_manual_enrichment table + merge_manual_enrichment()
│   └── 06_add_seniority_experience.sql  # Adds years_experience_min + seniority columns
├── tests/
│   ├── test_jsearch_client.py
│   ├── test_adzuna_client.py
│   ├── test_theirstack_client.py
│   ├── test_deduplication.py
│   └── test_data_cleaner.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Pipeline Flow

```
1. Fetch        JSearch + Adzuna + TheirStack → combined list
2. Dedup        Bulk WHERE job_id = ANY(array) against job_postings
3. Clean        Strip HTML · extract years_experience_min · classify seniority · parse skills
4. Stubs        Upsert company domain+name rows (ON CONFLICT DO NOTHING)
5. Upsert       job_postings with on_conflict=job_id (deduped within batch first)
6. Merge        merge_manual_enrichment() fills NULLs from job_manual_enrichment
7. Log          Update pipeline_runs: status, counts, duration
```

## Manual Enrichment

Insert rows into `job_manual_enrichment` (matching `job_id`) to backfill or correct any field. The pipeline calls the `merge_manual_enrichment()` Postgres function after every upsert — it fills only NULL fields and never overwrites existing data.

## Key Design Decisions

| Decision | Rationale |
|---|---|
| `company_domain` as join key | Normalised from employer URL; more reliable than company name which varies in casing/punctuation |
| Upsert on `job_id` | Safely refreshes salary/details if a source updates an existing posting |
| Batch dedup before upsert | One `WHERE job_id = ANY(array)` query; also dedupes within-batch to avoid Supabase error 21000 |
| `adzuna_` / `theirstack_` prefixes | Guarantees no `job_id` collision across the three sources |
| Seniority from title then years | Title keywords take precedence; years-of-experience brackets used as fallback; "Mid" as default |
| Anon key in dashboard | Read-only access even if Streamlit secrets leak; service key stays in GitHub Actions only |
| No Apollo enrichment | Free tier (50/month) too limiting for 3 sources running weekly; company data derived directly from job APIs |
