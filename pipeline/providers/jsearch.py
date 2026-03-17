"""JSearch (RapidAPI) job source provider."""
from __future__ import annotations

import logging
from typing import Any, List

import httpx

from pipeline.config import JSEARCH_API_KEY, JSEARCH_BASE_URL, JSEARCH_HOST
from pipeline.models import JobDict
from pipeline.providers.base import BaseJobSource

logger = logging.getLogger(__name__)


class JSearchProvider(BaseJobSource):
    def __init__(self) -> None:
        super().__init__(name="JSearch")
        self.headers = {
            "X-RapidAPI-Key": JSEARCH_API_KEY,
            "X-RapidAPI-Host": JSEARCH_HOST,
        }

    def fetch_jobs(
        self,
        query: str = "Data Scientist",
        max_pages: int = 10,
        **kwargs: Any,
    ) -> List[JobDict]:
        country = kwargs.get("country", "ca")
        jobs: List[JobDict] = []
        last_resp = None

        with httpx.Client(timeout=30) as client:
            for page in range(1, max_pages + 1):
                params = {
                    "query": query,
                    "page": str(page),
                    "num_pages": "1",
                    "country": country,
                    "date_posted": "month",
                }
                logger.info("Fetching %s page %d for '%s'", self.name, page, query)
                resp = client.get(
                    f"{JSEARCH_BASE_URL}/search",
                    headers=self.headers,
                    params=params,
                )
                resp.raise_for_status()
                last_resp = resp
                data = resp.json()
                raw_results = data.get("data", [])

                if not raw_results:
                    logger.info("No more results on page %d for %s.", page, self.name)
                    break

                for raw in raw_results:
                    jobs.append(self._map_to_job_dict(raw))

                logger.info("%s page %d: %d jobs fetched", self.name, page, len(raw_results))

        if last_resp is not None:
            self._log_credits(last_resp.headers)

        return jobs

    def _log_credits(self, headers: Any) -> None:
        try:
            remaining = int(headers.get("x-ratelimit-requests-remaining", -1))
            limit = int(headers.get("x-ratelimit-requests-limit", -1))
            if remaining >= 0:
                pct = round(remaining / limit * 100) if limit > 0 else "?"
                level = "WARNING" if remaining < 40 else "INFO"
                logger.log(
                    logging.WARNING if remaining < 40 else logging.INFO,
                    "%s credits: %d / %d remaining (%s%%)",
                    self.name, remaining, limit, pct,
                )
        except (ValueError, TypeError):
            pass

    def _map_to_job_dict(self, raw: dict[str, Any]) -> JobDict:
        """Map raw API response to Bronze (_raw) fields."""
        return {
            "job_id": raw["job_id"],  # JSearch IDs are unique strings
            
            # Bronze fields
            "title_raw": raw.get("job_title"),
            "company_name_raw": raw.get("employer_name"),
            "company_domain_raw": raw.get("employer_website") or raw.get("job_apply_link"),
            "location_city_raw": raw.get("job_city"),
            "location_state_raw": raw.get("job_state"),
            "location_country_raw": raw.get("job_country"),
            "is_remote_raw": raw.get("job_is_remote"),
            "employment_type_raw": raw.get("job_employment_type"),
            "salary_min_raw": raw.get("job_min_salary"),
            "salary_max_raw": raw.get("job_max_salary"),
            "salary_currency_raw": raw.get("job_salary_currency"),
            "salary_period_raw": raw.get("job_salary_period"),
            "job_description_raw": raw.get("job_description"),
            "job_apply_link_raw": raw.get("job_apply_link"),
            "employer_logo_raw": raw.get("employer_logo"),
            "posted_at_raw": raw.get("job_posted_at_datetime_utc"),
        }
