"""Salaries page: box plot, histogram, top paying roles."""
import plotly.express as px
import streamlit as st

from utils import load_jobs

st.set_page_config(page_title="Salaries", page_icon="💰", layout="wide")
st.title("💰 Salaries")

df = load_jobs()

if df.empty:
    st.info("No job data available yet.")
    st.stop()

salary_df = df[df["salary_min"].notna() & (df["salary_period"] == "YEAR")].copy()
salary_pct = round(len(salary_df) / len(df) * 100, 1) if len(df) else 0

st.metric("Jobs with Annual Salary Data", f"{len(salary_df):,} ({salary_pct}%)")
st.markdown("---")

if salary_df.empty:
    st.info("No salary data with annual period yet.")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Salary Range by Employment Type")
    fig = px.box(
        salary_df,
        x="employment_type",
        y="salary_min",
        color="employment_type",
        labels={"salary_min": "Min Annual Salary (CAD)", "employment_type": "Type"},
        points="outliers",
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Distribution of Minimum Annual Salary")
    fig2 = px.histogram(
        salary_df,
        x="salary_min",
        nbins=40,
        labels={"salary_min": "Min Annual Salary (CAD)"},
        color_discrete_sequence=["#636EFA"],
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
st.subheader("Top 10 Highest-Paying Roles")
top_paying = (
    salary_df.groupby("title")["salary_min"]
    .median()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)
top_paying.columns = ["Role", "Median Min Salary (USD)"]
fig3 = px.bar(
    top_paying,
    x="Median Min Salary (USD)",
    y="Role",
    orientation="h",
    color_discrete_sequence=["#EF553B"],
)
fig3.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig3, use_container_width=True)
