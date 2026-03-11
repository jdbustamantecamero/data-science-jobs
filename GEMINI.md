# GEMINI.md — Project context for Gemini

## What this project is

Automated ETL pipeline + Streamlit dashboard for Canadian Data Scientist job postings.
Four job APIs → Supabase (PostgreSQL) → public Streamlit dashboard.
Pipeline follows a medallion architecture: Bronze (raw) → Silver (cleaned) → Gold (aggregated views).

## Common commands

```bash
# Run the pipeline locally (requires .env)
python -m pipeline.run_pipeline

# Run the dashboard locally
streamlit run dashboard/app.py

# One-time backfill (uses JobTransformer to re-process all rows)
python -m pipeline.backfill_data

# Data quality diagnostic report
python -m pipeline.explore_data_quality

# Run tests
pytest tests/

# Analysis Notebooks
# 01_bronze_quality.ipynb - Verifying API mapping
# 02_silver_insights.ipynb - Market trends & salary viz
```

## Medallion architecture (Optimized)

| Layer | Where | What |
|---|---|---|
| **Bronze** | `job_postings.*_raw` | 100% raw capture (16 columns). Original API values. |
| **Silver** | `job_postings` core | Cleaned, normalised, and enriched via `JobTransformer`. |
| **Gold** | Supabase views | Pre-aggregated logic (e.g., `v_province_stats`) for UI. |

## Key architecture rules

- **Job Sources**: Inherit from `BaseJobSource` in `pipeline/providers/`. All sources normalize to `JobDict` schema defined in `models.py`.
- **Transformation**: `JobTransformer` in `transformer.py` is the single source of truth for cleaning logic.
- **Deduplication**: Bulk check against `job_id` using `filter_new_jobs()`.
- **FK constraint**: `job_postings.company_domain` references `companies.domain`. Always call `ensure_company_stubs()` before `upsert_jobs()`.
- **Target country**: Canada. JSearch uses `country="ca"`, Adzuna uses `where="Canada"`, TheirStack uses `job_country_code_or=["CA"]`, SerpAPI uses `location="Canada"`.
- **SerpAPI pagination**: uses `next_page_token` from `serpapi_pagination` in each response — NOT `start` offset.
- **SQL Schema**: Consolidated into 4 canonical files (`sql/01_schema.sql` to `sql/04_views.sql`). All changes must be idempotent (`IF NOT EXISTS`).

## File structure quick reference

```
pipeline/run_pipeline.py    Main Orchestrator (JobPipeline class)
pipeline/providers/         BaseJobSource & source-specific implementations
pipeline/transformer.py     JobTransformer (Bronze -> Silver logic)
pipeline/models.py          JobDict type definitions (Bronze & Silver fields)
pipeline/data_cleaner.py    Location, Salary, Seniority normalization helpers
pipeline/skills_parser.py   Keyword extraction (optimized regex matching)
pipeline/supabase_client.py  Bulk upsert helpers & pipeline run tracking
pipeline/deduplication.py   Bulk job_id dedup against database
pipeline/backfill_data.py   Uses JobTransformer for scalable historical enrichment
dashboard/app.py            Streamlit entry point
sql/                        Canonical migrations (01-04)
notebooks/                  Analysis notebooks (01_bronze, 02_silver)
```

## Seniority levels

Ordered: `Intern → Junior → Mid → Senior → Lead → Director+`
Classification: Title match (priority) → Experience brackets → "Mid" default.

## Adding a new job source

1. Create `pipeline/providers/{source}.py` inheriting from `BaseJobSource`.
2. Implement `fetch_jobs` and `_map_to_job_dict` (populating `*_raw` fields).
3. Add to the provider list in `JobPipeline.__init__` within `run_pipeline.py`.
4. Add API key to `config.py` (`_require()`), `.env.example`, and `weekly_pipeline.yml`.
