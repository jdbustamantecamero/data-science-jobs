"""One-time backfill script — normalises and enriches all existing DB rows.

Run with:
    venv/bin/python -m pipeline.backfill_data

What it does (for all 463+ existing rows):
  - Normalises location_city, location_state, location_country
  - Infers missing province from city; infers both from description
  - Re-classifies seniority for NULL rows
  - Re-extracts years_experience_min for NULL rows
  - Re-extracts skills_tags using the expanded SKILLS list
  - Converts hourly salaries to annual
"""
from __future__ import annotations

import logging

from pipeline.config import SUPABASE_SERVICE_KEY, SUPABASE_URL
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
from pipeline.skills_parser import extract_skills
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_BATCH_SIZE = 50


def _fetch_all(client) -> list[dict]:
    rows = []
    page = 0
    while True:
        resp = (
            client.table("job_postings")
            .select(
                "job_id, title, job_description, "
                "location_city, location_state, location_country, "
                "seniority, years_experience_min, skills_tags, "
                "salary_min, salary_max, salary_period"
            )
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
    return rows


def _patch(client, updates: list[dict]) -> None:
    """Issue individual updates (Supabase REST doesn't support bulk UPDATE)."""
    for upd in updates:
        job_id = upd.pop("job_id")
        client.table("job_postings").update(upd).eq("job_id", job_id).execute()


def run() -> None:
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    rows = _fetch_all(client)
    logger.info("Fetched %d rows for backfill.", len(rows))

    updates: list[dict] = []

    for row in rows:
        patch: dict = {"job_id": row["job_id"]}
        changed = False

        # ── Description (ensure clean for downstream steps) ───────────────────
        description = row.get("job_description") or ""
        cleaned = clean_description(description) if description else description

        # ── Skills: re-extract for ALL rows with expanded list ────────────────
        new_skills = extract_skills(cleaned)
        old_skills = row.get("skills_tags") or []
        if sorted(new_skills) != sorted(old_skills):
            patch["skills_tags"] = new_skills
            changed = True

        # ── Years experience: fill NULLs ──────────────────────────────────────
        if row.get("years_experience_min") is None and cleaned:
            yrs = extract_years_experience(cleaned)
            if yrs is not None:
                patch["years_experience_min"] = yrs
                changed = True

        # ── Seniority: re-classify NULLs ─────────────────────────────────────
        if row.get("seniority") is None:
            yrs_for_seniority = (
                patch.get("years_experience_min") or row.get("years_experience_min")
            )
            seniority = classify_seniority(row.get("title"), yrs_for_seniority)
            patch["seniority"] = seniority
            changed = True

        # ── Location normalisation ────────────────────────────────────────────
        city = normalize_city(row.get("location_city"))
        province = normalize_province(row.get("location_state"))
        country = normalize_country(row.get("location_country"))

        if not province and city:
            province = infer_province_from_city(city)

        if not city or not province:
            desc_city, desc_province = infer_location_from_description(cleaned)
            city = city or desc_city
            province = province or desc_province

        if city != row.get("location_city"):
            patch["location_city"] = city
            changed = True
        if province != row.get("location_state"):
            patch["location_state"] = province
            changed = True
        if country != row.get("location_country"):
            patch["location_country"] = country
            changed = True

        # ── Salary normalisation (hourly → annual) ────────────────────────────
        s_min, s_max, s_period = normalize_salary(
            row.get("salary_min"),
            row.get("salary_max"),
            row.get("salary_period"),
        )
        if s_min != row.get("salary_min") or s_period != row.get("salary_period"):
            patch["salary_min"] = s_min
            patch["salary_max"] = s_max
            patch["salary_period"] = s_period
            changed = True

        if changed:
            updates.append(patch)

    logger.info("%d rows need updates.", len(updates))

    # Push updates in batches
    for i in range(0, len(updates), _BATCH_SIZE):
        batch = updates[i : i + _BATCH_SIZE]
        _patch(client, batch)
        logger.info("Updated rows %d–%d.", i + 1, i + len(batch))

    logger.info("Backfill complete.")


if __name__ == "__main__":
    run()
