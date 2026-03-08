"""Overview page: KPIs, seniority distribution, weekly trend, pipeline runs."""
import plotly.express as px
import streamlit as st

from utils import load_jobs, load_pipeline_runs, load_weekly_trends

st.set_page_config(page_title="Overview", page_icon="🏠", layout="wide")
st.title("🏠 Overview")

jobs_df = load_jobs()
runs_df = load_pipeline_runs()
trends_df = load_weekly_trends()

# --- KPI metrics ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Jobs", f"{len(jobs_df):,}")
with col2:
    remote_pct = int(jobs_df["is_remote"].mean() * 100) if not jobs_df.empty else 0
    st.metric("Remote %", f"{remote_pct}%")
with col3:
    companies = jobs_df["company_name"].nunique() if not jobs_df.empty else 0
    st.metric("Unique Companies", f"{companies:,}")
with col4:
    salary_jobs = jobs_df["salary_min"].notna().sum() if not jobs_df.empty else 0
    st.metric("Jobs w/ Salary", f"{salary_jobs:,}")

st.markdown("---")

col_left, col_right = st.columns(2)

# --- Weekly trend ---
with col_left:
    st.subheader("Weekly Job Postings Trend")
    if not trends_df.empty:
        fig = px.line(
            trends_df,
            x="week_start",
            y=["job_count", "remote_count"],
            labels={"value": "Jobs", "week_start": "Week", "variable": ""},
            color_discrete_map={"job_count": "#636EFA", "remote_count": "#00CC96"},
        )
        fig.update_layout(legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trend data yet.")

# --- Seniority distribution ---
with col_right:
    st.subheader("Jobs by Seniority Level")
    if not jobs_df.empty and "seniority" in jobs_df.columns and jobs_df["seniority"].notna().any():
        order = ["Intern", "Junior", "Mid", "Senior", "Lead", "Director+"]
        seniority_counts = (
            jobs_df["seniority"]
            .value_counts()
            .reindex(order)
            .dropna()
            .reset_index()
        )
        seniority_counts.columns = ["seniority", "count"]
        fig_s = px.pie(
            seniority_counts,
            names="seniority",
            values="count",
            hole=0.4,
            category_orders={"seniority": order},
            color_discrete_sequence=px.colors.sequential.Blues_r,
        )
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("No seniority data yet.")

st.markdown("---")

# --- Recent pipeline runs ---
st.subheader("Recent Pipeline Runs")
if not runs_df.empty:
    display_cols = ["run_at", "status", "jobs_fetched", "jobs_new", "jobs_skipped", "duration_seconds"]
    display_cols = [c for c in display_cols if c in runs_df.columns]
    st.dataframe(runs_df[display_cols].head(5), use_container_width=True)
else:
    st.info("No pipeline runs recorded yet.")
