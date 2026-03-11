"""Main pipeline entry point.

Ingest (Bronze) -> Transform (Silver) -> Promote (Gold)
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List

from pipeline.deduplication import filter_new_jobs
from pipeline.models import JobDict
from pipeline.providers.adzuna import AdzunaProvider
from pipeline.providers.jsearch import JSearchProvider
from pipeline.providers.serpapi import SerpAPIProvider
from pipeline.providers.theirstack import TheirStackProvider
from pipeline.supabase_client import (
    apply_manual_enrichment,
    ensure_company_stubs,
    get_service_client,
    insert_pipeline_run,
    update_pipeline_run,
    upsert_jobs,
)
from pipeline.transformer import JobTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


class JobPipeline:
    """Orchestrates the 3-stage pipeline."""

    def __init__(self, query: str = "Data Scientist", max_pages: int = 5) -> None:
        self.query = query
        self.max_pages = max_pages
        self.client = get_service_client()
        self.transformer = JobTransformer()
        self.providers = [
            JSearchProvider(),
            AdzunaProvider(),
            TheirStackProvider(),
            SerpAPIProvider(),
        ]

    def run(self) -> None:
        """Execute the full pipeline."""
        run_id = insert_pipeline_run(self.client)
        start_time = time.monotonic()

        try:
            # 1. INGEST (Bronze)
            raw_jobs = self._ingest()
            jobs_fetched = len(raw_jobs)
            
            # 2. DEDUPLICATE
            new_jobs_raw, skipped_count = filter_new_jobs(raw_jobs, self.client)
            
            # 3. TRANSFORM (Silver)
            if new_jobs_raw:
                logger.info("Cleaning and enriching %d new job(s)...", len(new_jobs_raw))
                # Parallelize transformation for speed
                with ThreadPoolExecutor(max_workers=10) as executor:
                    enriched_jobs = list(executor.map(self.transformer.transform, new_jobs_raw))
            else:
                enriched_jobs = []

            # 4. LOAD
            if enriched_jobs:
                ensure_company_stubs(enriched_jobs, self.client)
                upsert_jobs(enriched_jobs, self.client)

            # 5. PROMOTE (Gold)
            if enriched_jobs:
                job_ids = [j["job_id"] for j in enriched_jobs]
                apply_manual_enrichment(job_ids, self.client)
                # Note: Materialized view refresh could be triggered here if needed.

            duration = round(time.monotonic() - start_time, 2)
            update_pipeline_run(
                run_id,
                self.client,
                status="success",
                jobs_fetched=jobs_fetched,
                jobs_new=len(enriched_jobs),
                jobs_skipped=skipped_count,
                duration_seconds=duration,
            )
            logger.info(
                "Pipeline complete in %.1fs: %d new, %d skipped.",
                duration, len(enriched_jobs), skipped_count,
            )

        except Exception as exc:
            duration = round(time.monotonic() - start_time, 2)
            logger.exception("Pipeline failed after %.1fs: %s", duration, exc)
            update_pipeline_run(
                run_id,
                self.client,
                status="failed",
                error_message=str(exc),
                duration_seconds=duration,
            )
            raise

    def _ingest(self) -> List[JobDict]:
        """Fetch from all providers in parallel."""
        logger.info("Starting Ingest (Bronze) stage...")
        all_jobs: List[JobDict] = []
        
        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            futures = {
                executor.submit(p.fetch_jobs, self.query, self.max_pages): p.name
                for p in self.providers
            }
            for future in futures:
                name = futures[future]
                try:
                    results = future.result()
                    all_jobs.extend(results)
                    logger.info("Fetched %d jobs from %s", len(results), name)
                except Exception:
                    logger.exception("Failed to fetch jobs from %s", name)

        logger.info("Ingest complete: %d total jobs fetched.", len(all_jobs))
        return all_jobs


def run() -> None:
    pipeline = JobPipeline()
    pipeline.run()


if __name__ == "__main__":
    run()
