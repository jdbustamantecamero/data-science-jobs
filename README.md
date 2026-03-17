# Data Science Jobs Pipeline

Automated, zero-cost pipeline that fetches **Data Scientist** job postings weekly from four Canadian job APIs, parses skills and seniority from descriptions, persists everything to Supabase (PostgreSQL), and serves insights on a public Streamlit dashboard.

## Architecture (3-Stage Medallion)

```
Ingest (Bronze) ──→ Transform (Silver) ──→ Promote (Gold)
      ↑                    ↑                    ↑
Raw API Data         Cleaned & Enriched      Aggregated Views
(16 _raw columns)    (Location, Salary,     (Dashboard Ready)
                      Skills, Seniority)
```

### Medallion ETL Layers

| Layer | Location | What |
|---|---|---|
| **Bronze** | `job_postings.*_raw` | 100% raw capture. Original API values, never modified after insert. |
| **Silver** | `job_postings` core columns | Cleaned, normalised, enriched via `JobTransformer`. |
| **Gold** | Supabase views | Pre-aggregated logic (e.g. `v_province_stats`) for the dashboard. |

### Pipeline Flow

1. **Ingest** — all providers (`JSearchProvider`, `AdzunaProvider`, `TheirStackProvider`, `SerpAPIProvider`) fetch in parallel via `ThreadPoolExecutor`. Each inherits from `BaseJobSource` and maps to `JobDict`.
2. **Dedup** — bulk `WHERE job_id = ANY(array)` check against Supabase to skip existing postings.
3. **Transform** — `JobTransformer` applies HTML stripping, location normalisation, salary conversion, seniority classification, and skill extraction (Bronze → Silver).
4. **Load** — bulk upsert to Supabase with company stub handling (`ensure_company_stubs()` before `upsert_jobs()`).
5. **Promote** — apply manual enrichments and refresh Gold layer views.

## Data Sources

| Source | Auth | Free tier | Notes |
|---|---|---|---|
| [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | RapidAPI key | 200 req/month | Provides employer website → domain |
| [Adzuna](https://developer.adzuna.com) | App ID + App Key | 1,000 req/month | Remote inferred from text |
| [TheirStack](https://theirstack.com) | Bearer token | Varies | POST API; provides company URL and logo |
| [SerpAPI](https://serpapi.com) | API key | 250 searches/month | Google Jobs; salary/location parsed from strings; posted_at from relative time (EST) |

## Setup

### 1. Supabase

1. Create a free project at [supabase.com](https://supabase.com)
2. Run the migration files **in order** via the SQL Editor:
   - `sql/01_schema.sql` — tables: job_postings, companies, pipeline_runs
   - `sql/02_indexes.sql` — performance + GIN indexes
   - `sql/03_rls_policies.sql` — anon = SELECT only; service_role = full access
   - `sql/04_views.sql` — Gold layer views (v_jobs_enriched, v_province_stats, etc.)
3. Copy your **Project URL**, **service_role key**, and **anon key** from Settings → API

### 2. API Keys

- **JSearch**: [RapidAPI JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
- **Adzuna**: [developer.adzuna.com](https://developer.adzuna.com) — App ID + App Key
- **TheirStack**: [theirstack.com](https://theirstack.com) — API key
- **SerpAPI**: [serpapi.com](https://serpapi.com) — API key

### 3. Local development

```bash
cp .env.example .env
# Fill in all values in .env

pip install -r requirements.txt

# Run the pipeline
python -m pipeline.run_pipeline

# Run the dashboard
streamlit run dashboard/app.py

# Run tests
pytest tests/

# Analysis notebooks
# 01_bronze_quality.ipynb  — API field mapping & Bronze layer QA
# 02_silver_insights.ipynb — Market trends & salary visualisation
```

### 4. GitHub Actions

1. Push this repo to GitHub
2. Go to **Settings → Secrets → Actions** and add:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`
   - `JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`
   - `THEIRSTACK_API_KEY`, `SERPAPI_API_KEY`

The workflow runs on two triggers:
- **Push / PR to main** — runs `pytest tests/` only (no secrets needed)
- **Monday 06:00 UTC / manual** — runs tests first, then the pipeline if tests pass

### 5. Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) → New app
2. Point to this repo, branch `main`, main file `dashboard/app.py`
3. Add secrets (anon key only — **never** the service key):
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`

## Running Tests

```bash
pytest tests/
```

Tests cover all four API provider normalisers, deduplication logic, and the Silver-layer data cleaner. All tests use mocked HTTP and a mock Supabase client — no real keys or DB connection needed.

## Project Structure

```
DataScienceJobs/
├── .github/workflows/
│   └── weekly_pipeline.yml       # CI: tests on push/PR; pipeline gated on tests
├── .streamlit/
│   └── config.toml               # Native dark theme (bg, text, primary colour, font)
├── pipeline/
│   ├── providers/                # Class-based API clients
│   │   ├── base.py               # BaseJobSource ABC + shared helpers
│   │   ├── jsearch.py            # JSearch provider
│   │   ├── adzuna.py             # Adzuna provider
│   │   ├── theirstack.py         # TheirStack provider
│   │   └── serpapi.py            # SerpAPI provider
│   ├── models.py                 # JobDict schema contract (Bronze + Silver fields)
│   ├── transformer.py            # JobTransformer — Bronze → Silver logic
│   ├── data_cleaner.py           # Location, salary, seniority normalisation helpers
│   ├── skills_parser.py          # Keyword extraction — 73 skills
│   ├── supabase_client.py        # Bulk upsert helpers + pipeline run tracking
│   ├── deduplication.py          # Bulk job_id dedup
│   ├── run_pipeline.py           # Main orchestrator (JobPipeline class)
│   ├── backfill_data.py          # Re-run JobTransformer on all existing rows
│   └── explore_data_quality.py   # Diagnostic report on field coverage
├── dashboard/
│   ├── app.py                    # Streamlit entry point
│   ├── utils.py                  # Cached Supabase loaders (env → st.secrets fallback)
│   ├── ui_components.py          # Design system: colours, apply_theme(), helpers
│   ├── view_template.py          # Annotated starter template for new pages
│   └── pages/
│       ├── 01_Overview.py        # KPIs, seniority pie, weekly trend, pipeline runs
│       ├── 02_Companies.py       # Top companies, seniority dist, employment type
│       ├── 03_Salaries.py        # Box plot, histogram, top-paying roles
│       ├── 04_Location_Remote.py # Folium choropleth + city dot density — 4 metrics
│       └── 05_Skills.py          # Skills explorer — 73 skills, 4 categories
├── notebooks/
│   ├── 01_bronze_quality.ipynb   # API field mapping & Bronze layer QA
│   └── 02_silver_insights.ipynb  # Market trends & salary visualisation
├── sql/
│   ├── 01_schema.sql             # Tables: job_postings, companies, pipeline_runs
│   ├── 02_indexes.sql            # Performance indexes incl. GIN on skills_tags
│   ├── 03_rls_policies.sql       # Row-level security
│   └── 04_views.sql              # Gold layer: v_jobs_enriched, v_province_stats, etc.
├── tests/
│   ├── test_jsearch_client.py
│   ├── test_adzuna_client.py
│   ├── test_theirstack_client.py
│   ├── test_serpapi_client.py
│   ├── test_deduplication.py
│   └── test_data_cleaner.py
├── .env.example
├── requirements.txt
└── README.md
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| `BaseJobSource` + `JobDict` | Enforces a consistent data contract across all providers; adding a new source is a single-file change |
| `JobTransformer` as single source of truth | All Bronze → Silver logic lives in one class — backfill, live pipeline, and tests all use the same path |
| Medallion architecture | Bronze `_raw` columns preserve original API values; Silver holds cleaned values; enables re-processing without re-fetching |
| Bulk dedup via `ANY(array)` | One query per batch; also dedupes within-batch to avoid Supabase error 21000 |
| `company_domain` as FK | Normalised from employer URL; more stable than company name |
| Hourly → annual salary conversion | × 2080; original preserved in `_raw` columns |
| Fetch window: 15 days (Adzuna/TheirStack), month (JSearch), no filter (SerpAPI) | Wider window catches postings missed by a failed run; JSearch has no 15-day enum so `month` is the next option |
| `max_pages=10` per provider | Deeper pagination increases job yield; providers stop early when results are exhausted |
| Credit monitoring in providers | JSearch reads `x-ratelimit-requests-remaining` headers; SerpAPI calls `/account` — both log a WARNING when credits run low. Adzuna and TheirStack don't expose credits via API. |
| Anon key in dashboard | Read-only even if Streamlit secrets leak; service key stays in GitHub Actions only |
| `.streamlit/config.toml` for theme | Native Streamlit theming — no CSS injection needed for base palette |
| `ui_components.py` design system | Single source of truth for colours and layout helpers; pages never write raw CSS |
| Tests gate the pipeline | CI runs `pytest` on every push/PR; Monday cron only proceeds if tests pass |
| Folium + CartoDB tiles for map | Real map tiles with province choropleth + city dot density in one view; dark theme matches dashboard |
