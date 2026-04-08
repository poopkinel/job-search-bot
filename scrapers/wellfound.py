"""
Wellfound (formerly AngelList Talent) scraper.
Best source for Berlin startups. Requires a free account.
"""

from __future__ import annotations

import time
from typing import Iterator
from urllib.parse import quote

from scrapers.base import BaseScraper, JobListing


class WellfoundScraper(BaseScraper):
    source_key = "wellfound"

    def scrape(self, query: str) -> Iterator[JobListing]:
        # Wellfound uses React — we need to render with Playwright
        url = (
            f"https://wellfound.com/jobs"
            f"?q={quote(query)}"
            f"&locations[]=Berlin"
            f"&remote=true"
        )
        self.page.goto(url, timeout=30_000)
        time.sleep(3)

        for _ in range(4):
            self.page.keyboard.press("End")
            time.sleep(2)

        cards = self.page.query_selector_all(
            "[data-test='JobListing'], .styles_component__UCLp1, [class*='JobListing']"
        )

        for card in cards:
            try:
                title_el = card.query_selector(
                    "[data-test='job-title'], h2, .styles_title__xpQDw"
                )
                company_el = card.query_selector(
                    "[data-test='company-name'], .styles_company__AvJGN, a[href*='/company/']"
                )
                location_el = card.query_selector(
                    "[data-test='location'], .styles_location__"
                )
                link_el = card.query_selector("a[href*='/jobs/']")

                if not (title_el and company_el and link_el):
                    continue

                href = link_el.get_attribute("href") or ""
                if not href.startswith("http"):
                    href = "https://wellfound.com" + href

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
            time.sleep(2)
            desc_el = self.page.query_selector(
                "[data-test='job-description'], .styles_description__"
            )
            return self._clean(desc_el.inner_text()) if desc_el else ""
        except Exception:
            return ""
