# CLAUDE.md — Project context for Claude Code

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

# One-time backfill (re-runs JobTransformer on all existing rows)
python -m pipeline.backfill_data

# Data quality diagnostic report
python -m pipeline.explore_data_quality

# Run tests
pytest tests/

# Analysis notebooks
# 01_bronze_quality.ipynb  — API field mapping & Bronze layer QA
# 02_silver_insights.ipynb — Market trends & salary visualisation
```

## Medallion architecture

| Layer | Where | What |
|---|---|---|
| **Bronze** | `job_postings.*_raw` | 100% raw capture. Original API values, never modified after insert. |
| **Silver** | `job_postings` core columns | Cleaned, normalised, enriched via `JobTransformer`. |
| **Gold** | Supabase views | Pre-aggregated logic (e.g. `v_province_stats`) for the dashboard. |

Bronze raw fields are populated by each provider's `_map_to_job_dict()` method before any transformation. Silver columns are written by `JobTransformer`.

## Key architecture rules

- **Providers**: All API clients inherit from `BaseJobSource` in `pipeline/providers/base.py`. Each implements `fetch_jobs()` and `_map_to_job_dict()`, returning a `JobDict` (defined in `models.py`). Never write provider logic outside `pipeline/providers/`.
- **JobTransformer**: Single source of truth for Bronze → Silver logic (`pipeline/transformer.py`). Backfill, live pipeline, and tests all run through the same class.
- **JobDict**: The data contract. Both Bronze (`*_raw`) and Silver fields are defined in `pipeline/models.py`. Never add ad-hoc keys outside this schema.
- **job_id prefixes**: JSearch IDs are plain. Adzuna prefixes `adzuna_`. TheirStack prefixes `theirstack_`. SerpAPI prefixes `serpapi_`. Never change — prevents cross-source collisions.
- **No Apollo**: Removed (free tier too limiting). Company records are minimal stubs (domain + name only). Do not re-add.
- **Dedup is bulk**: `filter_new_jobs()` in `deduplication.py` issues a single `WHERE job_id = ANY(array)` query. Never replace with per-job queries.
- **Upsert dedup within batch**: `upsert_jobs()` in `supabase_client.py` dedupes by `job_id` before the upsert call to avoid Supabase error code 21000. Keep this.
- **FK constraint**: `job_postings.company_domain` references `companies.domain`. Always call `ensure_company_stubs()` before `upsert_jobs()`.
- **Pipeline step order**: Bronze snapshot → `clean_description` → `extract_years_experience` → `classify_seniority` → `extract_skills` → location normalisation → employment type normalisation → salary normalisation. Order matters — skills and seniority run on the cleaned description.
- **Target country**: Canada. JSearch uses `country="ca"`, Adzuna uses `where="Canada"`, TheirStack uses `job_country_code_or=["CA"]`, SerpAPI uses `location="Canada"` (no `gl` — causes 400).
- **SerpAPI pagination**: uses `next_page_token` from `serpapi_pagination` — NOT `start` offset (causes 400 on `google_jobs`).
- **SerpAPI timezone & timestamps**: SerpAPI returns relative timestamps ("3 days ago", "2 hours ago"). These are converted to absolute ISO 8601 UTC timestamps via `convert_relative_timestamp()` in `data_cleaner.py` using `ZoneInfo("America/Toronto")` as the reference. Only SerpAPI needs this conversion.
- **Salary currency**: CAD. Both DB column default and pipeline fallback.
- **Hourly salary conversion**: × 2080 in `JobTransformer`. Original preserved in `salary_min_raw`, `salary_max_raw`, `salary_period_raw`.
- **SQL schema**: Consolidated into 4 canonical files (`sql/01_schema.sql` → `sql/04_views.sql`). All DDL must be idempotent (`IF NOT EXISTS` / `IF EXISTS`). Apply via Supabase MCP `apply_migration`.

## Location normalisation rules

All handled by `data_cleaner.py` helpers, called by `JobTransformer`:
- Accents stripped: "Québec" → "Quebec", "Montréal" → "Montreal"
- Province abbreviations expanded: "QC" → "Quebec", "ON" → "Ontario", etc.
- Country normalised: "CA" → "Canada", null → "Anywhere"
- City aliases resolved: "Greater Vancouver" → "Vancouver", etc.
- Missing province inferred from city lookup (`_CITY_TO_PROVINCE`)
- Missing city/province inferred from description via "City, AB" pattern scan

## Employment type normalisation rules

All handled by `normalize_employment_type()` in `data_cleaner.py`, called by `JobTransformer`:
- Standardizes across API providers: `FULL_TIME` → `"Full-time"`, `full-time` → `"Full-time"`, `fulltime` → `"Full-time"`
- Canonical categories: `"Full-time"`, `"Part-time"`, `"Contract"`, `"Internship"`
- Maps common variations: `FT` → `"Full-time"`, `PT` → `"Part-time"`, `permanent` → `"Full-time"`, `temp` → `"Contract"`
- Prevents duplicate/inconsistent employment type categories in dashboards

## File structure quick reference

```
pipeline/run_pipeline.py          Main orchestrator — JobPipeline class
pipeline/providers/base.py        BaseJobSource ABC + shared helpers
pipeline/providers/jsearch.py     JSearch provider
pipeline/providers/adzuna.py      Adzuna provider
pipeline/providers/theirstack.py  TheirStack provider
pipeline/providers/serpapi.py     SerpAPI provider
pipeline/models.py                JobDict schema contract (Bronze + Silver fields)
pipeline/transformer.py           JobTransformer — Bronze → Silver logic
pipeline/data_cleaner.py          Location, salary, seniority normalisation helpers
pipeline/skills_parser.py         Keyword extraction — 73 skills
pipeline/supabase_client.py       Bulk upsert helpers + pipeline run tracking
pipeline/deduplication.py         Bulk job_id dedup
pipeline/backfill_data.py         Re-run JobTransformer on all existing rows
pipeline/explore_data_quality.py  Diagnostic report on field coverage
dashboard/utils.py                All Supabase reads for dashboard; add loaders here
dashboard/ui_components.py        Design system — colour constants, apply_theme(), helpers
dashboard/view_template.py        Annotated starter template — copy when adding a new page
dashboard/pages/04_Location_Remote.py  Folium choropleth + city dot density — 4 metrics
dashboard/pages/05_Skills.py      Skills explorer; Timeframe + Province + Seniority filters; SKILL_CATEGORIES must sync with skills_parser.SKILLS
notebooks/01_bronze_quality.ipynb API field mapping & Bronze layer QA
notebooks/02_silver_insights.ipynb Market trends & salary visualisation
sql/01_schema.sql                 Tables: job_postings, companies, pipeline_runs
sql/02_indexes.sql                Performance + GIN indexes
sql/03_rls_policies.sql           Row-level security
sql/04_views.sql                  Gold layer views
.streamlit/config.toml            Native dark theme (background, text, primary colour, font)
```

## Dashboard UI design system

The dashboard theme has two layers:

1. **`.streamlit/config.toml`** — sets `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `primaryColor`, `font`. Streamlit applies these natively before any Python runs. Update this file when changing the base palette.

2. **`dashboard/ui_components.py`** — CSS overrides that `config.toml` cannot express (borders, label styles, responsive breakpoints) plus Python helpers. Exports:
   - `apply_theme()` — call once per page, right after `st.set_page_config()`
   - `center_layout(max_width=920)` — centres the main content block
   - `page_header(title, subtitle)` — consistent `st.title()` + muted subtitle line
   - `kpi_row(items)` — responsive KPI row using native `st.metric` + `st.columns`
   - `kpi_row_html(items)` — KPI cards as a responsive CSS grid (`dsj-kpi-grid` class)
   - `section_divider(label)` — styled `<hr>` with optional centred label
   - `empty_state(message)` — centred no-data placeholder
   - `badge(text, color)` — inline HTML pill for `st.markdown`
   - Colour constants: `BG`, `SURFACE`, `BORDER`, `TEXT`, `SUBTEXT`, `MUTED`, `ACCENT_*`

**Rules:**
- Never write raw CSS hex colours or pixel margins in a page file. Import constants from `ui_components`.
- Never inject a full theme CSS block in a page. Call `apply_theme()` instead.
- Use `view_template.py` as the starting point for every new page.
- `SKILL_DISPLAY_NAMES` and `CATEGORY_SKILLS` in `05_Skills.py` must stay in sync with `skills_parser.SKILLS` (73 skills).

## Dashboard rules

- Dashboard pages import from `utils` (not `dashboard.utils`) — Streamlit adds `dashboard/` to sys.path.
- All data loaders in `utils.py` use `@st.cache_data(ttl=3600)`.
- Env var priority: `os.environ` first, then `st.secrets`. Set in `utils.py:get_client()`.
- Never use the service key in the dashboard. Anon key only.
- The dashboard reads from `v_jobs_enriched` (Gold view joining `job_postings` + `companies`).
- Location page (`04_Location_Remote.py`) uses Folium + CartoDB Dark Matter tiles: province choropleth with 4 switchable metrics + city dot density layer. GeoJSON fetched from CDN and cached 24h.

## Seniority levels

Ordered: `Intern → Junior → Mid → Senior → Lead → Director+`

Classification priority (in `JobTransformer`):
1. Title keyword match (`data_cleaner._TITLE_RULES`)
2. `years_experience_min` brackets (0–2 Junior, 3–5 Mid, 6–9 Senior, 10+ Lead)
3. Default: `"Mid"`

## Adding a new job source

1. Create `pipeline/providers/{source}.py` inheriting from `BaseJobSource`
2. Implement `fetch_jobs()` and `_map_to_job_dict()` — populate all `*_raw` fields in `JobDict`
3. Prefix `job_id` with `{source}_`
4. Register in `JobPipeline.__init__()` in `run_pipeline.py`
5. Add API key to `config.py` (`_require()`), `.env.example`, and `weekly_pipeline.yml`
6. Add tests in `tests/test_{source}_client.py`

## Adding a new dashboard page

1. Copy `dashboard/view_template.py` to `dashboard/pages/NN_YourPage.py`
2. Replace all `TODO` values
3. Call `apply_theme()` right after `st.set_page_config()`
4. Call `center_layout()` if the page benefits from centred content
5. Use `page_header()`, `kpi_row()`, `section_divider()` — never write raw CSS

## SQL migration pattern

New schema changes go in `sql/04_views.sql` (for views) or the appropriate canonical file. All statements must be idempotent (`IF NOT EXISTS` / `OR REPLACE`). Apply via the Supabase MCP `apply_migration` tool.

## Supabase MCP

Configured in `.mcp.json` (gitignored — contains PAT). Provides `execute_sql`, `apply_migration`, `list_tables` and more. Use `apply_migration` for DDL. Use `execute_sql` for queries and data checks.

## GitHub Actions

Two jobs in `.github/workflows/weekly_pipeline.yml`:

- **`test`** — runs `pytest tests/ -v` on every push and PR to `main`. No secrets needed (all mocked).
- **`run-pipeline`** — runs only on `schedule` (Monday 06:00 UTC) and `workflow_dispatch`. Blocked by `needs: test`.

Secrets required: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`,
`JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `THEIRSTACK_API_KEY`, `SERPAPI_API_KEY`

## Timezone note

Only SerpAPI computes timestamps locally (converting "3 days ago" → absolute datetime).
Uses `ZoneInfo("America/Toronto")` for EST/EDT. The other three APIs return pre-timestamped strings.
