"""Tests for deduplication module."""
from __future__ import annotations

from unittest.mock import MagicMock

from pipeline.deduplication import filter_new_jobs


def _make_mock_client(existing_ids: list[str]) -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"job_id": jid} for jid in existing_ids
    ]
    return client


def test_all_new():
    jobs = [{"job_id": "a"}, {"job_id": "b"}]
    client = _make_mock_client([])
    new_jobs, skipped = filter_new_jobs(jobs, client)
    assert len(new_jobs) == 2
    assert skipped == 0


def test_all_existing():
    jobs = [{"job_id": "a"}, {"job_id": "b"}]
    client = _make_mock_client(["a", "b"])
    new_jobs, skipped = filter_new_jobs(jobs, client)
    assert len(new_jobs) == 0
    assert skipped == 2


def test_partial_dedup():
    jobs = [{"job_id": "a"}, {"job_id": "b"}, {"job_id": "c"}]
    client = _make_mock_client(["b"])
    new_jobs, skipped = filter_new_jobs(jobs, client)
    assert len(new_jobs) == 2
    assert skipped == 1
    assert all(j["job_id"] != "b" for j in new_jobs)


def test_empty_input():
    client = _make_mock_client([])
    new_jobs, skipped = filter_new_jobs([], client)
    assert new_jobs == []
    assert skipped == 0
