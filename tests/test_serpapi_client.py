"""Tests for serpapi_client module."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from pipeline.serpapi_client import (
    _normalize_job,
    _parse_location,
    _parse_posted_at,
    _parse_salary,
    fetch_jobs,
)


# ---------------------------------------------------------------------------
# _parse_location
# ---------------------------------------------------------------------------

def test_parse_location_full():
    city, province, country = _parse_location("Toronto, ON, Canada")
    assert city == "Toronto"
    assert province == "ON"
    assert country == "Canada"


def test_parse_location_two_parts():
    city, province, country = _parse_location("Ontario, Canada")
    assert city is None
    assert province == "Ontario"
    assert country == "Canada"


def test_parse_location_country_only():
    city, province, country = _parse_location("Canada")
    assert city is None
    assert province is None
    assert country == "Canada"


def test_parse_location_none():
    assert _parse_location(None) == (None, None, None)


# ---------------------------------------------------------------------------
# _parse_salary
# ---------------------------------------------------------------------------

def test_salary_annual_range():
    mn, mx, cur, period = _parse_salary("CA$90,000–$120,000 a year")
    assert mn == 90000
    assert mx == 120000
    assert cur == "CAD"
    assert period == "YEAR"


def test_salary_hourly_range():
    mn, mx, cur, period = _parse_salary("$45–$55 an hour")
    assert mn == 45
    assert mx == 55
    assert period == "HOUR"


def test_salary_k_suffix():
    mn, mx, cur, period = _parse_salary("CA$80K a year")
    assert mn == 80000
    assert mx is None
    assert period == "YEAR"


def test_salary_monthly():
    mn, mx, cur, period = _parse_salary("$5,000 a month")
    assert mn == 5000
    assert period == "MONTH"


def test_salary_none():
    mn, mx, cur, period = _parse_salary(None)
    assert mn is None
    assert mx is None
    assert cur == "CAD"
    assert period is None


# ---------------------------------------------------------------------------
# _parse_posted_at
# ---------------------------------------------------------------------------

def test_posted_at_days():
    result = _parse_posted_at("3 days ago")
    assert result is not None
    assert "T" in result  # ISO format


def test_posted_at_weeks():
    result = _parse_posted_at("2 weeks ago")
    assert result is not None


def test_posted_at_hours():
    result = _parse_posted_at("5 hours ago")
    assert result is not None


def test_posted_at_unrecognised():
    assert _parse_posted_at("Just posted") is None


def test_posted_at_none():
    assert _parse_posted_at(None) is None


# ---------------------------------------------------------------------------
# _normalize_job
# ---------------------------------------------------------------------------

def _raw_job(job_id: str = "abc123", **overrides) -> dict:
    base = {
        "job_id": job_id,
        "title": "Data Scientist",
        "company_name": "Acme Corp",
        "location": "Toronto, ON, Canada",
        "description": "We need python and sql skills.",
        "thumbnail": "https://acme.io/logo.png",
        "apply_options": [{"link": "https://acme.io/apply", "title": "Apply"}],
        "detected_extensions": {
            "schedule_type": "Full-time",
            "work_from_home": False,
            "posted_at": "3 days ago",
            "salary": "CA$90,000–$120,000 a year",
        },
    }
    base.update(overrides)
    return base


def test_normalize_job_id_prefix():
    job = _normalize_job(_raw_job("xyz"))
    assert job["job_id"] == "serpapi_xyz"


def test_normalize_job_fields():
    job = _normalize_job(_raw_job())
    assert job["title"] == "Data Scientist"
    assert job["company_name"] == "Acme Corp"
    assert job["company_domain"] is None   # Google Jobs never provides this
    assert job["location_city"] == "Toronto"
    assert job["location_state"] == "ON"
    assert job["location_country"] == "Canada"
    assert job["is_remote"] is False
    assert job["employment_type"] == "FULL_TIME"
    assert job["salary_min"] == 90000
    assert job["salary_max"] == 120000
    assert job["salary_currency"] == "CAD"
    assert job["salary_period"] == "YEAR"
    assert job["job_apply_link"] == "https://acme.io/apply"
    assert job["employer_logo"] == "https://acme.io/logo.png"
    assert job["posted_at"] is not None
    assert job["skills_tags"] == []


def test_normalize_job_remote_true():
    job = _normalize_job(_raw_job(detected_extensions={"work_from_home": True}))
    assert job["is_remote"] is True


def test_normalize_job_no_apply_options():
    job = _normalize_job(_raw_job(apply_options=[]))
    assert job["job_apply_link"] is None


def test_normalize_job_no_salary():
    raw = _raw_job()
    raw["detected_extensions"].pop("salary", None)
    job = _normalize_job(raw)
    assert job["salary_min"] is None
    assert job["salary_max"] is None


# ---------------------------------------------------------------------------
# fetch_jobs
# ---------------------------------------------------------------------------

def _page(n: int, job_id_prefix: str = "j", next_page_token: str | None = None) -> dict:
    resp: dict = {"jobs_results": [_raw_job(f"{job_id_prefix}{i}") for i in range(n)]}
    if next_page_token:
        resp["serpapi_pagination"] = {"next_page_token": next_page_token}
    return resp


def test_fetch_jobs_returns_normalised(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=_page(10))  # no token → stops after one page
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 10
    assert all(j["job_id"].startswith("serpapi_") for j in jobs)


def test_fetch_jobs_stops_on_empty_results(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"jobs_results": [], "serpapi_pagination": {}})
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 0


def test_fetch_jobs_stops_when_no_next_token(httpx_mock: HTTPXMock):
    # First page has results but no token → should not request page 2
    httpx_mock.add_response(json=_page(10, "a"))
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 10
    assert len(httpx_mock.get_requests()) == 1


def test_fetch_jobs_follows_next_page_token(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=_page(10, "p0", next_page_token="tok1"))
    httpx_mock.add_response(json=_page(10, "p1", next_page_token="tok2"))
    httpx_mock.add_response(json=_page(5,  "p2"))  # no token → stop
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 25


def test_fetch_jobs_passes_token_in_second_request(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=_page(10, "p0", next_page_token="mytoken"))
    httpx_mock.add_response(json=_page(5, "p1"))
    fetch_jobs("Data Scientist", max_pages=5)
    requests = httpx_mock.get_requests()
    assert "next_page_token" not in str(requests[0].url)
    assert "next_page_token=mytoken" in str(requests[1].url)


def test_fetch_jobs_respects_max_pages(httpx_mock: HTTPXMock):
    for i in range(3):
        httpx_mock.add_response(json=_page(10, str(i), next_page_token=f"tok{i}"))
    jobs = fetch_jobs("Data Scientist", max_pages=3)
    assert len(jobs) == 30
    assert len(httpx_mock.get_requests()) == 3


def test_fetch_jobs_uses_get(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"jobs_results": []})
    fetch_jobs("Data Scientist", max_pages=1)
    assert httpx_mock.get_requests()[0].method == "GET"


def test_fetch_jobs_no_start_param(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"jobs_results": []})
    fetch_jobs("Data Scientist", max_pages=1)
    assert "start=" not in str(httpx_mock.get_requests()[0].url)


def test_fetch_jobs_no_gl_param(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"jobs_results": []})
    fetch_jobs("Data Scientist", max_pages=1)
    assert "gl=" not in str(httpx_mock.get_requests()[0].url)
