"""Backfill script — uses JobTransformer to re-enrich all existing rows.

Run with:
    python -m pipeline.backfill_data
"""
from __future__ import annotations

import logging
from typing import Any, List

from pipeline.models import JobDict
from pipeline.supabase_client import get_service_client, upsert_jobs
from pipeline.transformer import JobTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


def _fetch_all_jobs(client) -> List[dict]:
    """Fetch all rows from job_postings."""
    rows = []
    page = 0
    while True:
        resp = (
            client.table("job_postings")
            .select("*")
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
    return rows


def run() -> None:
    client = get_service_client()
    transformer = JobTransformer()
    
    logger.info("Starting backfill: fetching all rows...")
    raw_rows = _fetch_all_jobs(client)
    logger.info("Found %d rows for backfill.", len(raw_rows))

    for i in range(0, len(raw_rows), _BATCH_SIZE):
        batch = raw_rows[i : i + _BATCH_SIZE]
        enriched_batch: List[JobDict] = []
        
        for row in batch:
            # We treat existing rows as 'Bronze' to re-run the Silver logic.
            # If Bronze columns are already present, JobTransformer will use them.
            # If not, it will fall back to Silver columns (starting baseline).
            
            # Prepare a JobDict for the transformer
            job_dict: JobDict = row.copy()
            
            # Ensure Bronze fields exist for the transformer (fallback to Silver)
            fields_to_backfill = [
                "title", "company_name", "company_domain", "location_city",
                "location_state", "location_country", "is_remote", "employment_type",
                "salary_min", "salary_max", "salary_currency", "salary_period",
                "job_description", "job_apply_link", "employer_logo", "posted_at"
            ]
            for f in fields_to_backfill:
                raw_f = f"{f}_raw"
                if job_dict.get(raw_f) is None:
                    job_dict[raw_f] = job_dict.get(f)
            
            # Transform (Bronze -> Silver)
            enriched = transformer.transform(job_dict)
            enriched_batch.append(enriched)

        # Upsert the enriched batch
        upsert_jobs(enriched_batch, client)
        logger.info("Processed rows %d–%d.", i + 1, i + len(batch))

    logger.info("Backfill complete.")


if __name__ == "__main__":
    run()
