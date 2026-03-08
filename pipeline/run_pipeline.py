"""Main pipeline entry point.

Run with:
    python -m pipeline.run_pipeline
"""
from __future__ import annotations

import logging
import time

import pipeline.adzuna_client as adzuna
import pipeline.jsearch_client as jsearch
import pipeline.theirstack_client as theirstack
from pipeline.data_cleaner import (
    clean_description,
    classify_seniority,
    extract_years_experience,
)
from pipeline.deduplication import filter_new_jobs
from pipeline.skills_parser import extract_skills
from pipeline.supabase_client import (
    apply_manual_enrichment,
    ensure_company_stubs,
    get_service_client,
    insert_pipeline_run,
    update_pipeline_run,
    upsert_jobs,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    client = get_service_client()
    run_id = insert_pipeline_run(client)
    start = time.monotonic()

    try:
        # 1. Fetch from all sources and combine
        jsearch_jobs = jsearch.fetch_jobs("Data Scientist", max_pages=5)
        adzuna_jobs = adzuna.fetch_jobs("Data Scientist", max_pages=5)
        theirstack_jobs = theirstack.fetch_jobs("Data Scientist", max_pages=5)
        raw_jobs = jsearch_jobs + adzuna_jobs + theirstack_jobs
        jobs_fetched = len(raw_jobs)
        logger.info(
            "Fetched %d total jobs: %d from JSearch, %d from Adzuna, %d from TheirStack.",
            jobs_fetched, len(jsearch_jobs), len(adzuna_jobs), len(theirstack_jobs),
        )

        # 2. Deduplicate against existing DB rows
        new_jobs, skipped_count = filter_new_jobs(raw_jobs, client)

        # 3. Clean and enrich each new job in-memory
        for job in new_jobs:
            description = clean_description(job.get("job_description"))
            job["job_description"] = description
            job["skills_tags"] = extract_skills(description)
            job["years_experience_min"] = extract_years_experience(description)
            job["seniority"] = classify_seniority(
                job.get("title"), job["years_experience_min"]
            )

        # 4. Ensure company stub rows exist (satisfies FK constraint)
        ensure_company_stubs(new_jobs, client)

        # 5. Upsert jobs
        upsert_jobs(new_jobs, client)

        # 6. Fill any NULL fields from manual enrichment table
        new_job_ids = [j["job_id"] for j in new_jobs]
        apply_manual_enrichment(new_job_ids, client)

        duration = round(time.monotonic() - start, 2)
        update_pipeline_run(
            run_id,
            client,
            status="success",
            jobs_fetched=jobs_fetched,
            jobs_new=len(new_jobs),
            jobs_skipped=skipped_count,
            duration_seconds=duration,
        )
        logger.info(
            "Pipeline complete in %.1fs: %d new, %d skipped.",
            duration, len(new_jobs), skipped_count,
        )

    except Exception as exc:
        duration = round(time.monotonic() - start, 2)
        logger.exception("Pipeline failed after %.1fs: %s", duration, exc)
        update_pipeline_run(
            run_id,
            client,
            status="failed",
            error_message=str(exc),
            duration_seconds=duration,
        )
        raise


if __name__ == "__main__":
    run()
