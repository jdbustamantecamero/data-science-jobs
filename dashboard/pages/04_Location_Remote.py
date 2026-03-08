"""Location & Remote page: remote vs on-site, provinces, choropleth, cities."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import load_jobs

st.set_page_config(page_title="Location & Remote", page_icon="📍", layout="wide")
st.title("📍 Location & Remote")

df = load_jobs()

if df.empty:
    st.info("No job data available yet.")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Remote vs On-Site")
    remote_counts = df["is_remote"].map({True: "Remote", False: "On-Site"}).value_counts().reset_index()
    remote_counts.columns = ["type", "count"]
    fig = px.pie(remote_counts, names="type", values="count", hole=0.4,
                 color_discrete_map={"Remote": "#00CC96", "On-Site": "#636EFA"})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Top 10 Provinces")
    province_df = df[df["location_state"].notna()]
    if not province_df.empty:
        top_provinces = province_df["location_state"].value_counts().head(10).reset_index()
        top_provinces.columns = ["province", "count"]
        fig2 = px.bar(top_provinces, x="count", y="province", orientation="h",
                      labels={"count": "Job Postings", "province": "Province"},
                      color_discrete_sequence=["#AB63FA"])
        fig2.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No province data available.")

st.markdown("---")

# Canada choropleth by province
# Plotly uses ISO 3166-2:CA codes (e.g. "CA-ON", "CA-BC")
_PROVINCE_CODES = {
    "Alberta": "CA-AB", "AB": "CA-AB",
    "British Columbia": "CA-BC", "BC": "CA-BC",
    "Manitoba": "CA-MB", "MB": "CA-MB",
    "New Brunswick": "CA-NB", "NB": "CA-NB",
    "Newfoundland and Labrador": "CA-NL", "NL": "CA-NL",
    "Northwest Territories": "CA-NT", "NT": "CA-NT",
    "Nova Scotia": "CA-NS", "NS": "CA-NS",
    "Nunavut": "CA-NU", "NU": "CA-NU",
    "Ontario": "CA-ON", "ON": "CA-ON",
    "Prince Edward Island": "CA-PE", "PE": "CA-PE",
    "Quebec": "CA-QC", "QC": "CA-QC",
    "Saskatchewan": "CA-SK", "SK": "CA-SK",
    "Yukon": "CA-YT", "YT": "CA-YT",
}

st.subheader("Canada Job Density by Province")
ca_df = df[df["location_state"].notna()].copy()
if not ca_df.empty:
    ca_df["province_code"] = ca_df["location_state"].map(_PROVINCE_CODES)
    ca_df = ca_df[ca_df["province_code"].notna()]

if not ca_df.empty:
    province_counts = ca_df["province_code"].value_counts().reset_index()
    province_counts.columns = ["province_code", "count"]
    fig3 = go.Figure(go.Choropleth(
        locations=province_counts["province_code"],
        z=province_counts["count"],
        locationmode="geojson-id",
        colorscale="Blues",
        colorbar_title="Job Postings",
        geojson="https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/canada.geojson",
    ))
    # Fallback: use a simple bar chart since geojson URL may not load in all envs
    fig3b = px.bar(
        province_counts.sort_values("count", ascending=False),
        x="province_code",
        y="count",
        labels={"province_code": "Province", "count": "Job Postings"},
        color="count",
        color_continuous_scale="Blues",
    )
    fig3b.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig3b, use_container_width=True)
else:
    st.info("No Canadian province data available yet.")

st.markdown("---")
st.subheader("Top 10 Cities")
city_df = df[df["location_city"].notna()]
if not city_df.empty:
    top_cities = city_df["location_city"].value_counts().head(10).reset_index()
    top_cities.columns = ["city", "count"]
    fig4 = px.bar(top_cities, x="city", y="count",
                  labels={"count": "Job Postings", "city": "City"},
                  color_discrete_sequence=["#FFA15A"])
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("No city data available.")
