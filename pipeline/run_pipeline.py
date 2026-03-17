"""
Main pipeline entry point (Orchestration Layer).

This module coordinates the 3-stage 'Medallion' workflow:
1. Ingest (Bronze): Fetch raw data from all providers in parallel.
2. Transform (Silver): Deduplicate, clean, and enrich job records.
3. Promote (Gold): Load data to Supabase and trigger manual enrichment.

Usage:
    python -m pipeline.run_pipeline
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

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

# Configure logging at the entry point.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


class JobPipeline:
    """
    Stateful orchestrator for the job ingestion pipeline.
    
    This class manages the client connections, shared logic, and the flow 
    of data across the Bronze, Silver, and Gold stages.
    """

    def __init__(self, query: str = "Data Scientist", max_pages: int = 10) -> None:
        """
        Initialize the pipeline with search parameters and providers.
        """
        self.query = query
        self.max_pages = max_pages
        self.client = get_service_client()
        self.transformer = JobTransformer()
        
        # All active API sources are instantiated here.
        self.providers = [
            JSearchProvider(),
            AdzunaProvider(),
            TheirStackProvider(),
            SerpAPIProvider(),
        ]

    def run(self) -> None:
        """
        Execute the full ETL lifecycle for all configured providers.
        """
        # Register the start of this pipeline run in the database for tracking.
        run_id = insert_pipeline_run(self.client)
        start_time = time.monotonic()

        try:
            # ── 1. INGEST (Bronze) ───────────────────────────────────────────
            # Fetch raw data from all providers in parallel to minimize latency.
            raw_jobs = self._ingest()
            jobs_fetched = len(raw_jobs)
            
            # ── 2. DEDUPLICATE ───────────────────────────────────────────────
            # Filter out any jobs that are already stored in the database.
            new_jobs_raw, skipped_count = filter_new_jobs(raw_jobs, self.client)
            
            # ── 3. TRANSFORM (Silver) ────────────────────────────────────────
            # For each new job, apply cleaning, normalization, and enrichment.
            if new_jobs_raw:
                logger.info("Cleaning and enriching %d new job(s)...", len(new_jobs_raw))
                # Use a thread pool for I/O bound transformation tasks.
                with ThreadPoolExecutor(max_workers=10) as executor:
                    enriched_jobs = list(executor.map(self.transformer.transform, new_jobs_raw))
            else:
                enriched_jobs = []

            # ── 4. LOAD ──────────────────────────────────────────────────────
            # Persist the cleaned data to Supabase.
            if enriched_jobs:
                # First ensure that the companies exist to satisfy FK constraints.
                ensure_company_stubs(enriched_jobs, self.client)
                upsert_jobs(enriched_jobs, self.client)

            # ── 5. PROMOTE (Gold) ────────────────────────────────────────────
            # Trigger database-side logic to apply manual curator enrichments.
            if enriched_jobs:
                job_ids = [j["job_id"] for j in enriched_jobs]
                apply_manual_enrichment(job_ids, self.client)

            # Record final success statistics.
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
            # Handle and log catastrophic failures while updating the run status.
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
        """
        Execute parallel ingestion from all registered providers.
        """
        logger.info("Starting Ingest (Bronze) stage...")
        all_jobs: List[JobDict] = []
        
        # Parallel execution reduces total fetch time to the speed of the slowest API.
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
    """Helper entry point for the pipeline module."""
    pipeline = JobPipeline()
    pipeline.run()


if __name__ == "__main__":
    run()
