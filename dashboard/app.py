"""Streamlit dashboard entry point."""
import streamlit as st

st.set_page_config(
    page_title="Data Science Jobs",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Data Science Jobs Dashboard")
st.markdown(
    "Weekly-refreshed insights from Canadian job postings."
)
st.markdown("---")
st.info("Select a page from the sidebar to explore the data.")
