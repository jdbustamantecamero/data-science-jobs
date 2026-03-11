"""Main pipeline entry point.

Run with:
    python -m pipeline.run_pipeline
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pipeline.adzuna_client as adzuna
import pipeline.jsearch_client as jsearch
import pipeline.serpapi_client as serpapi
import pipeline.theirstack_client as theirstack
from pipeline.data_cleaner import (
    clean_description,
    classify_seniority,
    extract_years_experience,
    infer_location_from_description,
    infer_province_from_city,
    normalize_city,
    normalize_country,
    normalize_province,
    normalize_salary,
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


def _clean_and_enrich_job(job: dict[str, Any]) -> dict[str, Any]:
    """Helper to clean and enrich a single job record."""
    description = clean_description(job.get("job_description"))
    job["job_description"] = description
    job["skills_tags"] = extract_skills(description)
    job["years_experience_min"] = extract_years_experience(description)
    job["seniority"] = classify_seniority(
        job.get("title"), job["years_experience_min"]
    )
    # Location normalisation
    city = normalize_city(job.get("location_city"))
    province = normalize_province(job.get("location_state"))
    country = normalize_country(job.get("location_country"))
    # Infer missing province from city
    if not province and city:
        province = infer_province_from_city(city)
    # Infer missing location from description
    if not city or not province:
        desc_city, desc_province = infer_location_from_description(description)
        city = city or desc_city
        province = province or desc_province
    job["location_city"] = city
    job["location_state"] = province
    job["location_country"] = country
    # Salary normalisation (hourly → annual)
    s_min, s_max, s_period = normalize_salary(
        job.get("salary_min"),
        job.get("salary_max"),
        job.get("salary_period"),
    )
    job["salary_min"] = s_min
    job["salary_max"] = s_max
    job["salary_period"] = s_period
    return job


def run() -> None:
    client = get_service_client()
    run_id = insert_pipeline_run(client)
    start = time.monotonic()

    try:
        # 1. Fetch from all sources in parallel
        query = "Data Scientist"
        max_pages = 5
        fetchers = [
            ("JSearch", jsearch.fetch_jobs),
            ("Adzuna", adzuna.fetch_jobs),
            ("TheirStack", theirstack.fetch_jobs),
            ("SerpAPI", serpapi.fetch_jobs),
        ]

        with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
            futures = {
                executor.submit(func, query, max_pages=max_pages): name
                for name, func in fetchers
            }
            results = {}
            for future in futures:
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception:
                    logger.exception("Failed to fetch jobs from %s", name)
                    results[name] = []

        raw_jobs = results["JSearch"] + results["Adzuna"] + results["TheirStack"] + results["SerpAPI"]
        jobs_fetched = len(raw_jobs)
        logger.info(
            "Fetched %d total jobs: %d JSearch, %d Adzuna, %d TheirStack, %d SerpAPI.",
            jobs_fetched, len(results["JSearch"]), len(results["Adzuna"]),
            len(results["TheirStack"]), len(results["SerpAPI"]),
        )

        # 2. Deduplicate against existing DB rows
        new_jobs, skipped_count = filter_new_jobs(raw_jobs, client)

        # 3. Clean and enrich each new job in-memory (parallelized)
        if new_jobs:
            logger.info("Cleaning and enriching %d new job(s)...", len(new_jobs))
            with ThreadPoolExecutor(max_workers=10) as executor:
                new_jobs = list(executor.map(_clean_and_enrich_job, new_jobs))

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
