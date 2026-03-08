"""Tests for adzuna_client module."""
from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from pipeline.adzuna_client import (
    _is_remote,
    _normalize_job,
    _parse_location,
    fetch_jobs,
)


def _raw_job(job_id: str = "123", **overrides) -> dict:
    base = {
        "id": job_id,
        "title": "Data Scientist",
        "company": {"display_name": "Acme Corp"},
        "location": {"area": ["Canada", "Ontario", "Toronto"], "display_name": "Toronto"},
        "description": "We need python and sql skills.",
        "redirect_url": "https://adzuna.ca/jobs/123",
        "salary_min": 90000.0,
        "salary_max": 130000.0,
        "contract_time": "full_time",
        "created": "2026-03-01T10:00:00Z",
    }
    base.update(overrides)
    return base


# --- _parse_location ---

def test_parse_location_full():
    city, province, country = _parse_location(["Canada", "Ontario", "Toronto"])
    assert city == "Toronto"
    assert province == "Ontario"
    assert country == "Canada"


def test_parse_location_province_only():
    city, province, country = _parse_location(["Canada", "British Columbia"])
    assert city is None
    assert province == "British Columbia"
    assert country == "Canada"


def test_parse_location_empty():
    city, province, country = _parse_location([])
    assert city is None
    assert province is None
    assert country == "Canada"


# --- _is_remote ---

def test_is_remote_in_title():
    assert _is_remote({"title": "Remote Data Scientist", "description": ""}) is True


def test_is_remote_in_description():
    assert _is_remote({"title": "Data Scientist", "description": "This is a remote role."}) is True


def test_is_remote_false():
    assert _is_remote({"title": "Data Scientist", "description": "On-site in Toronto."}) is False


# --- _normalize_job ---

def test_normalize_job_prefixes_id():
    job = _normalize_job(_raw_job("abc"))
    assert job["job_id"] == "adzuna_abc"


def test_normalize_job_fields():
    job = _normalize_job(_raw_job())
    assert job["company_name"] == "Acme Corp"
    assert job["location_city"] == "Toronto"
    assert job["location_state"] == "Ontario"
    assert job["location_country"] == "Canada"
    assert job["employment_type"] == "FULL_TIME"
    assert job["salary_min"] == 90000.0
    assert job["salary_currency"] == "CAD"
    assert job["salary_period"] == "YEAR"
    assert job["company_domain"] is None
    assert job["employer_logo"] is None
    assert job["skills_tags"] == []


def test_normalize_job_unknown_contract_time():
    job = _normalize_job(_raw_job(contract_time="contract"))
    assert job["employment_type"] is None


# --- fetch_jobs ---

def test_fetch_jobs_pagination(httpx_mock: HTTPXMock):
    page1 = {"results": [_raw_job(str(i)) for i in range(10)]}
    page2: dict = {"results": []}

    httpx_mock.add_response(json=page1)
    httpx_mock.add_response(json=page2)

    jobs = fetch_jobs("Data Scientist", max_pages=5)
    assert len(jobs) == 10
    assert all(j["job_id"].startswith("adzuna_") for j in jobs)


def test_fetch_jobs_respects_max_pages(httpx_mock: HTTPXMock):
    full_page = {"results": [_raw_job(str(i)) for i in range(50)]}

    # Always return a full page — max_pages=2 should stop after 2 requests
    httpx_mock.add_response(json=full_page)
    httpx_mock.add_response(json=full_page)

    jobs = fetch_jobs("Data Scientist", max_pages=2)
    assert len(jobs) == 100
