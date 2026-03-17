"""Adzuna job source provider."""
from __future__ import annotations

import logging
from typing import Any, List, Tuple

import httpx

from pipeline.config import ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_BASE_URL
from pipeline.models import JobDict
from pipeline.providers.base import BaseJobSource

logger = logging.getLogger(__name__)


class AdzunaProvider(BaseJobSource):
    def __init__(self) -> None:
        super().__init__(name="Adzuna")
        self.results_per_page = 50

    def fetch_jobs(
        self,
        query: str = "Data Scientist",
        max_pages: int = 5,
        **kwargs: Any,
    ) -> List[JobDict]:
        country = kwargs.get("country", "ca")
        jobs: List[JobDict] = []

        with httpx.Client(timeout=30) as client:
            for page in range(1, max_pages + 1):
                params = {
                    "app_id": ADZUNA_APP_ID,
                    "app_key": ADZUNA_APP_KEY,
                    "results_per_page": str(self.results_per_page),
                    "what": query,
                    "where": "Canada",
                    "sort_by": "date",
                    "max_days_old": "15",
                }
                url = f"{ADZUNA_BASE_URL}/{country}/search/{page}"
                logger.info("Fetching %s page %d for '%s'", self.name, page, query)
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                raw_results = data.get("results", [])
                
                if not raw_results:
                    logger.info("No more results on page %d for %s.", page, self.name)
                    break

                for raw in raw_results:
                    jobs.append(self._map_to_job_dict(raw))
                
                logger.info("%s page %d: %d jobs fetched", self.name, page, len(raw_results))

        return jobs

    def _parse_location(self, area: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract (city, province, country) from Adzuna's area array."""
        country = area[0] if len(area) > 0 else "Canada"
        province = area[1] if len(area) > 1 else None
        city = area[-1] if len(area) > 2 else None
        return city, province, country

    def _map_to_job_dict(self, raw: dict[str, Any]) -> JobDict:
        area = raw.get("location", {}).get("area", [])
        city, province, country = self._parse_location(area)
        
        return {
            "job_id": f"adzuna_{raw['id']}",
            
            # Bronze fields
            "title_raw": raw.get("title"),
            "company_name_raw": raw.get("company", {}).get("display_name"),
            "company_domain_raw": None,  # Adzuna doesn't provide this
            "location_city_raw": city,
            "location_state_raw": province,
            "location_country_raw": country,
            "is_remote_raw": None,  # Will be inferred in Silver layer
            "employment_type_raw": raw.get("contract_time"),
            "salary_min_raw": raw.get("salary_min"),
            "salary_max_raw": raw.get("salary_max"),
            "salary_currency_raw": "CAD",
            "salary_period_raw": "YEAR",
            "job_description_raw": raw.get("description"),
            "job_apply_link_raw": raw.get("redirect_url"),
            "employer_logo_raw": None,
            "posted_at_raw": raw.get("created"),
        }
