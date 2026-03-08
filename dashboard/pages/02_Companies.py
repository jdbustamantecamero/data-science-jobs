"""Companies page: top hiring companies, seniority mix, employment type, searchable table."""
import plotly.express as px
import pandas as pd
import streamlit as st

from utils import load_jobs

st.set_page_config(page_title="Companies", page_icon="🏢", layout="wide")
st.title("🏢 Companies")

df = load_jobs()

if df.empty:
    st.info("No job data available yet.")
    st.stop()

# --- Top 20 hiring companies ---
st.subheader("Top 20 Hiring Companies")
top20 = (
    df.groupby("company_name")
    .agg(
        job_count=("job_id", "count"),
        remote_count=("is_remote", "sum"),
        avg_salary_min=("salary_min", "mean"),
    )
    .reset_index()
    .sort_values("job_count", ascending=False)
    .head(20)
)
top20["remote_pct"] = (top20["remote_count"] / top20["job_count"] * 100).round(1)

fig = px.bar(
    top20,
    x="job_count",
    y="company_name",
    orientation="h",
    color="remote_pct",
    color_continuous_scale="teal",
    labels={"job_count": "Job Postings", "company_name": "Company", "remote_pct": "Remote %"},
)
fig.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
col1, col2 = st.columns(2)

# --- Seniority mix ---
with col1:
    st.subheader("Seniority Level Distribution")
    if "seniority" in df.columns and df["seniority"].notna().any():
        order = ["Intern", "Junior", "Mid", "Senior", "Lead", "Director+"]
        seniority_counts = (
            df["seniority"]
            .value_counts()
            .reindex(order)
            .dropna()
            .reset_index()
        )
        seniority_counts.columns = ["seniority", "count"]
        fig2 = px.bar(
            seniority_counts,
            x="seniority",
            y="count",
            color="seniority",
            labels={"count": "Job Postings", "seniority": "Level"},
            color_discrete_sequence=px.colors.sequential.Blues_r,
        )
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No seniority data yet.")

# --- Employment type breakdown ---
with col2:
    st.subheader("Employment Type Breakdown")
    if "employment_type" in df.columns and df["employment_type"].notna().any():
        emp_counts = df["employment_type"].value_counts().reset_index()
        emp_counts.columns = ["employment_type", "count"]
        fig3 = px.pie(
            emp_counts,
            names="employment_type",
            values="count",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No employment type data yet.")

st.markdown("---")

# --- Searchable job table by company ---
st.subheader("Browse by Company")
search = st.text_input("Search company name", "")

company_summary = (
    df.groupby("company_name")
    .agg(
        domain=("company_domain", "first"),
        jobs=("job_id", "count"),
        remote_pct=("is_remote", lambda x: f"{x.mean()*100:.0f}%"),
        avg_salary_min=("salary_min", lambda x: f"${x.mean():,.0f}" if x.notna().any() else "—"),
        top_seniority=("seniority", lambda x: x.value_counts().index[0] if x.notna().any() else "—"),
    )
    .reset_index()
    .sort_values("jobs", ascending=False)
)

if search:
    company_summary = company_summary[
        company_summary["company_name"].str.contains(search, case=False, na=False)
    ]

st.dataframe(
    company_summary.rename(columns={
        "company_name": "Company",
        "domain": "Domain",
        "jobs": "Postings",
        "remote_pct": "Remote %",
        "avg_salary_min": "Avg Min Salary",
        "top_seniority": "Most Common Level",
    }),
    use_container_width=True,
    hide_index=True,
)
