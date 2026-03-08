"""Bulk deduplication: filter out job_ids already in Supabase."""
from __future__ import annotations

import logging
from typing import Any

from supabase import Client

logger = logging.getLogger(__name__)


def filter_new_jobs(
    jobs: list[dict[str, Any]],
    client: Client,
) -> tuple[list[dict[str, Any]], int]:
    """Return (new_jobs, skipped_count).

    Issues a single query: WHERE job_id = ANY(array_of_ids).
    """
    if not jobs:
        return [], 0

    incoming_ids = [j["job_id"] for j in jobs]

    response = (
        client.table("job_postings")
        .select("job_id")
        .in_("job_id", incoming_ids)
        .execute()
    )
    existing_ids: set[str] = {row["job_id"] for row in response.data}

    new_jobs = [j for j in jobs if j["job_id"] not in existing_ids]
    skipped = len(jobs) - len(new_jobs)
    logger.info(
        "Dedup: %d incoming, %d new, %d skipped (already exist)",
        len(jobs), len(new_jobs), skipped,
    )
    return new_jobs, skipped
