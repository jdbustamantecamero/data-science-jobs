"""Canada choropleth map — switchable metrics by province."""
from __future__ import annotations

import json
import unicodedata
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import load_jobs

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Location", page_icon="🗺️", layout="wide")

# ── theme ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

*, body { font-family: 'DM Sans', sans-serif; }

.stApp { background-color: #0d1b2a; }

[data-testid="stSidebar"] {
    background-color: #0a1520;
    border-right: 1px solid #1e3a5f;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #7fa8c9 !important; font-size: 0.85rem; }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #e2eaf4 !important; }

h1, h2, h3, h4, p, span, div { color: #e2eaf4; }

[data-testid="metric-container"] {
    background-color: #102035;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 14px 18px;
}
[data-testid="metric-container"] label { color: #7fa8c9 !important; font-size: 0.75rem; letter-spacing: 0.05em; text-transform: uppercase; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #e2eaf4 !important; font-size: 1.6rem !important; font-weight: 600; }

hr { border-color: #1e3a5f; }

div[data-baseweb="select"] > div { background-color: #102035 !important; color: #e2eaf4 !important; border-color: #1e3a5f !important; }

div[data-testid="stRadio"] > div { flex-wrap: wrap; gap: 6px 20px; }
div[data-testid="stRadio"] label { color: #7fa8c9 !important; font-size: 0.875rem !important; cursor: pointer; }
div[data-testid="stRadio"] label:has(input:checked) { color: #e2eaf4 !important; font-weight: 600 !important; }

.stDataFrame { background: #102035; border-radius: 8px; border: 1px solid #1e3a5f; }

[data-testid="stPlotlyChart"] { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── constants ─────────────────────────────────────────────────────────────────
ALL_PROVINCES = [
    "Alberta", "British Columbia", "Manitoba", "New Brunswick",
    "Newfoundland and Labrador", "Northwest Territories", "Nova Scotia",
    "Nunavut", "Ontario", "Prince Edward Island", "Quebec",
    "Saskatchewan", "Yukon",
]

_PROVINCE_CODES = {
    "Alberta": "CA-AB", "British Columbia": "CA-BC", "Manitoba": "CA-MB",
    "New Brunswick": "CA-NB", "Newfoundland and Labrador": "CA-NL",
    "Northwest Territories": "CA-NT", "Nova Scotia": "CA-NS",
    "Nunavut": "CA-NU", "Ontario": "CA-ON", "Prince Edward Island": "CA-PE",
    "Quebec": "CA-QC", "Saskatchewan": "CA-SK", "Yukon": "CA-YT",
}

SENIOR_LABELS = {"Senior", "Lead", "Director+"}

GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood"
    "/master/public/data/canada.geojson"
)

METRIC_CONFIG = {
    "Job Volume": {
        "col": "job_count",
        "label": "Job Postings",
        "colorscale": [[0, "#0d2137"], [0.3, "#1e3a6e"], [1, "#3b82f6"]],
        "fmt": lambda v: f"{int(v):,}" if pd.notna(v) else "—",
        "unit": "",
        "note": None,
        "accent": "#3b82f6",
    },
    "Remote Rate": {
        "col": "remote_rate",
        "label": "Remote Rate",
        "colorscale": [[0, "#0d2137"], [0.3, "#7c3d0c"], [1, "#f59e0b"]],
        "fmt": lambda v: f"{v:.0f}%" if pd.notna(v) else "—",
        "unit": "%",
        "note": None,
        "accent": "#f59e0b",
    },
    "Senior+ Rate": {
        "col": "senior_rate",
        "label": "Senior / Lead / Director+",
        "colorscale": [[0, "#0d2137"], [0.3, "#6b1a6b"], [1, "#f472b6"]],
        "fmt": lambda v: f"{v:.0f}%" if pd.notna(v) else "—",
        "unit": "%",
        "note": "Senior+ includes Senior, Lead, and Director+ seniority levels.",
        "accent": "#f472b6",
    },
    "Avg Salary": {
        "col": "avg_salary",
        "label": "Avg Salary (CAD)",
        "colorscale": [[0, "#0d2137"], [0.3, "#064e3b"], [1, "#10b981"]],
        "fmt": lambda v: f"${v/1000:.0f}k" if pd.notna(v) else "—",
        "unit": "CAD",
        "note": "Only ~15% of postings include salary data. Unshaded provinces have no salary records.",
        "accent": "#10b981",
    },
}

# ── GeoJSON (cached) ──────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_geojson() -> dict:
    import urllib.request
    with urllib.request.urlopen(GEOJSON_URL) as r:
        geojson = json.loads(r.read())
    # Normalize province names: strip accents so "Québec" → "Quebec"
    for feature in geojson.get("features", []):
        raw_name = feature.get("properties", {}).get("name", "")
        normalized = "".join(
            c for c in unicodedata.normalize("NFD", raw_name)
            if unicodedata.category(c) != "Mn"
        )
        feature["properties"]["name"] = normalized
    return geojson

# ── data ──────────────────────────────────────────────────────────────────────
df_all = load_jobs()

if df_all.empty:
    st.info("No job data available yet.")
    st.stop()

if "posted_at" in df_all.columns:
    df_all["posted_at"] = pd.to_datetime(df_all["posted_at"], utc=True, errors="coerce")

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗺️ Location Explorer")
    st.markdown("---")
    timeframe = st.selectbox(
        "Timeframe",
        ["All Time", "Last 30 Days", "Last 90 Days", "YTD 2026"],
    )

# ── timeframe filter ──────────────────────────────────────────────────────────
now_utc = pd.Timestamp.now(tz="UTC")
df = df_all.copy()
if timeframe == "Last 30 Days":
    df = df[df["posted_at"] >= now_utc - pd.Timedelta(days=30)]
elif timeframe == "Last 90 Days":
    df = df[df["posted_at"] >= now_utc - pd.Timedelta(days=90)]
elif timeframe == "YTD 2026":
    df = df[df["posted_at"] >= pd.Timestamp("2026-01-01", tz="UTC")]

# ── per-province aggregation ──────────────────────────────────────────────────
prov_df = df[df["location_state"].notna()].copy()

def _top_skill(tags_series: pd.Series) -> str:
    c: Counter = Counter()
    for tags in tags_series.dropna():
        for sk in (tags if isinstance(tags, list) else []):
            c[sk] += 1
    return c.most_common(1)[0][0].title() if c else "—"

def _dominant_seniority(s: pd.Series) -> str:
    counts = s.dropna().value_counts()
    return counts.index[0] if not counts.empty else "—"

if not prov_df.empty:
    grp = prov_df.groupby("location_state")

    jobs_by_prov = grp.size().rename("job_count")

    remote_series = prov_df[prov_df["is_remote"].notna()].groupby("location_state")["is_remote"].apply(
        lambda x: round(100 * x.astype(bool).sum() / len(x), 1)
    ).rename("remote_rate")

    if "seniority" in prov_df.columns:
        prov_df["is_senior"] = prov_df["seniority"].isin(SENIOR_LABELS)
    else:
        prov_df["is_senior"] = False
    senior_series = grp["is_senior"].apply(
        lambda x: round(100 * x.sum() / len(x), 1)
    ).rename("senior_rate")

    sal_series = (
        prov_df[prov_df["salary_min"].notna()]
        .groupby("location_state")["salary_min"].mean()
        .rename("avg_salary")
    )

    top_skill_series = grp["skills_tags"].apply(_top_skill).rename("top_skill")
    seniority_col = prov_df["seniority"] if "seniority" in prov_df.columns else pd.Series(dtype=str)
    dom_seniority_series = (
        prov_df[prov_df["seniority"].notna()].groupby("location_state")["seniority"].apply(_dominant_seniority)
        if "seniority" in prov_df.columns
        else pd.Series(dtype=str)
    ).rename("dominant_seniority")

    stats = pd.concat(
        [jobs_by_prov, remote_series, senior_series, sal_series,
         top_skill_series, dom_seniority_series],
        axis=1,
    ).reset_index()
    stats.columns = ["province", "job_count", "remote_rate", "senior_rate",
                     "avg_salary", "top_skill", "dominant_seniority"]
else:
    stats = pd.DataFrame(columns=["province", "job_count", "remote_rate", "senior_rate",
                                   "avg_salary", "top_skill", "dominant_seniority"])

# Complete DataFrame with all 13 provinces (NaN for missing)
complete_stats = pd.DataFrame({"province": ALL_PROVINCES}).merge(stats, on="province", how="left")

# ── national KPIs ─────────────────────────────────────────────────────────────
total_with_province = int(stats["job_count"].sum()) if not stats.empty else 0
provinces_active = int((stats["job_count"] > 0).sum()) if not stats.empty else 0

remote_known = df[df["is_remote"].notna()]
national_remote = (
    round(100 * remote_known["is_remote"].astype(bool).sum() / len(remote_known), 1)
    if not remote_known.empty else 0.0
)
if "seniority" in df.columns:
    senior_known = df[df["seniority"].notna()]
    national_senior = (
        round(100 * senior_known["seniority"].isin(SENIOR_LABELS).sum() / len(senior_known), 1)
        if not senior_known.empty else 0.0
    )
else:
    national_senior = 0.0

# ── header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='margin-bottom:2px'>🗺️ Regional Job Market</h1>"
    f"<p style='color:#7fa8c9;font-size:0.9rem;margin-top:0;margin-bottom:20px'>"
    f"Data Science roles across Canada · {timeframe} · {len(df):,} jobs analysed</p>",
    unsafe_allow_html=True,
)

# KPI cards
k1, k2, k3, k4 = st.columns(4)
k1.metric("Jobs with Location", f"{total_with_province:,}")
k2.metric("Provinces Active", str(provinces_active))
k3.metric("National Remote Rate", f"{national_remote:.0f}%")
k4.metric("National Senior+ Rate", f"{national_senior:.0f}%")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── metric selector ───────────────────────────────────────────────────────────
metric_choice = st.radio(
    "Map metric",
    list(METRIC_CONFIG.keys()),
    horizontal=True,
    label_visibility="collapsed",
)
cfg = METRIC_CONFIG[metric_choice]

if cfg["note"]:
    st.info(cfg["note"])

# ── choropleth map ────────────────────────────────────────────────────────────
geojson = load_geojson()

# Build hover text
def _fmt_sal(v):
    return f"${v/1000:.0f}k" if pd.notna(v) else "n/a"

def _fmt_pct(v):
    return f"{v:.0f}%" if pd.notna(v) else "n/a"

complete_stats["hover"] = complete_stats.apply(
    lambda r: (
        f"<b>{r['province']}</b><br>"
        f"Jobs: {int(r['job_count']) if pd.notna(r.get('job_count')) else 'n/a'}<br>"
        f"Remote: {_fmt_pct(r.get('remote_rate'))}<br>"
        f"Senior+: {_fmt_pct(r.get('senior_rate'))}<br>"
        f"Avg Salary: {_fmt_sal(r.get('avg_salary'))}<br>"
        f"Top Skill: {r.get('top_skill') or '—'}<br>"
        f"Dominant: {r.get('dominant_seniority') or '—'}"
    ),
    axis=1,
)

col_data = complete_stats[cfg["col"]]
z_min = col_data.min(skipna=True)
z_max = col_data.max(skipna=True)

fig_map = px.choropleth(
    complete_stats,
    geojson=geojson,
    locations="province",
    featureidkey="properties.name",
    color=cfg["col"],
    color_continuous_scale=cfg["colorscale"],
    range_color=[z_min, z_max] if pd.notna(z_min) and pd.notna(z_max) else None,
    custom_data=["hover"],
)

fig_map.update_traces(
    hovertemplate="%{customdata[0]}<extra></extra>",
    marker_line_color="rgba(255,255,255,0.4)",
    marker_line_width=0.8,
)

fig_map.update_geos(
    visible=False,
    fitbounds="locations",
    showland=True,
    landcolor="#0a1520",
    showocean=True,
    oceancolor="#060e18",
    showlakes=True,
    lakecolor="#0a1520",
    showframe=False,
    showcoastlines=False,
)

fig_map.update_layout(
    paper_bgcolor="#0d1b2a",
    plot_bgcolor="#0d1b2a",
    geo_bgcolor="#0d1b2a",
    margin={"r": 10, "t": 10, "l": 10, "b": 10},
    height=540,
    coloraxis_colorbar=dict(
        title=dict(text=cfg["label"], font=dict(color="#7fa8c9", size=11)),
        tickfont=dict(color="#a8c0d6", size=10),
        bgcolor="#102035",
        bordercolor="#1e3a5f",
        borderwidth=1,
        len=0.7,
        thickness=14,
        x=1.01,
    ),
)

st.plotly_chart(fig_map, use_container_width=True)

# ── below-map detail ──────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#1e3a5f;margin:8px 0 20px'>", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown(
        f"<h3 style='font-size:1rem;color:#7fa8c9;letter-spacing:0.06em;"
        f"text-transform:uppercase;margin-bottom:12px'>Province Breakdown</h3>",
        unsafe_allow_html=True,
    )
    table_df = (
        stats[["province", "job_count", "remote_rate", "senior_rate", "avg_salary"]]
        .sort_values("job_count", ascending=False)
        .reset_index(drop=True)
    )
    table_df["avg_salary"] = table_df["avg_salary"].apply(
        lambda v: f"${v/1000:.0f}k" if pd.notna(v) else "—"
    )
    table_df["remote_rate"] = table_df["remote_rate"].apply(
        lambda v: f"{v:.0f}%" if pd.notna(v) else "—"
    )
    table_df["senior_rate"] = table_df["senior_rate"].apply(
        lambda v: f"{v:.0f}%" if pd.notna(v) else "—"
    )
    table_df["job_count"] = table_df["job_count"].astype(int)
    table_df.columns = ["Province", "Jobs", "Remote", "Senior+", "Avg Salary"]

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
    )

with col_right:
    st.markdown(
        f"<h3 style='font-size:1rem;color:#7fa8c9;letter-spacing:0.06em;"
        f"text-transform:uppercase;margin-bottom:12px'>Top Cities</h3>",
        unsafe_allow_html=True,
    )
    city_df = df[df["location_city"].notna()]
    if not city_df.empty:
        top_cities = (
            city_df["location_city"]
            .value_counts()
            .head(10)
            .reset_index()
        )
        top_cities.columns = ["city", "count"]

        fig_cities = px.bar(
            top_cities,
            x="count",
            y="city",
            orientation="h",
            color="count",
            color_continuous_scale=cfg["colorscale"],
        )
        fig_cities.update_traces(
            hovertemplate="<b>%{y}</b><br>%{x} jobs<extra></extra>",
        )
        fig_cities.update_layout(
            paper_bgcolor="#0d1b2a",
            plot_bgcolor="#102035",
            font=dict(color="#e2eaf4", size=12),
            margin={"r": 10, "t": 0, "l": 0, "b": 0},
            height=320,
            xaxis=dict(
                showgrid=True,
                gridcolor="#1e3a5f",
                title="",
                tickfont=dict(color="#7fa8c9"),
            ),
            yaxis=dict(
                title="",
                tickfont=dict(color="#e2eaf4"),
                categoryorder="total ascending",
            ),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_cities, use_container_width=True)
    else:
        st.info("No city data available.")
