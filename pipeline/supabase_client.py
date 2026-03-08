"""Supabase upsert/query helpers for the pipeline."""
from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

from pipeline.config import SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)


def get_service_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def upsert_jobs(jobs: list[dict[str, Any]], client: Client) -> None:
    if not jobs:
        return
    # JSearch can return the same job_id on multiple pages; deduplicate within
    # the batch before sending — Supabase raises code 21000 on intra-batch dupes.
    seen: set[str] = set()
    unique_jobs = []
    for job in jobs:
        if job["job_id"] not in seen:
            seen.add(job["job_id"])
            unique_jobs.append(job)
    client.table("job_postings").upsert(unique_jobs, on_conflict="job_id").execute()
    logger.info("Upserted %d job(s) into job_postings (%d dupes dropped).", len(unique_jobs), len(jobs) - len(unique_jobs))


def ensure_company_stubs(jobs: list[dict[str, Any]], client: Client) -> None:
    """Insert minimal company records (domain + name) for any new domains.

    Uses ignore_duplicates=True so existing records are never overwritten.
    Required to satisfy the job_postings.company_domain FK constraint.
    """
    records = {
        j["company_domain"]: j.get("company_name")
        for j in jobs
        if j.get("company_domain")
    }
    if not records:
        return
    stubs = [{"domain": domain, "name": name} for domain, name in records.items()]
    client.table("companies").upsert(stubs, on_conflict="domain", ignore_duplicates=True).execute()
    logger.info("Ensured %d company stub(s).", len(stubs))


def insert_pipeline_run(client: Client) -> str:
    """Insert a 'running' pipeline_run record and return its id."""
    resp = (
        client.table("pipeline_runs")
        .insert({"status": "running"})
        .execute()
    )
    run_id: str = resp.data[0]["id"]
    logger.info("Pipeline run started: %s", run_id)
    return run_id


def apply_manual_enrichment(job_ids: list[str], client: Client) -> int:
    """Call the merge_manual_enrichment Postgres function for the given job_ids.

    Fills NULL fields in job_postings with values from job_manual_enrichment.
    Returns the number of rows updated.
    """
    if not job_ids:
        return 0
    resp = client.rpc("merge_manual_enrichment", {"p_job_ids": job_ids}).execute()
    count: int = resp.data or 0
    logger.info("Manual enrichment applied to %d job(s).", count)
    return count


def update_pipeline_run(run_id: str, client: Client, **kwargs: Any) -> None:
    client.table("pipeline_runs").update(kwargs).eq("id", run_id).execute()
    logger.info("Pipeline run %s updated: %s", run_id, kwargs)
