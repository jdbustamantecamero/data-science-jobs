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

# One-time backfill (re-runs cleaning/skills/seniority on all existing rows)
venv/bin/python -m pipeline.backfill_data

# Data quality diagnostic report
venv/bin/python -m pipeline.explore_data_quality

# Run tests
pytest tests/

# Open exploration notebook
venv/bin/jupyter notebook notebooks/explore.ipynb
```

## Medallion architecture

| Layer | Where | What |
|---|---|---|
| **Bronze** | `job_postings.*_raw` columns | Original API values captured before any cleaning |
| **Silver** | `job_postings` core columns | Cleaned, normalised, enriched values |
| **Gold** | Supabase views | Pre-aggregated for dashboard consumption |

Bronze columns: `location_city_raw`, `location_state_raw`, `location_country_raw`, `salary_min_raw`, `salary_max_raw`, `salary_period_raw`. Written once at insert, never updated. Silver columns hold the cleaned equivalents.

## Key architecture rules

- **Four job sources**: JSearch (`jsearch_client.py`), Adzuna (`adzuna_client.py`), TheirStack (`theirstack_client.py`), SerpAPI (`serpapi_client.py`). All normalise to the same dict shape before anything downstream touches them.
- **job_id prefixes**: JSearch IDs are plain. Adzuna prefixes `adzuna_`. TheirStack prefixes `theirstack_`. SerpAPI prefixes `serpapi_`. Never change this — it prevents cross-source collisions in the dedup table.
- **No Apollo**: Apollo enrichment was removed (free tier too limiting). Do not re-add it. Company records are minimal stubs (domain + name only). Apollo columns were also removed from the `companies` table.
- **Dedup is bulk**: `deduplication.py` issues a single `WHERE job_id = ANY(array)` query. Never replace with per-job queries.
- **Upsert dedup within batch**: `upsert_jobs()` in `supabase_client.py` dedupes by `job_id` before the upsert call to avoid Supabase error code 21000. Keep this.
- **FK constraint**: `job_postings.company_domain` references `companies.domain`. Always call `ensure_company_stubs()` before `upsert_jobs()`.
- **Pipeline step order**: Bronze snapshot → `clean_description` → `extract_years_experience` → `classify_seniority` → `extract_skills` → location normalisation → salary normalisation. Order matters — skills and seniority run on the cleaned description, and Bronze must be captured before any Silver transformation.
- **Target country**: Canada. JSearch uses `country="ca"`, Adzuna uses `where="Canada"`, TheirStack uses `job_country_code_or=["CA"]`, SerpAPI uses `location="Canada"` (no `gl` — combining both causes 400).
- **SerpAPI pagination**: uses `next_page_token` from `serpapi_pagination` in each response — NOT `start` offset (that's regular Google Search and causes 400 on `google_jobs`).
- **SerpAPI timezone**: `posted_at` is computed from relative strings ("3 days ago") using `ZoneInfo("America/Toronto")` (EST/EDT). Only SerpAPI needs this — the other three APIs return pre-timestamped strings from their servers.
- **Salary currency**: CAD. Both the DB column default and the pipeline fallback.
- **Hourly salary conversion**: `normalize_salary()` in `data_cleaner.py` converts hourly rates (period=HOUR) to annual (× 2080). Original values preserved in `salary_min_raw`, `salary_max_raw`, `salary_period_raw`.

## Location normalisation rules

All handled by `data_cleaner.py` before writing to Silver:
- Accents stripped: "Québec" → "Quebec", "Montréal" → "Montreal"
- Province abbreviations expanded: "QC" → "Quebec", "ON" → "Ontario", etc.
- Country normalised: "CA" → "Canada", null → "Anywhere"
- City aliases resolved: "Greater Vancouver" → "Vancouver", "Hamilton region" → "Hamilton", "King and Spadina" → "Toronto"
- Missing province inferred from city lookup table (`_CITY_TO_PROVINCE`)
- Missing city/province inferred from description using "City, AB" pattern scan

## File structure quick reference

```
pipeline/run_pipeline.py        Main entry point — Bronze snapshot + Silver cleaning here
pipeline/data_cleaner.py        HTML strip, location normalisation, salary normalisation, seniority
pipeline/skills_parser.py       Keyword extraction — 73 skills, edit SKILLS list to change
pipeline/serpapi_client.py      SerpAPI: salary/location/date parsed from raw strings; EST timezone
pipeline/supabase_client.py     All DB writes; add new upsert helpers here
pipeline/deduplication.py       Bulk job_id dedup against DB
pipeline/backfill_data.py       One-time script: re-runs all Silver enrichment on existing rows
pipeline/explore_data_quality.py Diagnostic report on field coverage and data quality
pipeline/config.py              All env vars; use _require() for mandatory keys
dashboard/utils.py              All Supabase reads for dashboard; add loaders here
dashboard/ui_components.py      Design system — colour constants, apply_theme(), helpers (see below)
dashboard/view_template.py      Annotated starter template — copy when adding a new page
dashboard/pages/04_Location_Remote.py  Canada choropleth map — 4 switchable metrics
dashboard/pages/05_Skills.py    Skills explorer; SKILL_CATEGORIES must sync with skills_parser.SKILLS
notebooks/explore.ipynb         Jupyter notebook for ad-hoc data exploration
sql/                            Migration files 01→10; apply via Supabase MCP or SQL Editor
.streamlit/config.toml          Native Streamlit dark theme (background, text, primary colour, font)
```

## Dashboard UI design system

The dashboard theme has two layers:

1. **`.streamlit/config.toml`** — sets `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `primaryColor`, `font`. Streamlit applies these natively before any Python runs. Update this file when changing the base palette.

2. **`dashboard/ui_components.py`** — CSS overrides that `config.toml` cannot express (borders, label styles, responsive breakpoints) plus Python helpers. Exports:
   - `apply_theme()` — call once per page, right after `st.set_page_config()`
   - `center_layout(max_width=920)` — centres the main content block; call after `apply_theme()` on chart-heavy pages
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
- `SKILL_DISPLAY_NAMES` and `CATEGORY_SKILLS` in `05_Skills.py` must stay in sync with `skills_parser.SKILLS` (73 skills across 4 categories).

## Dashboard rules

- Dashboard pages import from `utils` (not `dashboard.utils`) — Streamlit adds `dashboard/` to sys.path for pages.
- All data loaders in `utils.py` use `@st.cache_data(ttl=3600)`.
- Env var priority: `os.environ` first, then `st.secrets`. This is set in `utils.py:get_client()`.
- Never use the service key in the dashboard. Anon key only.
- The dashboard reads from `v_jobs_enriched` (a view joining `job_postings` + `companies`, including both Silver and Bronze columns).
- Location page (`04_Location_Remote.py`) is a full-width Canada choropleth map with 4 switchable metrics: Job Volume, Remote Rate, Senior+ Rate, Avg Salary. GeoJSON fetched from CDN and cached 24h.

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

## Adding a new dashboard page

1. Copy `dashboard/view_template.py` to `dashboard/pages/NN_YourPage.py`
2. Replace all `TODO` values
3. Call `apply_theme()` right after `st.set_page_config()`
4. Call `center_layout()` if the page is chart-heavy and benefits from centred content
5. Use `page_header()`, `kpi_row()`, `section_divider()` — never write raw CSS

## SQL migration pattern

New schema changes go in a new numbered file (`sql/NN_description.sql`). Always use `IF NOT EXISTS` / `IF EXISTS` guards so files are safe to re-run. Apply via the Supabase MCP (`apply_migration` tool) — no manual SQL Editor needed. Current files: 01–10.

## Supabase MCP

Configured in `.mcp.json` (gitignored — contains PAT). Provides `execute_sql`, `apply_migration`, `list_tables` and more. Use `apply_migration` for all DDL (tracked in Supabase migration history). Use `execute_sql` for queries and data checks.

## GitHub Actions

Two jobs in `.github/workflows/weekly_pipeline.yml`:

- **`test`** — runs `pytest tests/ -v` on every push and PR to `main`. No secrets needed (all mocked).
- **`run-pipeline`** — runs only on `schedule` (Monday 06:00 UTC) and `workflow_dispatch`. Blocked by `needs: test`, so a failing test prevents the pipeline from running.

Secrets required (set in GitHub → Settings → Secrets → Actions):
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`,
`JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `THEIRSTACK_API_KEY`, `SERPAPI_API_KEY`

## Timezone note

Only SerpAPI computes timestamps locally (converting "3 days ago" → absolute datetime).
It uses `ZoneInfo("America/Toronto")` for EST/EDT. The other three APIs return
pre-timestamped strings from their own servers and need no local timezone handling.
