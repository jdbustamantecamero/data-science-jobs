"""Data models for the job pipeline."""
from __future__ import annotations

from typing import List, Optional, TypedDict


class JobDict(TypedDict, total=False):
    # ── BRONZE LAYER (Raw API values) ────────────────────────────────────────
    # Every field coming from an external API should have a _raw version.
    title_raw: Optional[str]
    company_name_raw: Optional[str]
    company_domain_raw: Optional[str]
    location_city_raw: Optional[str]
    location_state_raw: Optional[str]
    location_country_raw: Optional[str]
    is_remote_raw: Optional[bool]
    employment_type_raw: Optional[str]
    salary_min_raw: Optional[float]
    salary_max_raw: Optional[float]
    salary_currency_raw: Optional[str]
    salary_period_raw: Optional[str]
    job_description_raw: Optional[str]
    job_apply_link_raw: Optional[str]
    employer_logo_raw: Optional[str]
    posted_at_raw: Optional[str]

    # ── SILVER LAYER (Cleaned / Normalised values) ───────────────────────────
    # These are the fields used for processing and enrichment.
    job_id: str  # Unique across all layers
    title: Optional[str]
    company_name: Optional[str]
    company_domain: Optional[str]
    location_city: Optional[str]
    location_state: Optional[str]
    location_country: Optional[str]
    is_remote: bool
    employment_type: Optional[str]
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: str
    salary_period: Optional[str]
    job_description: Optional[str]
    job_apply_link: Optional[str]
    employer_logo: Optional[str]
    posted_at: Optional[str]

    # Silver-only (Derived in this layer)
    skills_tags: List[str]
    years_experience_min: Optional[int]
    seniority: str
