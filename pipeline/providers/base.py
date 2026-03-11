"""Base class and common utilities for all job source providers."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional
from urllib.parse import urlparse

from pipeline.models import JobDict

logger = logging.getLogger(__name__)


class BaseJobSource(ABC):
    """Abstract base class for all job providers (JSearch, Adzuna, etc.)."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def fetch_jobs(
        self,
        query: str = "Data Scientist",
        max_pages: int = 5,
        **kwargs: Any,
    ) -> List[JobDict]:
        """Fetch and return a list of jobs in the standardized JobDict format.

        This method MUST populate the _raw fields in the JobDict.
        Cleaning and normalization of Silver fields will happen in the transformer.
        """
        pass

    def _normalize_domain(self, url: Optional[str]) -> Optional[str]:
        """Standard domain extraction utility used across providers."""
        if not url:
            return None
        try:
            url_str = str(url)
            parsed = urlparse(url_str if url_str.startswith("http") else f"https://{url_str}")
            netloc = parsed.netloc or parsed.path
            domain = netloc.replace("www.", "").lower().strip("/")
            return domain or None
        except Exception:
            return None
