"""
StepStone scraper (English-language search).
StepStone is Germany's largest job board and has an English UI at stepstone.de/en/
"""

from __future__ import annotations

import time
from typing import Iterator
from urllib.parse import quote

from scrapers.base import BaseScraper, JobListing


class StepStoneScraper(BaseScraper):
    source_key = "stepstone"

    def scrape(self, query: str) -> Iterator[JobListing]:
        url = f"https://www.stepstone.de/en/jobs/{quote(query)}/in-berlin/?radius=30&sort=2"
        self.page.goto(url, timeout=30_000)
        time.sleep(2)

        for _ in range(3):
            self.page.keyboard.press("End")
            time.sleep(1.5)

        cards = self.page.query_selector_all("article[data-at='job-item']")

        for card in cards:
            try:
                title_el = card.query_selector("[data-at='job-item-title']")
                company_el = card.query_selector("[data-at='job-item-company-name']")
                location_el = card.query_selector("[data-at='job-item-location']")
                link_el = card.query_selector("a[data-at='job-item-title']")

                if not (title_el and company_el and link_el):
                    continue

                href = link_el.get_attribute("href") or ""
                if not href.startswith("http"):
                    href = "https://www.stepstone.de" + href

                listing = JobListing(
                    source=self.source_key,
                    title=self._clean(title_el.inner_text()),
                    company=self._clean(company_el.inner_text()),
                    location=self._clean(location_el.inner_text()) if location_el else "Berlin",
                    url=href.split("?")[0],
                )

                if not self._passes_filters(listing):
                    continue

                description = self._fetch_description(href)
                listing.description = description

                if not self._passes_filters(listing):
                    continue

                yield listing

            except Exception:
                continue

    def _fetch_description(self, url: str) -> str:
        try:
            self.page.goto(url, timeout=20_000)
            time.sleep(1.5)
            desc_el = self.page.query_selector(
                ".job-ad-display__content, [data-at='job-ad-description']"
            )
            return self._clean(desc_el.inner_text()) if desc_el else ""
        except Exception:
            return ""
