"""Skills page — dark theme, CSS/flex gradient bars, dynamic KPIs."""
from __future__ import annotations

import html as _html
import pandas as pd
import streamlit as st

from utils import load_jobs

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Skills", page_icon="🛠️", layout="wide")

# ── theme CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #0d1b2a; }

[data-testid="stSidebar"] {
    background-color: #102035;
    border-right: 1px solid #1e3a5f;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stRadio > label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
    color: #a8c0d6 !important; font-size: 0.85rem;
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #e2eaf4 !important;
}

h1, h2, h3, h4, p, span, div { color: #e2eaf4; }

[data-testid="metric-container"] {
    background-color: #102035;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="metric-container"] label { color: #7fa8c9 !important; font-size: 0.78rem; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #e2eaf4 !important; }

hr { border-color: #1e3a5f; }
div[data-baseweb="select"] > div { background-color: #152d45 !important; color: #e2eaf4 !important; }

/* ── inline radio filter — padding set dynamically below ── */
div[data-testid="stRadio"] > div {
    flex-wrap: wrap;
    gap: 4px 16px;
    row-gap: 6px;
}
div[data-testid="stRadio"] label {
    color: #a8c0d6 !important;
    font-size: 0.875rem !important;
    cursor: pointer;
}
div[data-testid="stRadio"] label:has(input:checked) {
    color: #e2eaf4 !important;
    font-weight: 600 !important;
}
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.8rem;
    color: #7fa8c9;
}
</style>
""", unsafe_allow_html=True)

# ── skill display names (lowercase key → proper title) ───────────────────────
SKILL_DISPLAY_NAMES: dict[str, str] = {
    # Languages
    "python": "Python", "sql": "SQL", "r": "R", "java": "Java", "scala": "Scala",
    "julia": "Julia", "sas": "SAS", "matlab": "MATLAB", "bash": "Bash",
    # ML / Stats concepts
    "statistics": "Statistics", "machine learning": "Machine Learning",
    "deep learning": "Deep Learning", "generative ai": "Generative AI",
    "llm": "LLM", "nlp": "NLP", "computer vision": "Computer Vision",
    "reinforcement learning": "Reinforcement Learning",
    "time series": "Time Series", "a/b testing": "A/B Testing",
    "feature engineering": "Feature Engineering", "transformers": "Transformers",
    "anomaly detection": "Anomaly Detection", "forecasting": "Forecasting",
    # ML frameworks & libs
    "scikit-learn": "Scikit-Learn", "tensorflow": "TensorFlow",
    "pytorch": "PyTorch", "keras": "Keras", "xgboost": "XGBoost",
    "lightgbm": "LightGBM", "hugging face": "Hugging Face", "langchain": "LangChain",
    # Data / analytics
    "pandas": "Pandas", "numpy": "NumPy", "scipy": "SciPy",
    "matplotlib": "Matplotlib", "seaborn": "Seaborn", "plotly": "Plotly",
    "dask": "Dask",
    # BI / Viz
    "tableau": "Tableau", "power bi": "Power BI", "looker": "Looker",
    "excel": "Excel", "qlik": "Qlik",
    # Cloud
    "aws": "AWS", "azure": "Azure", "gcp": "GCP", "sagemaker": "SageMaker",
    "databricks": "DataBricks",
    # Warehouses & databases
    "snowflake": "Snowflake", "bigquery": "BigQuery", "redshift": "Redshift",
    "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB",
    "elasticsearch": "Elasticsearch",
    # Orchestration / pipelines
    "spark": "Spark", "hadoop": "Hadoop", "kafka": "Kafka",
    "airflow": "Airflow", "dbt": "DBT", "luigi": "Luigi",
    "prefect": "Prefect", "dagster": "Dagster",
    # MLOps / DevOps
    "mlflow": "MLflow", "kubeflow": "Kubeflow", "wandb": "W&B",
    "fastapi": "FastAPI", "flask": "Flask",
    "docker": "Docker", "kubernetes": "Kubernetes",
    "git": "Git", "linux": "Linux", "terraform": "Terraform",
}

# category → skill keys
CATEGORY_SKILLS: dict[str, list[str]] = {
    "Languages": [
        "python", "sql", "r", "java", "scala", "julia", "sas", "matlab", "bash",
    ],
    "Modeling": [
        "statistics", "machine learning", "deep learning", "generative ai",
        "llm", "nlp", "computer vision", "reinforcement learning",
        "time series", "a/b testing", "feature engineering",
        "transformers", "anomaly detection", "forecasting",
        "scikit-learn", "tensorflow", "pytorch", "keras",
        "xgboost", "lightgbm", "hugging face", "langchain", "mlflow",
    ],
    "Analytics": [
        "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly", "dask",
        "tableau", "power bi", "looker", "excel", "qlik",
    ],
    "Infrastructure": [
        "aws", "azure", "gcp", "sagemaker", "databricks",
        "snowflake", "bigquery", "redshift", "postgresql", "mysql",
        "mongodb", "elasticsearch",
        "spark", "hadoop", "kafka", "airflow", "dbt", "luigi",
        "prefect", "dagster",
        "docker", "kubernetes", "kubeflow", "wandb", "fastapi", "flask",
        "git", "linux", "terraform",
    ],
}

# skill key → category name
SKILL_CATEGORIES: dict[str, str] = {
    s: cat for cat, skills in CATEGORY_SKILLS.items() for s in skills
}

# category → hex color (including "All" sentinel)
CAT_COLORS: dict[str, str] = {
    "All":              "#475569",
    "Languages":        "#3b82f6",
    "Modeling": "#f472b6",
    "Analytics":        "#10b981",
    "Infrastructure":   "#f59e0b",
    "Other":            "#64748b",
}

CATEGORIES = ["All"] + list(CATEGORY_SKILLS.keys())

_TEXT    = "#e2eaf4"
_SUBTEXT = "#7fa8c9"

# ── layout spacing controls ───────────────────────────────────────────────────
# Title (h1)
TITLE_ML = 450   # px — title left margin
TITLE_MR = 0     # px — title right margin
TITLE_MB = 0     # px — gap below title before subtitle

# Subtitle (meta line)
SUB_ML   = 625   # px — subtitle left margin
SUB_MR   = 0     # px — subtitle right margin
SUB_MB   = 15     # px — gap below subtitle before KPIs

# KPI cards container
KPI_ML   = 150     # px — KPI row left margin
KPI_MR   = 150     # px — KPI row right margin
KPI_MB   = 0    # px — gap below KPIs before skill filter  ← controls KPI→filter gap

# Skill filter (radio) container
FILTER_ML = 455  # px — filter left margin  (keep in sync with LEFT_PAD below)
FILTER_MR = 0  # px — filter right margin (keep in sync with RIGHT_PAD below)
FILTER_MB = 15   # px — gap below filter before chart

# Chart wrapper
LEFT_PAD  = 215  # px — left gap: content edge → skill name column
RIGHT_PAD = 250  # px — right gap: chart → content edge

# ── session state (managed automatically by st.radio key below) ───────────────

# ── data ──────────────────────────────────────────────────────────────────────
jobs_df = load_jobs()
if jobs_df.empty:
    st.info("No job data available yet.")
    st.stop()

if "posted_at" in jobs_df.columns:
    jobs_df["posted_at"] = pd.to_datetime(jobs_df["posted_at"], utc=True, errors="coerce")

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛠️ Skills Explorer")
    st.markdown("---")

    top_n_label = st.radio("Show", ["Top 25", "All Skills"], index=0)
    top_n = 25 if top_n_label == "Top 25" else None

    st.markdown("---")
    timeframe = st.selectbox(
        "Timeframe", ["All Time", "Last 7 Days", "Last 30 Days", "YTD 2026"]
    )

    st.markdown("---")
    provinces = ["All Provinces"]
    if "location_state" in jobs_df.columns:
        provinces += sorted(jobs_df["location_state"].dropna().unique().tolist())
    province_filter = st.selectbox("Province", provinces)

# ── apply sidebar filters ─────────────────────────────────────────────────────
filtered = jobs_df.copy()
now_utc = pd.Timestamp.now(tz="UTC")
if timeframe == "Last 7 Days":
    filtered = filtered[filtered["posted_at"] >= now_utc - pd.Timedelta(days=7)]
elif timeframe == "Last 30 Days":
    filtered = filtered[filtered["posted_at"] >= now_utc - pd.Timedelta(days=30)]
elif timeframe == "YTD 2026":
    filtered = filtered[filtered["posted_at"] >= pd.Timestamp("2026-01-01", tz="UTC")]
if province_filter != "All Provinces":
    filtered = filtered[filtered["location_state"] == province_filter]

total_jobs = len(filtered)

# ── skill frequency ───────────────────────────────────────────────────────────
def build_freq(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "skills_tags" not in df.columns:
        return pd.DataFrame(columns=["skill", "count", "pct", "category", "display_name"])
    exploded = df["skills_tags"].explode().dropna()
    exploded = exploded[exploded != ""]
    if exploded.empty:
        return pd.DataFrame(columns=["skill", "count", "pct", "category", "display_name"])
    counts = exploded.value_counts().reset_index()
    counts.columns = ["skill", "count"]
    counts["pct"] = (counts["count"] / total_jobs * 100).round(1)
    counts["category"] = counts["skill"].map(SKILL_CATEGORIES).fillna("Other")
    counts["display_name"] = counts["skill"].map(SKILL_DISPLAY_NAMES).fillna(
        counts["skill"].str.title()
    )
    return counts


freq = build_freq(filtered)

# ── resolve current filter (reads previous run's value before radio renders) ──
category_filter: str = st.session_state.get("cat_filter", "All")
if category_filter not in CATEGORIES:
    category_filter = "All"

# ── apply category + top-n filters ───────────────────────────────────────────
freq_chart = (
    freq[freq["category"] == category_filter].copy()
    if category_filter != "All"
    else freq.copy()
)
if top_n:
    freq_chart = freq_chart.head(top_n)

# ── title ─────────────────────────────────────────────────────────────────────
label_parts = []
if province_filter != "All Provinces":
    label_parts.append(province_filter)
label_parts.append(timeframe)
st.markdown(
    f"<h1 style='margin-left:{TITLE_ML}px;margin-right:{TITLE_MR}px;"
    f"margin-bottom:{TITLE_MB}px !important'>Top Skills for Data Science</h1>"
    f"<p style='margin-left:{SUB_ML}px;margin-right:{SUB_MR}px;"
    f"margin-bottom:{SUB_MB}px;margin-top:0 !important;color:{_SUBTEXT};font-size:0.9rem'>"
    f"{' · '.join(label_parts)} · {total_jobs:,} jobs analysed</p>",
    unsafe_allow_html=True,
)
# ── KPIs (dynamic: based on category_filter + timeframe + province) ───────────
skills_tracked = (
    len(CATEGORY_SKILLS[category_filter])
    if category_filter != "All"
    else len(SKILL_DISPLAY_NAMES)
)
top_skill = freq_chart.iloc[0]["display_name"] if not freq_chart.empty else "—"
top_pct   = f"{freq_chart.iloc[0]['pct']:.1f}%" if not freq_chart.empty else "—"

_kpi_items = [
    ("Skills Tracked",  str(skills_tracked)),
    ("Skills Found",    str(len(freq_chart))),
    ("#1 Skill",        top_skill),
    ("#1 Mention Rate", top_pct),
]
_kpi_cards = "".join(
    f'<div style="background:#102035;border:1px solid #1e3a5f;border-radius:8px;padding:12px 16px; text-align:center">'
    f'<div style="color:#7fa8c9;font-size:0.78rem;margin-bottom:4px">{lbl}</div>'
    f'<div style="color:#e2eaf4;font-size:1.5rem;font-weight:600;line-height:1.2">{val}</div>'
    f'</div>'
    for lbl, val in _kpi_items
)
st.markdown(
    f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;'
    f'margin-left:{KPI_ML}px;margin-right:{KPI_MR}px;margin-bottom:{KPI_MB}px">'
    f'{_kpi_cards}</div>',
    unsafe_allow_html=True,
)

# ── inline radio category filter ──────────────────────────────────────────────
st.markdown(
    f"<style>[data-testid='stMainBlockContainer'] div[data-testid='stRadio']"
    f"{{padding-left:{FILTER_ML}px;padding-right:{FILTER_MR}px;"
    f"margin-bottom:{FILTER_MB}px}}</style>",
    unsafe_allow_html=True,
)
st.radio(
    "Skill category",
    CATEGORIES,
    index=CATEGORIES.index(category_filter),
    horizontal=True,
    key="cat_filter",
    label_visibility="collapsed",
)

# ── CSS/flex bar chart (fixed-height bars, widths scale with container) ───────
_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"

def _make_chart(plot_df: pd.DataFrame, cat_filter: str) -> str:
    n = len(plot_df)
    if n == 0:
        return ""

    BAR_H    = 15    # px — bar height
    ROW_MB   = 1     # px — gap between rows
    LABEL_W  = 130   # px — skill name column (pushes bars right)
    PCT_FS   = 15    # px — font size of the % label
    RADIUS   = "0 7px 7px 0"
    # LEFT_PAD / RIGHT_PAD → module-level constants above (line ~132)

    max_pct = plot_df["pct"].max()
    rows = []

    for i, row in enumerate(plot_df.itertuples()):
        width_pct = (row.pct / max_pct) * 100
        opacity   = round(1.0 - (i / max(n - 1, 1)) * 0.75, 3)

        fill = (
            CAT_COLORS.get(row.category, "#64748b")
            if cat_filter == "All"
            else CAT_COLORS.get(cat_filter, "#3b82f6")
        )

        label = _html.escape(row.display_name)

        rows.append(
            f'<div style="display:flex;align-items:center;margin-bottom:{ROW_MB}px">'
            # skill name — right-aligned, fixed width
            f'<div style="min-width:{LABEL_W}px;max-width:{LABEL_W}px;'
            f'text-align:right;padding-right:14px;'
            f'font-size:14px;color:{_TEXT};font-family:{_FONT};'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</div>'
            # bar + label container — fills remaining space
            f'<div style="flex:1;height:{BAR_H}px;display:flex;align-items:center">'
            f'<div style="height:100%;width:{width_pct:.2f}%;'
            f'background:{fill};opacity:{opacity};'
            f'border-radius:{RADIUS};flex-shrink:0"></div>'
            # % label — floats right next to bar end
            f'<span style="margin-left:10px;font-size:{PCT_FS}px;font-weight:700;'
            f'color:{fill};opacity:{opacity};font-family:{_FONT};white-space:nowrap">'
            f'{row.pct:.1f}%</span>'
            f'</div>'
            f'</div>'
        )

    return (
        f'<div style="width:100%;padding:4px {RIGHT_PAD}px 4px {LEFT_PAD}px">'
        + "".join(rows)
        + "</div>"
    )


if freq_chart.empty:
    st.info("No skill data matches the current filters.")
else:
    plot_df = freq_chart.sort_values("pct", ascending=False).reset_index(drop=True)
    st.markdown(_make_chart(plot_df, category_filter), unsafe_allow_html=True)
