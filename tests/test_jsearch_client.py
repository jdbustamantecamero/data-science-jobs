"""Tests for jsearch_client module."""
from __future__ import annotations

import pytest
import httpx
from pytest_httpx import HTTPXMock

from pipeline.jsearch_client import _normalize_domain, _normalize_job, fetch_jobs


def test_normalize_domain_strips_www():
    assert _normalize_domain("https://www.example.com/jobs") == "example.com"


def test_normalize_domain_none():
    assert _normalize_domain(None) is None


def test_normalize_domain_no_scheme():
    assert _normalize_domain("careers.acme.io") == "careers.acme.io"


def test_normalize_job_basic():
    raw = {
        "job_id": "abc123",
        "job_title": "Data Scientist",
        "employer_name": "Acme Corp",
        "employer_website": "https://www.acme.io",
        "job_city": "San Francisco",
        "job_state": "CA",
        "job_country": "US",
        "job_is_remote": True,
        "job_employment_type": "FULL_TIME",
        "job_min_salary": 100000,
        "job_max_salary": 150000,
        "job_salary_currency": "CAD",
        "job_salary_period": "YEAR",
        "job_description": "We need python and sql skills.",
        "job_apply_link": "https://acme.io/apply",
        "employer_logo": "https://acme.io/logo.png",
        "job_posted_at_datetime_utc": "2026-03-01T10:00:00Z",
    }
    job = _normalize_job(raw)
    assert job["job_id"] == "abc123"
    assert job["company_domain"] == "acme.io"
    assert job["is_remote"] is True
    assert job["salary_min"] == 100000
    assert job["skills_tags"] == []


def test_fetch_jobs_pagination(httpx_mock: HTTPXMock):
    page1 = {"data": [{"job_id": f"j{i}", "job_title": "DS", "employer_name": "Co",
                        "employer_website": None, "job_city": None, "job_state": None,
                        "job_country": "CA", "job_is_remote": False,
                        "job_employment_type": "FULL_TIME", "job_min_salary": None,
                        "job_max_salary": None, "job_salary_currency": None,
                        "job_salary_period": None, "job_description": None,
                        "job_apply_link": None, "employer_logo": None,
                        "job_posted_at_datetime_utc": None} for i in range(10)]}
    page2: dict = {"data": []}  # empty signals end of pages

    httpx_mock.add_response(json=page1)
    httpx_mock.add_response(json=page2)

    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 10
