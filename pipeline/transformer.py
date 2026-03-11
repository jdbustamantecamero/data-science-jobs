"""Transformer to clean and enrich job records (Bronze -> Silver)."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from pipeline.data_cleaner import (
    classify_seniority,
    clean_description,
    extract_years_experience,
    infer_location_from_description,
    infer_province_from_city,
    normalize_city,
    normalize_country,
    normalize_province,
    normalize_salary,
)
from pipeline.models import JobDict
from pipeline.skills_parser import extract_skills

logger = logging.getLogger(__name__)


class JobTransformer:
    """Handles the transformation from Bronze (raw) to Silver (cleaned) layer."""

    def transform(self, job: JobDict) -> JobDict:
        """Clean and enrich a single job record."""
        # 1. Initialize Silver fields from Bronze
        # Most fields start as a direct copy of the raw API value.
        job["title"] = job.get("title_raw")
        job["company_name"] = job.get("company_name_raw")
        job["location_city"] = job.get("location_city_raw")
        job["location_state"] = job.get("location_state_raw")
        job["location_country"] = job.get("location_country_raw")
        job["is_remote"] = bool(job.get("is_remote_raw", False))
        job["employment_type"] = job.get("employment_type_raw")
        job["salary_min"] = job.get("salary_min_raw")
        job["salary_max"] = job.get("salary_max_raw")
        job["salary_currency"] = job.get("salary_currency_raw") or "CAD"
        job["salary_period"] = job.get("salary_period_raw")
        job["job_description"] = job.get("job_description_raw")
        job["job_apply_link"] = job.get("job_apply_link_raw")
        job["employer_logo"] = job.get("employer_logo_raw")
        job["posted_at"] = job.get("posted_at_raw")

        # 2. Description Cleaning
        cleaned_desc = clean_description(job.get("job_description"))
        job["job_description"] = cleaned_desc

        # 3. Location Normalization
        city = normalize_city(job.get("location_city"))
        province = normalize_province(job.get("location_state"))
        country = normalize_country(job.get("location_country"))

        # Infer missing province from city
        if not province and city:
            province = infer_province_from_city(city)

        # Infer missing location from description
        if not city or not province:
            desc_city, desc_province = infer_location_from_description(cleaned_desc)
            city = city or desc_city
            province = province or desc_province
            
        job["location_city"] = city
        job["location_state"] = province
        job["location_country"] = country

        # 4. Salary Normalization (hourly -> annual, etc.)
        s_min, s_max, s_period = normalize_salary(
            job.get("salary_min"),
            job.get("salary_max"),
            job.get("salary_period"),
        )
        job["salary_min"] = s_min
        job["salary_max"] = s_max
        job["salary_period"] = s_period

        # 5. Remote Inference (if not already set)
        if not job["is_remote"] and cleaned_desc:
            if "remote" in cleaned_desc.lower() or "work from home" in cleaned_desc.lower():
                job["is_remote"] = True

        # 6. Enrichment (Silver-only fields)
        job["skills_tags"] = extract_skills(cleaned_desc)
        job["years_experience_min"] = extract_years_experience(cleaned_desc)
        job["seniority"] = classify_seniority(
            job.get("title"), job["years_experience_min"]
        )

        return job

    def transform_batch(self, jobs: List[JobDict]) -> List[JobDict]:
        """Transform a list of jobs."""
        return [self.transform(job) for job in jobs]
