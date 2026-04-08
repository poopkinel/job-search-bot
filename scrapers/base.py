"""
Base scraper class. All scrapers extend this.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

from config.preferences import PREFERENCES


@dataclass
class JobListing:
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""


class BaseScraper(ABC):
    source_key: str = ""

    def __init__(self, browser_page):
        self.page = browser_page

    @abstractmethod
    def scrape(self, query: str) -> Iterator[JobListing]:
        """Yield JobListing objects for the given search query."""
        ...

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _passes_filters(self, listing: JobListing) -> bool:
        text = f"{listing.title} {listing.description}".lower()

        # Exclude junior/intern/etc
        for kw in PREFERENCES["exclude_keywords"]:
            if kw.lower() in text:
                return False

        # Exclude known German-required phrases
        for phrase in PREFERENCES["language_keywords_exclude"]:
            if phrase.lower() in text:
                return False

        # Exclude blocked companies
        for co in PREFERENCES["exclude_companies"]:
            if co.lower() in listing.company.lower():
                return False

        return True

    @staticmethod
    def _clean(text: str) -> str:
        """Strip excessive whitespace."""
        return re.sub(r"\s+", " ", text).strip()
