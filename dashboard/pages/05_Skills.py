"""Skills page: top skills bar, co-occurrence heatmap, trend over time."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from utils import load_jobs, load_skill_frequency

st.set_page_config(page_title="Skills", page_icon="🛠️", layout="wide")
st.title("🛠️ Skills")

jobs_df = load_jobs()
freq_df = load_skill_frequency()

if jobs_df.empty:
    st.info("No job data available yet.")
    st.stop()

# --- Top 30 skills bar ---
st.subheader("Top 30 In-Demand Skills")
if not freq_df.empty:
    top30 = freq_df.head(30)
    fig = px.bar(
        top30,
        x="occurrences",
        y="skill",
        orientation="h",
        labels={"occurrences": "Job Postings Mentioning Skill", "skill": "Skill"},
        color="occurrences",
        color_continuous_scale="Blues",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No skill data yet.")

st.markdown("---")

# --- Co-occurrence heatmap (top 15 skills) ---
st.subheader("Skill Co-occurrence Heatmap (Top 15)")

if not jobs_df.empty and "skills_tags" in jobs_df.columns:
    top15_skills = freq_df["skill"].head(15).tolist() if not freq_df.empty else []

    if top15_skills:
        # Build co-occurrence matrix
        matrix = pd.DataFrame(0, index=top15_skills, columns=top15_skills)
        for tags in jobs_df["skills_tags"].dropna():
            tags_list = [t for t in tags if t in top15_skills]
            for i, s1 in enumerate(tags_list):
                for s2 in tags_list[i:]:
                    matrix.loc[s1, s2] += 1
                    if s1 != s2:
                        matrix.loc[s2, s1] += 1

        fig2 = go.Figure(
            data=go.Heatmap(
                z=matrix.values,
                x=top15_skills,
                y=top15_skills,
                colorscale="Blues",
                text=matrix.values,
                texttemplate="%{text}",
            )
        )
        fig2.update_layout(
            xaxis_tickangle=-45,
            height=550,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough skill data for heatmap.")
else:
    st.info("No skills_tags data available.")

st.markdown("---")

# --- Skill trend over time ---
st.subheader("Skill Trend Over Time")
if not jobs_df.empty and "skills_tags" in jobs_df.columns and "posted_at" in jobs_df.columns:
    top_skill_options = freq_df["skill"].head(20).tolist() if not freq_df.empty else []
    selected_skill = st.selectbox("Select a skill", top_skill_options or ["python"])

    if selected_skill:
        trend_df = jobs_df[["posted_at", "skills_tags"]].copy()
        trend_df = trend_df[trend_df["posted_at"].notna()]
        trend_df["has_skill"] = trend_df["skills_tags"].apply(
            lambda tags: selected_skill in (tags or [])
        )
        trend_df["week"] = trend_df["posted_at"].dt.to_period("W").dt.start_time
        weekly = (
            trend_df.groupby("week")["has_skill"]
            .agg(count="sum", total="count")
            .reset_index()
        )
        weekly["pct"] = (weekly["count"] / weekly["total"] * 100).round(1)
        fig3 = px.line(
            weekly,
            x="week",
            y="pct",
            labels={"week": "Week", "pct": f"% Jobs Mentioning '{selected_skill}'"},
        )
        st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No temporal skill data available yet.")
