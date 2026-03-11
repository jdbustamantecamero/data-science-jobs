# Data Science Jobs Pipeline

Automated, zero-cost pipeline that fetches **Data Scientist** job postings weekly from four Canadian job APIs, parses skills and seniority from descriptions, persists everything to Supabase (PostgreSQL), and serves insights on a public Streamlit dashboard.

## Architecture (3-Stage Medallion)

```
Ingest (Bronze) ──→ Transform (Silver) ──→ Promote (Gold)
      ↑                    ↑                    ↑
Raw API Data         Cleaned & Enriched      Aggregated Views
(16 _raw columns)    (Location, Salary)     (Dashboard Ready)
```

### Medallion ETL Layers

| Layer | Location | What |
|---|---|---|
| **Bronze** | `job_postings.*_raw` | 100% raw capture (16 columns). Original API values, never modified. |
| **Silver** | `job_postings` core | Cleaned, normalised, and enriched values (Skills, Seniority). |
| **Gold** | Supabase views | Pre-aggregated logic (e.g., `v_province_stats`) for the dashboard. |

### Pipeline Flow

1. **Ingest**: All providers (JSearch, Adzuna, TheirStack, SerpAPI) fetch in parallel via `BaseJobSource` subclasses.
2. **Dedup**: Bulk ID check against Supabase to skip existing postings.
3. **Transform**: `JobTransformer` applies cleaning (HTML strip, location normalization, salary conversion) and enrichment (skills/seniority).
4. **Load**: Bulk upsert to Supabase with company stub handling.
5. **Promote**: Apply manual enrichments and refresh views for the Gold layer.

## Setup

### 1. Supabase

1. Create a free project at [supabase.com](https://supabase.com).
2. In the SQL Editor, run the canonical migration files **in order**:
   - `sql/01_schema.sql` (Tables: jobs, companies, runs)
   - `sql/02_indexes.sql` (Performance & GIN indexes)
   - `sql/03_rls_policies.sql` (Security)
   - `sql/04_views.sql` (Gold layer views)

### 2. Local Development

```bash
cp .env.example .env
# Fill in Supabase and API keys in .env

pip install -r requirements.txt

# Run the pipeline
python -m pipeline.run_pipeline

# Run the dashboard
streamlit run dashboard/app.py

# Analysis Notebooks
# 01_bronze_quality.ipynb - Verifying API mapping
# 02_silver_insights.ipynb - Market trends & salary viz
```

## Project Structure

```
DataScienceJobs/
├── pipeline/
│   ├── providers/          # Class-based API clients (JSearch, Adzuna, etc.)
│   ├── models.py           # JobDict schema contract
│   ├── transformer.py      # JobTransformer (Bronze -> Silver logic)
│   ├── data_cleaner.py     # Location/Salary normalization helpers
│   ├── skills_parser.py    # Scalable keyword extraction (73 skills)
│   ├── run_pipeline.py     # Main Orchestrator (Ingest -> Transform -> Promote)
│   └── ...
├── dashboard/
│   ├── pages/              # Streamlit pages (Overview, Salaries, Skills, etc.)
│   └── ui_components.py    # Unified design system
├── sql/
│   └── 01-04_*.sql         # Canonical squashed migrations
├── notebooks/
│   ├── 01_bronze_quality.ipynb
│   └── 02_silver_insights.ipynb
└── tests/                  # Mocked unit tests for all components
```
