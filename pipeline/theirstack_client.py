"""Fetch job postings from TheirStack API with pagination.

TheirStack uses a POST /v1/jobs/search endpoint with a JSON body.
Pages are 0-indexed; each response contains a `data` array and a `total` count.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from pipeline.config import THEIRSTACK_API_KEY, THEIRSTACK_BASE_URL

logger = logging.getLogger(__name__)

_PAGE_SIZE = 25  # TheirStack default; increase if your plan allows

# TheirStack may return various employment type strings — normalise to the
# same values used by JSearch so dashboard filters work across sources.
_EMPLOYMENT_TYPE_MAP = {
    "full_time": "FULL_TIME",
    "full-time": "FULL_TIME",
    "fulltime": "FULL_TIME",
    "full time": "FULL_TIME",
    "part_time": "PART_TIME",
    "part-time": "PART_TIME",
    "parttime": "PART_TIME",
    "part time": "PART_TIME",
    "contract": "CONTRACT",
    "contractor": "CONTRACT",
    "temporary": "TEMPORARY",
    "intern": "INTERN",
    "internship": "INTERN",
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


def _normalize_employment_type(raw_type: str | None) -> str | None:
    if not raw_type:
        return None
    return _EMPLOYMENT_TYPE_MAP.get(raw_type.lower().strip(), raw_type.upper())


def _normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": f"theirstack_{raw['id']}",
        "title": raw.get("job_title"),
        "company_name": raw.get("company_name"),
        "company_domain": _normalize_domain(raw.get("company_url")),
        "location_city": raw.get("city"),
        "location_state": raw.get("state"),
        "location_country": raw.get("country"),
        "is_remote": bool(raw.get("remote", False)),
        "employment_type": _normalize_employment_type(raw.get("employment_type")),
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "salary_currency": raw.get("salary_currency") or "CAD",
        "salary_period": raw.get("salary_period") or "YEAR",
        "job_description": raw.get("description"),
        "job_apply_link": raw.get("url"),
        "employer_logo": raw.get("company_logo"),
        "posted_at": raw.get("date_posted"),
        "skills_tags": [],  # filled by skills_parser later
    }


def fetch_jobs(
    query: str = "Data Scientist",
    max_pages: int = 5,
    country_code: str = "CA",
) -> list[dict[str, Any]]:
    """Return a flat list of normalised job dicts across *max_pages* pages."""
    jobs: list[dict[str, Any]] = []
    headers = {
        "Authorization": f"Bearer {THEIRSTACK_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        for page in range(0, max_pages):
            payload = {
                "page": page,
                "limit": _PAGE_SIZE,
                "order_by": [{"desc": True, "field": "date_posted"}],
                "job_title_or": [query],
                "job_country_code_or": [country_code],
                "posted_at_max_age_days": 7,
            }
            logger.info("Fetching TheirStack page %d for '%s'", page, query)
            resp = client.post(
                f"{THEIRSTACK_BASE_URL}/jobs/search",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("data", [])
            if not raw_jobs:
                logger.info("No more TheirStack results on page %d, stopping.", page)
                break
            for raw in raw_jobs:
                jobs.append(_normalize_job(raw))
            logger.info(
                "TheirStack page %d: %d jobs fetched (total so far: %d)",
                page, len(raw_jobs), len(jobs),
            )
            # Stop early if we've received all available results
            total = data.get("total", 0)
            if len(jobs) >= total:
                break

    return jobs
