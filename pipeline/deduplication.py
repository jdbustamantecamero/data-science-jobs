"""
Bulk deduplication logic for filtering out existing job postings.

This module ensures that only new, unseen job postings are processed by the 
transformation and loading stages of the pipeline. It compares the IDs 
of incoming jobs against the 'job_id' column in the database.
"""
from __future__ import annotations

import logging
from typing import Any

from supabase import Client

logger = logging.getLogger(__name__)


def filter_new_jobs(
    jobs: list[dict[str, Any]],
    client: Client,
) -> tuple[list[dict[str, Any]], int]:
    """
    Given a list of job postings, returns a filtered list containing only 
    those that do not already exist in the database.

    Args:
        jobs: A list of raw job dictionaries fetched from the providers.
        client: A Supabase Client with service-role permissions.

    Returns:
        A tuple of (new_jobs, skipped_count).
    """
    if not jobs:
        return [], 0

    # Extract all unique incoming job IDs for a single bulk query.
    # This is much more efficient than checking IDs one-by-one.
    incoming_ids = [j["job_id"] for j in jobs]

    # SELECT only the job_ids that already exist in our database.
    response = (
        client.table("job_postings")
        .select("job_id")
        .in_("job_id", incoming_ids)
        .execute()
    )
    existing_ids: set[str] = {row["job_id"] for row in response.data}

    # Filter out any incoming jobs whose IDs are already in the existing_ids set.
    new_jobs = [j for j in jobs if j["job_id"] not in existing_ids]
    skipped = len(jobs) - len(new_jobs)
    
    logger.info(
        "Dedup Complete: %d incoming, %d new, %d skipped (already in database).",
        len(jobs), len(new_jobs), skipped,
    )
    
    return new_jobs, skipped
