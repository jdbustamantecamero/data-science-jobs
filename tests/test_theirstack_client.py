"""Tests for theirstack_client module."""
from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from pipeline.theirstack_client import (
    _normalize_domain,
    _normalize_employment_type,
    _normalize_job,
    fetch_jobs,
)


def _raw_job(job_id: str = "ts123", **overrides) -> dict:
    base = {
        "id": job_id,
        "job_title": "Data Scientist",
        "company_name": "Acme Corp",
        "company_url": "https://www.acme.io",
        "company_logo": "https://acme.io/logo.png",
        "city": "Toronto",
        "state": "Ontario",
        "country": "Canada",
        "remote": False,
        "employment_type": "full_time",
        "salary_min": 95000,
        "salary_max": 135000,
        "salary_currency": "CAD",
        "salary_period": "YEAR",
        "description": "We need python and sql skills.",
        "url": "https://acme.io/jobs/123",
        "date_posted": "2026-03-01",
    }
    base.update(overrides)
    return base


# --- _normalize_domain ---

def test_normalize_domain_strips_www():
    assert _normalize_domain("https://www.acme.io") == "acme.io"


def test_normalize_domain_bare():
    assert _normalize_domain("careers.acme.io") == "careers.acme.io"


def test_normalize_domain_none():
    assert _normalize_domain(None) is None


# --- _normalize_employment_type ---

def test_employment_type_full_time_variants():
    for raw in ("full_time", "full-time", "Full Time", "FULLTIME"):
        assert _normalize_employment_type(raw) == "FULL_TIME", f"failed for '{raw}'"


def test_employment_type_part_time_variants():
    for raw in ("part_time", "part-time", "Part Time"):
        assert _normalize_employment_type(raw) == "PART_TIME", f"failed for '{raw}'"


def test_employment_type_contract():
    assert _normalize_employment_type("contract") == "CONTRACT"
    assert _normalize_employment_type("contractor") == "CONTRACT"


def test_employment_type_unknown_uppercased():
    assert _normalize_employment_type("casual") == "CASUAL"


def test_employment_type_none():
    assert _normalize_employment_type(None) is None


# --- _normalize_job ---

def test_normalize_job_id_prefix():
    job = _normalize_job(_raw_job("abc"))
    assert job["job_id"] == "theirstack_abc"


def test_normalize_job_fields():
    job = _normalize_job(_raw_job())
    assert job["title"] == "Data Scientist"
    assert job["company_name"] == "Acme Corp"
    assert job["company_domain"] == "acme.io"
    assert job["location_city"] == "Toronto"
    assert job["location_state"] == "Ontario"
    assert job["location_country"] == "Canada"
    assert job["is_remote"] is False
    assert job["employment_type"] == "FULL_TIME"
    assert job["salary_min"] == 95000
    assert job["salary_currency"] == "CAD"
    assert job["salary_period"] == "YEAR"
    assert job["job_apply_link"] == "https://acme.io/jobs/123"
    assert job["employer_logo"] == "https://acme.io/logo.png"
    assert job["posted_at"] == "2026-03-01"
    assert job["skills_tags"] == []


def test_normalize_job_remote_flag():
    job = _normalize_job(_raw_job(remote=True))
    assert job["is_remote"] is True


def test_normalize_job_missing_salary_currency_defaults_to_cad():
    job = _normalize_job(_raw_job(salary_currency=None))
    assert job["salary_currency"] == "CAD"


def test_normalize_job_missing_salary_period_defaults_to_year():
    job = _normalize_job(_raw_job(salary_period=None))
    assert job["salary_period"] == "YEAR"


def test_normalize_job_no_company_url():
    job = _normalize_job(_raw_job(company_url=None))
    assert job["company_domain"] is None


# --- fetch_jobs ---

def test_fetch_jobs_returns_normalised(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"data": [_raw_job(str(i)) for i in range(10)], "total": 10}
    )
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 10
    assert all(j["job_id"].startswith("theirstack_") for j in jobs)


def test_fetch_jobs_stops_on_empty_page(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"data": [_raw_job("1")], "total": 1})
    httpx_mock.add_response(json={"data": [], "total": 1})
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 1


def test_fetch_jobs_stops_when_total_reached(httpx_mock: HTTPXMock):
    # total=5 means only one page needed even though max_pages=5
    httpx_mock.add_response(
        json={"data": [_raw_job(str(i)) for i in range(5)], "total": 5}
    )
    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 5


def test_fetch_jobs_uses_post(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"data": [], "total": 0})
    fetch_jobs("Data Scientist", max_pages=1)
    request = httpx_mock.get_requests()[0]
    assert request.method == "POST"


def test_fetch_jobs_sends_bearer_auth(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"data": [], "total": 0})
    fetch_jobs("Data Scientist", max_pages=1)
    request = httpx_mock.get_requests()[0]
    assert request.headers["authorization"].startswith("Bearer ")
