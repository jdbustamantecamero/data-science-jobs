"""
Job record transformer (Bronze -> Silver Layer).

This module contains the 'JobTransformer' class, which is responsible for 
the transition of job records from their raw state (Bronze) to a cleaned, 
standardized, and enriched state (Silver).
"""
from __future__ import annotations

import logging
from typing import List

from pipeline.data_cleaner import (
    classify_seniority,
    clean_description,
    convert_relative_timestamp,
    extract_years_experience,
    infer_location_from_description,
    infer_province_from_city,
    normalize_city,
    normalize_country,
    normalize_employment_type,
    normalize_province,
    normalize_salary,
)
from pipeline.models import JobDict
from pipeline.skills_parser import extract_skills

logger = logging.getLogger(__name__)


class JobTransformer:
    """
    Orchestrates the cleaning and enrichment of job records.
    
    This class takes raw Bronze records (populated by API providers) and applies
    all normalization rules defined in data_cleaner.py and skills_parser.py.
    """

    def transform(self, job: JobDict) -> JobDict:
        """
        Transform a single raw job record into a cleaned Silver record.
        
        This method is the canonical location for defining the flow of 
        data from raw API fields (_raw) to their cleaned counterparts.
        """
        # 1. Initialize Silver fields from Bronze (raw snapshots)
        # We start by copying the raw API values into our working Silver fields.
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
        
        # Handle timestamp conversion: SerpAPI returns relative timestamps like "1 day ago"
        # which must be converted to absolute ISO 8601 timestamps before database insert
        posted_at_raw = job.get("posted_at_raw")
        if posted_at_raw and isinstance(posted_at_raw, str) and "ago" in posted_at_raw.lower():
            # SerpAPI relative timestamp - convert to ISO 8601
            job["posted_at"] = convert_relative_timestamp(posted_at_raw)
        else:
            # Other providers (JSearch, Adzuna, TheirStack) provide ISO timestamps or None
            job["posted_at"] = posted_at_raw

        # 2. Description Cleaning
        # Strip HTML and normalize whitespace immediately so downstream 
        # parsers (skills, experience) work with clean text.
        cleaned_desc = clean_description(job.get("job_description"))
        job["job_description"] = cleaned_desc

        # 3. Location Normalization
        # Apply Canadian-specific location normalization rules.
        city = normalize_city(job.get("location_city"))
        province = normalize_province(job.get("location_state"))
        country = normalize_country(job.get("location_country"))

        # Heuristic: Infer missing province from a known city (e.g., 'Toronto' -> 'Ontario').
        if not province and city:
            province = infer_province_from_city(city)

        # Heuristic: If still missing city/province, scan the description for patterns.
        if not city or not province:
            desc_city, desc_province = infer_location_from_description(cleaned_desc)
            city = city or desc_city
            province = province or desc_province
            
        job["location_city"] = city
        job["location_state"] = province
        job["location_country"] = country

        # 4. Employment Type Normalization
        # Standardize employment types across all API sources (FULL_TIME -> Full-time, etc.)
        job["employment_type"] = normalize_employment_type(job.get("employment_type"))

        # 5. Salary Normalization
        # Standardize pay into annual CAD figures.
        s_min, s_max, s_period = normalize_salary(
            job.get("salary_min"),
            job.get("salary_max"),
            job.get("salary_period"),
        )
        job["salary_min"] = s_min
        job["salary_max"] = s_max
        job["salary_period"] = s_period

        # 6. Remote Inference
        # If the API didn't flag the job as remote, check the text for 'remote/WFH'.
        if not job["is_remote"] and cleaned_desc:
            desc_lower = cleaned_desc.lower()
            if "remote" in desc_lower or "work from home" in desc_lower:
                job["is_remote"] = True

        # 7. Pipeline Enrichment (Silver-only derived fields)
        # These fields are entirely computed by the pipeline logic.
        job["skills_tags"] = extract_skills(cleaned_desc)
        job["years_experience_min"] = extract_years_experience(cleaned_desc)
        job["seniority"] = classify_seniority(
            job.get("title"), job["years_experience_min"]
        )

        return job

    def transform_batch(self, jobs: List[JobDict]) -> List[JobDict]:
        """
        Helper to transform multiple records in a batch.
        """
        return [self.transform(job) for job in jobs]
