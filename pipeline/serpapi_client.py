"""Fetch job postings from SerpAPI Google Jobs with pagination.

SerpAPI uses a GET /search endpoint with engine=google_jobs.
Pagination uses next_page_token from serpapi_pagination (NOT start offset —
that parameter is for regular Google Search and causes 400 on google_jobs).
Salary, location, and posted_at all require parsing from raw strings.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

_EST = ZoneInfo("America/Toronto")

import httpx

from pipeline.config import SERPAPI_API_KEY, SERPAPI_BASE_URL

logger = logging.getLogger(__name__)

_PAGE_SIZE = 10  # Google Jobs always returns 10 results per page

_EMPLOYMENT_TYPE_MAP = {
    "full-time": "FULL_TIME",
    "full time": "FULL_TIME",
    "part-time": "PART_TIME",
    "part time": "PART_TIME",
    "contractor": "CONTRACT",
    "contract": "CONTRACT",
    "temporary": "TEMPORARY",
    "temp": "TEMPORARY",
    "internship": "INTERN",
    "intern": "INTERN",
}


# ---------------------------------------------------------------------------
# Location parsing
# ---------------------------------------------------------------------------

def _parse_location(location: str | None) -> tuple[str | None, str | None, str | None]:
    """Split 'Toronto, ON, Canada' into (city, province, country).

    Google Jobs location strings are generally:
        "City, Province, Country"
        "Province, Country"
        "Country"
    """
    if not location:
        return None, None, None
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 3:
        return parts[0], parts[-2], parts[-1]
    if len(parts) == 2:
        return None, parts[0], parts[1]
    return None, None, parts[0]


# ---------------------------------------------------------------------------
# Salary parsing
# ---------------------------------------------------------------------------

# Matches optional currency prefix, numeric amount with optional K suffix
_AMOUNT_RE = re.compile(r"(?:CA\$|C\$|\$|CAD\s*)?([\d,]+(?:\.\d+)?)\s*([Kk])?")

_PERIOD_MAP = {
    "year": "YEAR", "yr": "YEAR", "annual": "YEAR", "annually": "YEAR",
    "hour": "HOUR", "hr": "HOUR", "hourly": "HOUR",
    "month": "MONTH", "monthly": "MONTH",
    "week": "WEEK", "weekly": "WEEK",
}
_PERIOD_RE = re.compile(
    r"(?:a|an|per)\s+(year|yr|hour|hr|month|week|annual|annually|hourly|monthly|weekly)",
    re.I,
)


def _parse_amount(text: str) -> float | None:
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
        if m.group(2):          # K/k suffix
            val *= 1000
        return val
    except ValueError:
        return None


def _parse_salary(
    salary_str: str | None,
) -> tuple[float | None, float | None, str, str | None]:
    """Return (salary_min, salary_max, currency, period) from a raw salary string.

    Examples handled:
        "CA$90,000–$120,000 a year"   → (90000, 120000, "CAD", "YEAR")
        "$45–$55 an hour"             → (45, 55, "CAD", "HOUR")
        "CA$80K a year"               → (80000, None, "CAD", "YEAR")
        "$5,000 a month"              → (5000, None, "CAD", "MONTH")
    """
    if not salary_str:
        return None, None, "CAD", None

    currency = "CAD"  # targeting Canadian jobs

    # Split on range separator (–, -, to)
    range_parts = re.split(r"\s*[–\-]\s*|\s+to\s+", salary_str, maxsplit=1)
    salary_min = _parse_amount(range_parts[0])
    salary_max = _parse_amount(range_parts[1]) if len(range_parts) > 1 else None

    period_match = _PERIOD_RE.search(salary_str)
    period = _PERIOD_MAP.get(period_match.group(1).lower()) if period_match else None

    return salary_min, salary_max, currency, period


# ---------------------------------------------------------------------------
# Posted-at parsing
# ---------------------------------------------------------------------------

_RELATIVE_DATE_RE = re.compile(r"(\d+)\s+(hour|day|week|month)s?\s+ago", re.I)


def _parse_posted_at(relative: str | None) -> str | None:
    """Convert '3 days ago' → approximate EST ISO string, or return None."""
    if not relative:
        return None
    m = _RELATIVE_DATE_RE.search(relative)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    delta_map = {"hour": timedelta(hours=n), "day": timedelta(days=n),
                 "week": timedelta(weeks=n), "month": timedelta(days=n * 30)}
    approx = datetime.now(tz=_EST) - delta_map[unit]
    return approx.isoformat()


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

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
    detected = raw.get("detected_extensions") or {}

    city, province, country = _parse_location(raw.get("location"))

    schedule_type: str | None = detected.get("schedule_type")
    employment_type = _EMPLOYMENT_TYPE_MAP.get(
        (schedule_type or "").lower().strip(), schedule_type or None
    )

    salary_min, salary_max, currency, period = _parse_salary(detected.get("salary"))

    # Best available apply link
    apply_options: list[dict] = raw.get("apply_options") or []
    apply_link: str | None = apply_options[0].get("link") if apply_options else None

    return {
        "job_id": f"serpapi_{raw['job_id']}",
        "title": raw.get("title"),
        "company_name": raw.get("company_name"),
        "company_domain": None,  # Google Jobs does not expose employer website
        "location_city": city,
        "location_state": province,
        "location_country": country,
        "is_remote": bool(detected.get("work_from_home", False)),
        "employment_type": employment_type,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
        "salary_period": period,
        "job_description": raw.get("description"),
        "job_apply_link": apply_link,
        "employer_logo": raw.get("thumbnail"),
        "posted_at": _parse_posted_at(detected.get("posted_at")),
        "skills_tags": [],  # filled by skills_parser later
    }


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_jobs(
    query: str = "Data Scientist",
    max_pages: int = 5,
    location: str = "Canada",
) -> list[dict[str, Any]]:
    """Return a flat list of normalised job dicts across *max_pages* pages.

    Google Jobs pagination uses next_page_token, not start offset.
    gl is omitted — location alone is sufficient and combining both causes 400s.
    """
    jobs: list[dict[str, Any]] = []
    next_page_token: str | None = None

    with httpx.Client(timeout=30) as client:
        for page in range(max_pages):
            params: dict[str, Any] = {
                "engine": "google_jobs",
                "q": query,
                "location": location,
                "hl": "en",
                "api_key": SERPAPI_API_KEY,
            }
            if next_page_token:
                params["next_page_token"] = next_page_token

            logger.info("Fetching SerpAPI page %d for '%s'", page, query)
            resp = client.get(SERPAPI_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            raw_jobs: list[dict] = data.get("jobs_results", [])
            if not raw_jobs:
                logger.info("No more SerpAPI results on page %d, stopping.", page)
                break
            for raw in raw_jobs:
                jobs.append(_normalize_job(raw))
            logger.info(
                "SerpAPI page %d: %d jobs fetched (total so far: %d)",
                page, len(raw_jobs), len(jobs),
            )

            next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")
            if not next_page_token:
                logger.info("No next_page_token on page %d, stopping.", page)
                break

    return jobs
