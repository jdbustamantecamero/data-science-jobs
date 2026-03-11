"""Canada map — province choropleth + city dot density (Folium / Leaflet)."""
from __future__ import annotations

import copy
import json
import math
import unicodedata

import branca.colormap as cm
import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from ui_components import apply_theme, center_layout, page_header, section_divider
from utils import load_jobs, load_province_stats

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Location", page_icon="🗺️", layout="wide")
apply_theme()
center_layout(960)

# Center the metric radio + style the province table
st.markdown("""
<style>
/* Metric radio — centred */
[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] {
    display: flex;
    justify-content: center;
    margin-bottom: 12px;
}
/* Province table — centred cells */
.stTable table { width: 100%; border-collapse: collapse; }
.stTable td, .stTable th {
    text-align: center !important;
    padding: 8px 14px !important;
    font-size: 0.875rem;
}
</style>
""", unsafe_allow_html=True)

# ── constants ─────────────────────────────────────────────────────────────────
ALL_PROVINCES = [
    "Alberta", "British Columbia", "Manitoba", "New Brunswick",
    "Newfoundland and Labrador", "Northwest Territories", "Nova Scotia",
    "Nunavut", "Ontario", "Prince Edward Island", "Quebec",
    "Saskatchewan", "Yukon",
]

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
        "note": None,
        "accent": "#3b82f6",
    },
    "Remote Rate": {
        "col": "remote_rate",
        "label": "Remote Rate",
        "colorscale": [[0, "#0d2137"], [0.3, "#7c3d0c"], [1, "#f59e0b"]],
        "fmt": lambda v: f"{v:.0f}%" if pd.notna(v) else "—",
        "note": None,
        "accent": "#f59e0b",
    },
    "Senior+ Rate": {
        "col": "senior_rate",
        "label": "Senior / Lead / Director+",
        "colorscale": [[0, "#0d2137"], [0.3, "#6b1a6b"], [1, "#f472b6"]],
        "fmt": lambda v: f"{v:.0f}%" if pd.notna(v) else "—",
        "note": "Senior+ includes Senior, Lead, and Director+ seniority levels.",
        "accent": "#f472b6",
    },
    "Avg Salary": {
        "col": "avg_salary",
        "label": "Avg Salary (CAD)",
        "colorscale": [[0, "#0d2137"], [0.3, "#064e3b"], [1, "#10b981"]],
        "fmt": lambda v: f"${v/1000:.0f}k" if pd.notna(v) else "—",
        "note": "Only ~15% of postings include salary data. Unshaded provinces have no salary records.",
        "accent": "#10b981",
    },
}

# ── Seniority order + colours (shared by Top Cities chart) ────────────────────
_SEN_ORDER = ["Intern", "Junior", "Mid", "Senior", "Lead", "Director+"]
_SEN_COLORS = {
    "Intern":    "#94a3b8",
    "Junior":    "#60a5fa",
    "Mid":       "#3b82f6",
    "Senior":    "#f472b6",
    "Lead":      "#f59e0b",
    "Director+": "#10b981",
}

# ── City coordinates — covers the Canadian cities most likely in the dataset ──
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Toronto":        (43.6532, -79.3832),
    "Vancouver":      (49.2827, -123.1207),
    "Montreal":       (45.5017, -73.5673),
    "Calgary":        (51.0447, -114.0719),
    "Edmonton":       (53.5461, -113.4938),
    "Ottawa":         (45.4215, -75.6972),
    "Winnipeg":       (49.8951,  -97.1384),
    "Quebec City":    (46.8139,  -71.2080),
    "Hamilton":       (43.2557,  -79.8711),
    "Kitchener":      (43.4516,  -80.4925),
    "Waterloo":       (43.4668,  -80.5164),
    "London":         (43.0096,  -81.2737),
    "Halifax":        (44.6488,  -63.5752),
    "Victoria":       (48.4284, -123.3656),
    "Saskatoon":      (52.1332, -106.6700),
    "Regina":         (50.4452, -104.6189),
    "St. John's":     (47.5615,  -52.7126),
    "Moncton":        (46.0878,  -64.7782),
    "Fredericton":    (45.9636,  -66.6431),
    "Windsor":        (42.3149,  -83.0364),
    "Mississauga":    (43.5890,  -79.6441),
    "Brampton":       (43.7315,  -79.7624),
    "Markham":        (43.8561,  -79.3370),
    "Richmond Hill":  (43.8828,  -79.4403),
    "Guelph":         (43.5448,  -80.2482),
    "Barrie":         (44.3894,  -79.6903),
    "Kelowna":        (49.8880, -119.4960),
    "Abbotsford":     (49.0504, -122.3045),
    "Surrey":         (49.1913, -122.8490),
    "Burnaby":        (49.2488, -122.9805),
    "Oakville":       (43.4675,  -79.6877),
    "Burlington":     (43.3255,  -79.7990),
    "Oshawa":         (43.8971,  -78.8658),
    "Sherbrooke":     (45.4042,  -71.8929),
    "Laval":          (45.6066,  -73.7124),
    "Longueuil":      (45.5315,  -73.5180),
    "Gatineau":       (45.4765,  -75.7013),
    "Sudbury":        (46.4917,  -80.9930),
    "Thunder Bay":    (48.3809,  -89.2477),
    "Lethbridge":     (49.6956, -112.8451),
    "Red Deer":       (52.2690, -113.8116),
    "Kamloops":       (50.6745, -120.3273),
    "Nanaimo":        (49.1659, -123.9401),
}

# ── GeoJSON (cached 24h) ──────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_geojson() -> dict:
    import urllib.request
    with urllib.request.urlopen(GEOJSON_URL) as r:
        geojson = json.loads(r.read())
    for feature in geojson.get("features", []):
        raw = feature.get("properties", {}).get("name", "")
        feature["properties"]["name"] = "".join(
            c for c in unicodedata.normalize("NFD", raw)
            if unicodedata.category(c) != "Mn"
        )
    return geojson


# ── Map builder ───────────────────────────────────────────────────────────────
def _inject_stats(geojson: dict, stats_df: pd.DataFrame) -> dict:
    """Return a deep copy of geojson with formatted stats injected per feature."""
    geo = copy.deepcopy(geojson)
    idx = stats_df.set_index("province")
    for feat in geo["features"]:
        name = feat["properties"]["name"]
        feat["properties"].update({"_jobs": "—", "_remote": "—", "_senior": "—", "_salary": "—"})
        if name not in idx.index:
            continue
        r = idx.loc[name]
        if pd.notna(r.get("job_count")):
            feat["properties"]["_jobs"] = f"{int(r['job_count']):,}"
        if pd.notna(r.get("remote_rate")):
            feat["properties"]["_remote"] = f"{r['remote_rate']:.0f}%"
        if pd.notna(r.get("senior_rate")):
            feat["properties"]["_senior"] = f"{r['senior_rate']:.0f}%"
        if pd.notna(r.get("avg_salary")):
            feat["properties"]["_salary"] = f"${r['avg_salary'] / 1000:.0f}k"
    return geo


def _build_map(
    geojson: dict,
    stats_df: pd.DataFrame,
    jobs_df: pd.DataFrame,
    cfg: dict,
    show_cities: bool,
) -> folium.Map:
    """Build and return the Folium map for the current metric + city toggle."""
    m = folium.Map(location=[56.1, -96.0], zoom_start=3, tiles=None, zoom_control=True)

    folium.TileLayer(
        tiles="CartoDB dark_matter", name="Basemap", overlay=False, control=False,
    ).add_to(m)

    # Colormap matching METRIC_CONFIG colorscale
    col_series = stats_df[cfg["col"]].dropna()
    z_min = float(col_series.min()) if not col_series.empty else 0.0
    z_max = float(col_series.max()) if not col_series.empty else 1.0
    if z_min == z_max:
        z_max = z_min + 1.0

    colormap = cm.LinearColormap(
        colors=[c for _, c in cfg["colorscale"]],
        index=[z_min + p * (z_max - z_min) for p, _ in cfg["colorscale"]],
        vmin=z_min, vmax=z_max, caption=cfg["label"],
    )
    colormap.add_to(m)

    # Province choropleth
    geo_with_stats = _inject_stats(geojson, stats_df)
    province_vals  = stats_df.set_index("province")[cfg["col"]].to_dict()

    province_fg = folium.FeatureGroup(name="Provinces", show=True)
    folium.GeoJson(
        geo_with_stats,
        style_function=lambda f, pv=province_vals, cmap=colormap: {
            "fillColor": cmap(pv[f["properties"]["name"]])
                if f["properties"]["name"] in pv
                and pd.notna(pv.get(f["properties"]["name"]))
                else "#0d2137",
            "color": "rgba(255,255,255,0.3)",
            "weight": 0.8,
            "fillOpacity": 0.65,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["name", "_jobs", "_remote", "_senior", "_salary"],
            aliases=["Province", "Jobs", "Remote", "Senior+", "Avg Salary"],
            style=(
                "background-color:#102035;color:#e2eaf4;"
                "border:1px solid #1e3a5f;border-radius:6px;"
                "padding:6px 12px;font-family:system-ui,sans-serif;font-size:12px;"
            ),
            sticky=True,
        ),
    ).add_to(province_fg)
    province_fg.add_to(m)

    # City dot density
    if show_cities and "location_city" in jobs_df.columns:
        city_counts = jobs_df["location_city"].dropna().value_counts()
        city_fg = folium.FeatureGroup(name="City density", show=True)
        for city, count in city_counts.items():
            coords = CITY_COORDS.get(city)
            if coords is None:
                continue
            radius = max(4, min(24, 4 + math.log1p(count) * 3.5))
            folium.CircleMarker(
                location=coords, radius=radius,
                color="white", weight=0.5,
                fill=True, fill_color=cfg["accent"], fill_opacity=0.75,
                tooltip=(
                    f"<b style='font-family:system-ui'>{city}</b>"
                    f"<br><span style='color:#a8c0d6'>{count:,} jobs</span>"
                ),
            ).add_to(city_fg)
        city_fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


# ── Data ──────────────────────────────────────────────────────────────────────
stats  = load_province_stats()
df_all = load_jobs()

if df_all.empty:
    st.info("No job data available yet.")
    st.stop()
if "posted_at" in df_all.columns:
    df_all["posted_at"] = pd.to_datetime(df_all["posted_at"], utc=True, errors="coerce")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗺️ Location Explorer")
    section_divider()
    timeframe = st.selectbox(
        "Timeframe (KPIs & Cities)",
        ["All Time", "Last 30 Days", "Last 90 Days", "YTD 2026"],
    )
    section_divider()
    show_cities = st.checkbox("Show city dots", value=True)

# ── Timeframe filter ───────────────────────────────────────────────────────────
now_utc = pd.Timestamp.now(tz="UTC")
df = df_all.copy()
if timeframe == "Last 30 Days":
    df = df[df["posted_at"] >= now_utc - pd.Timedelta(days=30)]
elif timeframe == "Last 90 Days":
    df = df[df["posted_at"] >= now_utc - pd.Timedelta(days=90)]
elif timeframe == "YTD 2026":
    df = df[df["posted_at"] >= pd.Timestamp("2026-01-01", tz="UTC")]

# ── National KPIs ─────────────────────────────────────────────────────────────
total_with_province = int(stats["job_count"].sum()) if not stats.empty else 0
provinces_active    = int((stats["job_count"] > 0).sum()) if not stats.empty else 0

remote_known    = df[df["is_remote"].notna()]
national_remote = (
    round(100 * remote_known["is_remote"].astype(bool).sum() / len(remote_known), 1)
    if not remote_known.empty else 0.0
)
senior_known    = df[df["seniority"].notna()] if "seniority" in df.columns else pd.DataFrame()
national_senior = (
    round(100 * senior_known["seniority"].isin(SENIOR_LABELS).sum() / len(senior_known), 1)
    if not senior_known.empty else 0.0
)

# ── Header + KPIs ─────────────────────────────────────────────────────────────
page_header(
    "🗺️ Regional Job Market",
    f"Data Science roles across Canada · Map: All Time · KPIs & Cities: {timeframe}",
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Jobs with Location",    f"{total_with_province:,}")
k2.metric("Provinces Active",      str(provinces_active))
k3.metric("National Remote Rate",  f"{national_remote:.0f}%")
k4.metric("National Senior+ Rate", f"{national_senior:.0f}%")

st.write("")

# ── Metric selector ───────────────────────────────────────────────────────────
metric_choice = st.radio(
    "Map metric", list(METRIC_CONFIG.keys()),
    horizontal=True, label_visibility="collapsed",
)
cfg = METRIC_CONFIG[metric_choice]
if cfg["note"]:
    st.info(cfg["note"])

# ── Folium map ────────────────────────────────────────────────────────────────
geojson = load_geojson()
complete_stats = pd.DataFrame({"province": ALL_PROVINCES}).merge(
    stats, on="province", how="left"
)

st_folium(
    _build_map(geojson, complete_stats, df, cfg, show_cities),
    use_container_width=True,
    height=540,
    returned_objects=[],
    key=f"canada_map_{metric_choice}_{show_cities}",
)

# ── Below-map detail ──────────────────────────────────────────────────────────
section_divider()

# ── Province Breakdown ────────────────────────────────────────────────────────
with st.container():
    st.markdown(
        "<h3 style='text-align:center;margin-bottom:8px'>Province Breakdown</h3>",
        unsafe_allow_html=True,
    )
    # Median salary computed locally from the timeframe-filtered jobs
    median_sal = (
        df_all[df_all["salary_min"].notna() & df_all["location_state"].notna()]
        .groupby("location_state")["salary_min"]
        .median()
        .reset_index()
        .rename(columns={"location_state": "province", "salary_min": "median_salary"})
    )
    table_df = (
        stats[["province", "job_count", "remote_rate", "senior_rate"]]
        .merge(median_sal, on="province", how="left")
        .copy()
    )
    table_df["remote_rate"]    = table_df["remote_rate"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "—")
    table_df["senior_rate"]    = table_df["senior_rate"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "—")
    table_df["median_salary"]  = table_df["median_salary"].apply(lambda v: f"${v/1000:.0f}k" if pd.notna(v) else "—")
    table_df["job_count"]      = table_df["job_count"].astype(int)
    table_df.columns = ["Province", "Jobs", "Remote", "Senior+", "Median Salary"]
    st.table(table_df.set_index("Province"))

section_divider()

# ── Top Cities — stacked by seniority ────────────────────────────────────────
with st.container():
    st.markdown(
        "<h3 style='text-align:center;margin-bottom:8px'>Top Cities</h3>",
        unsafe_allow_html=True,
    )
    city_df = df[df["location_city"].notna()]
    if not city_df.empty:
        top_10 = city_df["location_city"].value_counts().head(10).index.tolist()

        if "seniority" in city_df.columns and city_df["seniority"].notna().any():
            cs = (
                city_df[city_df["location_city"].isin(top_10)]
                .groupby(["location_city", "seniority"])
                .size()
                .reset_index(name="count")
            )
            fig_cities = px.bar(
                cs,
                x="count", y="location_city",
                color="seniority",
                orientation="h",
                barmode="stack",
                category_orders={
                    "location_city": top_10[::-1],
                    "seniority": _SEN_ORDER,
                },
                color_discrete_map=_SEN_COLORS,
                labels={"count": "Jobs", "location_city": "", "seniority": ""},
            )
            fig_cities.update_layout(
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="center", x=0.5,
                    font=dict(color="#a8c0d6", size=10),
                    title_text="",
                ),
            )
        else:
            # Fallback: single-series bar if seniority not available
            top_cities = city_df["location_city"].value_counts().head(10).reset_index()
            top_cities.columns = ["city", "count"]
            fig_cities = px.bar(
                top_cities, x="count", y="city", orientation="h",
                color="count", color_continuous_scale=cfg["colorscale"],
                labels={"count": "Jobs", "city": ""},
            )
            fig_cities.update_layout(coloraxis_showscale=False)

        fig_cities.update_traces(hovertemplate="<b>%{y}</b><br>%{x} jobs<extra></extra>")
        fig_cities.update_layout(
            paper_bgcolor="#0d1b2a", plot_bgcolor="#102035",
            font=dict(color="#e2eaf4", size=12),
            margin={"r": 10, "t": 40, "l": 0, "b": 0}, height=420,
            xaxis=dict(showgrid=True, gridcolor="#1e3a5f", title="", tickfont=dict(color="#7fa8c9")),
            yaxis=dict(title="", tickfont=dict(color="#e2eaf4")),
        )
        st.plotly_chart(fig_cities, use_container_width=True)
    else:
        st.info("No city data available.")
