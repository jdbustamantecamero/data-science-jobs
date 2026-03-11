"""
Supabase database interface for the job pipeline.

This module provides high-level helpers for interacting with Supabase (PostgreSQL),
including bulk job upserts, company record management, and pipeline run tracking.
"""
from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

from pipeline.config import SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)


def get_service_client() -> Client:
    """
    Initialize and return a Supabase client using the service role key.
    The service key is required to bypass Row Level Security (RLS) during writes.
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def upsert_jobs(jobs: list[dict[str, Any]], client: Client) -> None:
    """
    Perform a bulk upsert of job postings into the 'job_postings' table.

    Deduplicates within the provided batch by 'job_id' to prevent PostgreSQL
    errors (code 21000) that occur when a single batch contains duplicate keys.
    """
    if not jobs:
        return
        
    seen: set[str] = set()
    unique_jobs = []
    for job in jobs:
        if job["job_id"] not in seen:
            seen.add(job["job_id"])
            unique_jobs.append(job)
            
    # Perform the bulk upsert using the 'job_id' column for conflict resolution.
    client.table("job_postings").upsert(unique_jobs, on_conflict="job_id").execute()
    
    logger.info(
        "Upserted %d job(s) into job_postings (%d intra-batch dupes dropped).", 
        len(unique_jobs), len(jobs) - len(unique_jobs)
    )


def ensure_company_stubs(jobs: list[dict[str, Any]], client: Client) -> None:
    """
    Insert minimal 'stub' records into the 'companies' table for any new domains.
    
    This is required to satisfy the foreign key constraint (job_postings.company_domain).
    Uses 'ignore_duplicates=True' to ensure existing company records are not modified.
    """
    records = {
        j["company_domain"]: j.get("company_name")
        for j in jobs
        if j.get("company_domain")
    }
    if not records:
        return
        
    stubs = [{"domain": domain, "name": name} for domain, name in records.items()]
    
    # Bulk upsert company stubs. ignore_duplicates ensures we don't overwrite
    # existing company metadata (e.g. employee count) with generic stubs.
    client.table("companies").upsert(stubs, on_conflict="domain", ignore_duplicates=True).execute()
    
    logger.info("Ensured %d company stub(s).", len(stubs))


def insert_pipeline_run(client: Client) -> str:
    """
    Create a new record in 'pipeline_runs' with 'running' status.
    Returns the UUID of the newly created run.
    """
    resp = (
        client.table("pipeline_runs")
        .insert({"status": "running"})
        .execute()
    )
    run_id: str = resp.data[0]["id"]
    logger.info("Pipeline run started: %s", run_id)
    return run_id


def apply_manual_enrichment(job_ids: list[str], client: Client) -> int:
    """
    Invoke the 'merge_manual_enrichment' Postgres function (RPC) for specific jobs.
    
    This function fills NULL fields in 'job_postings' with values curated in 
    the 'job_manual_enrichment' table.
    """
    if not job_ids:
        return 0
    resp = client.rpc("merge_manual_enrichment", {"p_job_ids": job_ids}).execute()
    count: int = resp.data or 0
    logger.info("Manual enrichment applied to %d job(s).", count)
    return count


def update_pipeline_run(run_id: str, client: Client, **kwargs: Any) -> None:
    """
    Update a pipeline run record with final statistics and status.
    """
    client.table("pipeline_runs").update(kwargs).eq("id", run_id).execute()
    logger.info("Pipeline run %s updated: %s", run_id, kwargs)
