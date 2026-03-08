"""Fetch job postings from Adzuna API with pagination."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from pipeline.config import ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_BASE_URL

logger = logging.getLogger(__name__)

_RESULTS_PER_PAGE = 50  # Adzuna maximum

_CONTRACT_TIME_MAP = {
    "full_time": "FULL_TIME",
    "part_time": "PART_TIME",
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


def _parse_location(area: list[str]) -> tuple[str | None, str | None, str | None]:
    """Return (city, province, country) from Adzuna location.area array.

    Adzuna area is ordered broad → specific, e.g.:
        ["Canada", "Ontario", "Toronto"]
        ["Canada", "British Columbia"]
    """
    country = area[0] if len(area) > 0 else "Canada"
    province = area[1] if len(area) > 1 else None
    city = area[-1] if len(area) > 2 else None
    return city, province, country


def _is_remote(raw: dict[str, Any]) -> bool:
    """Adzuna has no explicit remote flag — infer from title/description."""
    haystack = " ".join([
        raw.get("title") or "",
        raw.get("description") or "",
    ]).lower()
    return "remote" in haystack


def _normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    area: list[str] = raw.get("location", {}).get("area", [])
    city, province, country = _parse_location(area)

    company_name: str | None = raw.get("company", {}).get("display_name")
    # Adzuna doesn't expose employer website; domain stays None
    domain: str | None = None

    employment_type: str | None = _CONTRACT_TIME_MAP.get(
        raw.get("contract_time", ""), None
    )

    return {
        "job_id": f"adzuna_{raw['id']}",
        "title": raw.get("title"),
        "company_name": company_name,
        "company_domain": domain,
        "location_city": city,
        "location_state": province,
        "location_country": country,
        "is_remote": _is_remote(raw),
        "employment_type": employment_type,
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "salary_currency": "CAD",
        "salary_period": "YEAR",  # Adzuna salaries are always annual
        "job_description": raw.get("description"),
        "job_apply_link": raw.get("redirect_url"),
        "employer_logo": None,
        "posted_at": raw.get("created"),
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
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "results_per_page": str(_RESULTS_PER_PAGE),
                "what": query,
                "where": "Canada",
                "sort_by": "date",
                "max_days_old": "7",
            }
            url = f"{ADZUNA_BASE_URL}/{country}/search/{page}"
            logger.info("Fetching Adzuna page %d for '%s'", page, query)
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("results", [])
            if not raw_jobs:
                logger.info("No more Adzuna results on page %d, stopping.", page)
                break
            for raw in raw_jobs:
                jobs.append(_normalize_job(raw))
            logger.info(
                "Adzuna page %d: %d jobs fetched (total so far: %d)",
                page, len(raw_jobs), len(jobs),
            )

    return jobs
