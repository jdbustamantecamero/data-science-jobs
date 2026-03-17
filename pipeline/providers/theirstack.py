"""TheirStack job source provider."""
from __future__ import annotations

import logging
from typing import Any, List

import httpx

from pipeline.config import THEIRSTACK_API_KEY, THEIRSTACK_BASE_URL
from pipeline.models import JobDict
from pipeline.providers.base import BaseJobSource

logger = logging.getLogger(__name__)


class TheirStackProvider(BaseJobSource):
    def __init__(self) -> None:
        super().__init__(name="TheirStack")
        self.page_size = 25

    def fetch_jobs(
        self,
        query: str = "Data Scientist",
        max_pages: int = 5,
        **kwargs: Any,
    ) -> List[JobDict]:
        country_code = kwargs.get("country_code", "CA")
        jobs: List[JobDict] = []
        headers = {
            "Authorization": f"Bearer {THEIRSTACK_API_KEY}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=30) as client:
            for page in range(0, max_pages):
                payload = {
                    "page": page,
                    "limit": self.page_size,
                    "order_by": [{"desc": True, "field": "date_posted"}],
                    "job_title_or": [query],
                    "job_country_code_or": [country_code],
                    "posted_at_max_age_days": 15,
                }
                logger.info("Fetching %s page %d for '%s'", self.name, page, query)
                resp = client.post(
                    f"{THEIRSTACK_BASE_URL}/jobs/search",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                raw_results = data.get("data", [])
                
                if not raw_results:
                    logger.info("No more results on page %d for %s.", page, self.name)
                    break

                for raw in raw_results:
                    jobs.append(self._map_to_job_dict(raw))
                
                logger.info("%s page %d: %d jobs fetched", self.name, page, len(raw_results))
                
                # Check if we've received all available results
                total = data.get("total", 0)
                if len(jobs) >= total:
                    break

        return jobs

    def _map_to_job_dict(self, raw: dict[str, Any]) -> JobDict:
        return {
            "job_id": f"theirstack_{raw['id']}",
            
            # Bronze fields
            "title_raw": raw.get("job_title"),
            "company_name_raw": raw.get("company_name"),
            "company_domain_raw": raw.get("company_url"),
            "location_city_raw": raw.get("city"),
            "location_state_raw": raw.get("state"),
            "location_country_raw": raw.get("country"),
            "is_remote_raw": raw.get("remote"),
            "employment_type_raw": raw.get("employment_type"),
            "salary_min_raw": raw.get("salary_min"),
            "salary_max_raw": raw.get("salary_max"),
            "salary_currency_raw": raw.get("salary_currency"),
            "salary_period_raw": raw.get("salary_period"),
            "job_description_raw": raw.get("description"),
            "job_apply_link_raw": raw.get("url"),
            "employer_logo_raw": raw.get("company_logo"),
            "posted_at_raw": raw.get("date_posted"),
        }
