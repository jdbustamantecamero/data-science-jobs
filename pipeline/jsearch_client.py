"""Fetch job postings from JSearch (RapidAPI) with pagination."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from pipeline.config import JSEARCH_API_KEY, JSEARCH_BASE_URL, JSEARCH_HOST

logger = logging.getLogger(__name__)

_HEADERS = {
    "X-RapidAPI-Key": JSEARCH_API_KEY,
    "X-RapidAPI-Host": JSEARCH_HOST,
}


def _normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        netloc = parsed.netloc or parsed.path
        return netloc.replace("www.", "").lower().strip("/") or None
    except Exception:
        return None


def _normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    employer_website = raw.get("employer_website") or raw.get("job_apply_link", "")
    domain = _normalize_domain(employer_website)
    return {
        "job_id": raw["job_id"],
        "title": raw.get("job_title"),
        "company_name": raw.get("employer_name"),
        "company_domain": domain,
        "location_city": raw.get("job_city"),
        "location_state": raw.get("job_state"),
        "location_country": raw.get("job_country"),
        "is_remote": raw.get("job_is_remote", False),
        "employment_type": raw.get("job_employment_type"),
        "salary_min": raw.get("job_min_salary"),
        "salary_max": raw.get("job_max_salary"),
        "salary_currency": raw.get("job_salary_currency") or "CAD",
        "salary_period": raw.get("job_salary_period"),
        "job_description": raw.get("job_description"),
        "job_apply_link": raw.get("job_apply_link"),
        "employer_logo": raw.get("employer_logo"),
        "posted_at": raw.get("job_posted_at_datetime_utc"),
        "skills_tags": [],  # filled by skills_parser later
    }


def fetch_jobs(
    query: str = "Data Scientist",
    max_pages: int = 5,
    country: str = "ca",
) -> list[dict[str, Any]]:
    """Return a flat list of normalised job dicts across *max_pages* pages."""
    jobs: list[dict[str, Any]] = []

    with httpx.Client(timeout=30) as client:
        for page in range(1, max_pages + 1):
            params = {
                "query": query,
                "page": str(page),
                "num_pages": "1",
                "country": country,
                "date_posted": "week",
            }
            logger.info("Fetching JSearch page %d for '%s'", page, query)
            resp = client.get(
                f"{JSEARCH_BASE_URL}/search",
                headers=_HEADERS,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("data", [])
            if not raw_jobs:
                logger.info("No more results on page %d, stopping.", page)
                break
            for raw in raw_jobs:
                jobs.append(_normalize_job(raw))
            logger.info("Page %d: %d jobs fetched (total so far: %d)", page, len(raw_jobs), len(jobs))

    return jobs
