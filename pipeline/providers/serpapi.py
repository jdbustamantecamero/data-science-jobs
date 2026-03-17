"""SerpAPI Google Jobs source provider."""
from __future__ import annotations

import logging
import re
from typing import Any, List, Optional, Tuple

import httpx

from pipeline.config import SERPAPI_API_KEY, SERPAPI_BASE_URL, SERPAPI_ACCOUNT_URL
from pipeline.models import JobDict
from pipeline.providers.base import BaseJobSource

logger = logging.getLogger(__name__)


class SerpAPIProvider(BaseJobSource):
    def __init__(self) -> None:
        super().__init__(name="SerpAPI")
        self.amount_re = re.compile(r"(?:CA\$|C\$|\$|CAD\s*)?([\d,]+(?:\.\d+)?)\s*([Kk])?")

    def fetch_jobs(
        self,
        query: str = "Data Scientist",
        max_pages: int = 5,
        **kwargs: Any,
    ) -> List[JobDict]:
        location = kwargs.get("location", "Canada")
        jobs: List[JobDict] = []
        next_page_token: Optional[str] = None

        with httpx.Client(timeout=30) as client:
            for page in range(max_pages):
                params: dict[str, Any] = {
                    "engine": "google_jobs",
                    "q": query,
                    "location": location,
                    "hl": "en",
                    "api_key": SERPAPI_API_KEY,
                }
                if next_page_token:
                    params["next_page_token"] = next_page_token

                logger.info("Fetching %s page %d for '%s'", self.name, page, query)
                resp = client.get(SERPAPI_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                raw_results: List[dict] = data.get("jobs_results", [])
                if not raw_results:
                    logger.info("No more results on page %d for %s.", page, self.name)
                    break

                for raw in raw_results:
                    jobs.append(self._map_to_job_dict(raw))
                
                logger.info("%s page %d: %d jobs fetched", self.name, page, len(raw_results))

                next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")
                if not next_page_token:
                    break

        self._log_credits()
        return jobs

    def _log_credits(self) -> None:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(SERPAPI_ACCOUNT_URL, params={"api_key": SERPAPI_API_KEY})
                resp.raise_for_status()
                data = resp.json()
            remaining = data.get("plan_searches_left")
            used = data.get("this_month_usage")
            plan = data.get("plan_name", "unknown")
            if remaining is not None:
                logger.log(
                    logging.WARNING if remaining < 50 else logging.INFO,
                    "%s credits: %s remaining this month (used %s) — plan: %s",
                    self.name, remaining, used, plan,
                )
        except Exception as exc:
            logger.warning("%s: could not fetch credit info — %s", self.name, exc)

    def _parse_location(self, location_str: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if not location_str:
            return None, None, None
        parts = [p.strip() for p in location_str.split(",")]
        if len(parts) >= 3:
            return parts[0], parts[-2], parts[-1]
        if len(parts) == 2:
            return None, parts[0], parts[1]
        return None, None, parts[0]

    def _parse_amount(self, text: str) -> Optional[float]:
        m = self.amount_re.search(text)
        if not m:
            return None
        try:
            val = float(m.group(1).replace(",", ""))
            if m.group(2): val *= 1000
            return val
        except ValueError:
            return None

    def _map_to_job_dict(self, raw: dict[str, Any]) -> JobDict:
        detected = raw.get("detected_extensions") or {}
        city, province, country = self._parse_location(raw.get("location"))
        
        salary_str = detected.get("salary")
        salary_min, salary_max = None, None
        if salary_str:
            range_parts = re.split(r"\s*[–\-]\s*|\s+to\s+", salary_str, maxsplit=1)
            salary_min = self._parse_amount(range_parts[0])
            if len(range_parts) > 1:
                salary_max = self._parse_amount(range_parts[1])

        apply_options = raw.get("apply_options") or []
        apply_link = apply_options[0].get("link") if apply_options else None

        return {
            "job_id": f"serpapi_{raw['job_id']}",
            
            # Bronze fields
            "title_raw": raw.get("title"),
            "company_name_raw": raw.get("company_name"),
            "company_domain_raw": None,
            "location_city_raw": city,
            "location_state_raw": province,
            "location_country_raw": country,
            "is_remote_raw": detected.get("work_from_home"),
            "employment_type_raw": detected.get("schedule_type"),
            "salary_min_raw": salary_min,
            "salary_max_raw": salary_max,
            "salary_currency_raw": "CAD",
            "salary_period_raw": None, # Will be parsed from string in Silver
            "job_description_raw": raw.get("description"),
            "job_apply_link_raw": apply_link,
            "employer_logo_raw": raw.get("thumbnail"),
            "posted_at_raw": detected.get("posted_at"),
        }
