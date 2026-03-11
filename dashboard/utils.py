"""Shared Supabase client + cached data loaders for the dashboard."""
from __future__ import annotations

import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()
import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or (st.secrets.get("SUPABASE_URL") if hasattr(st, "secrets") else None) or ""
    key = os.environ.get("SUPABASE_ANON_KEY") or (st.secrets.get("SUPABASE_ANON_KEY") if hasattr(st, "secrets") else None) or ""
    if not url or not key:
        st.error("SUPABASE_URL and SUPABASE_ANON_KEY must be set.")
        st.stop()
    return create_client(url, key)


@st.cache_data(ttl=3600)
def load_jobs() -> pd.DataFrame:
    client = get_client()
    resp = client.table("v_jobs_enriched").select("*").execute()
    df = pd.DataFrame(resp.data)
    if not df.empty and "posted_at" in df.columns:
        df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, errors="coerce")
    return df



@st.cache_data(ttl=3600)
def load_pipeline_runs() -> pd.DataFrame:
    client = get_client()
    resp = (
        client.table("pipeline_runs")
        .select("*")
        .order("run_at", desc=True)
        .limit(20)
        .execute()
    )
    df = pd.DataFrame(resp.data)
    if not df.empty and "run_at" in df.columns:
        df["run_at"] = pd.to_datetime(df["run_at"], utc=True, errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_province_stats() -> pd.DataFrame:
    """Gold layer: pre-aggregated province metrics from v_province_stats."""
    client = get_client()
    resp = client.table("v_province_stats").select("*").execute()
    df = pd.DataFrame(resp.data)
    for col in ("job_count", "remote_rate", "senior_rate", "avg_salary"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_skill_frequency() -> pd.DataFrame:
    client = get_client()
    resp = client.table("v_skill_frequency").select("*").execute()
    return pd.DataFrame(resp.data)


@st.cache_data(ttl=3600)
def load_weekly_trends() -> pd.DataFrame:
    client = get_client()
    resp = client.table("v_weekly_trends").select("*").execute()
    df = pd.DataFrame(resp.data)
    if not df.empty and "week_start" in df.columns:
        df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    return df
