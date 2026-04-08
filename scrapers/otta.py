"""
Welcome to the Jungle scraper — welcometothejungle.com
(Formerly Otta — rebranded 2024)

Startup/growth-stage focused job board. Strong Berlin/Europe coverage.
Free account recommended for full access.
"""

from __future__ import annotations

import time
from typing import Iterator
from urllib.parse import quote

from scrapers.base import BaseScraper, JobListing


class OttaScraper(BaseScraper):
    source_key = "otta"

    def scrape(self, query: str) -> Iterator[JobListing]:
        url = (
            f"https://www.welcometothejungle.com/en/jobs"
            f"?query={quote(query)}&aroundQuery=Berlin%2C+Germany"
        )
        self.page.goto(url, timeout=30_000)
        time.sleep(4)  # React app needs time to render

        for _ in range(4):
            self.page.keyboard.press("End")
            time.sleep(2)

        cards = (
            self.page.query_selector_all("[data-testid='search-results-list-item-wrapper']")
            or self.page.query_selector_all("li[class*='sc-'][class*='job']")
            or self.page.query_selector_all("[class*='JobCard']")
            or self.page.query_selector_all("article[class*='job']")
        )

        if not cards:
            print(f"[wttj] no cards found for '{query}' — may need login or selectors changed")
            return

        print(f"[wttj] found {len(cards)} cards for '{query}'")

        for card in cards:
            try:
                title_el = card.query_selector(
                    "h4, h3, [class*='title'], [data-testid='job-title']"
                )
                company_el = card.query_selector(
                    "[class*='company'], [class*='Company'], "
                    "[data-testid='company-name'], span[class*='sc-']"
                )
                location_el = card.query_selector(
                    "[class*='location'], [class*='Location'], "
                    "[data-testid='job-location']"
                )
                link_el = card.query_selector("a[href*='/en/companies/'], a[href*='/jobs/']")

                if not (title_el and link_el):
                    continue

                href = link_el.get_attribute("href") or ""
                if not href.startswith("http"):
                    href = "https://www.welcometothejungle.com" + href

                location_text = self._clean(location_el.inner_text()) if location_el else ""
                if location_text and not any(
                    kw in location_text.lower()
                    for kw in ("berlin", "germany", "remote", "anywhere", "europe", "worldwide")
                ):
                    continue

                listing = JobListing(
                    source=self.source_key,
                    title=self._clean(title_el.inner_text()),
                    company=self._clean(company_el.inner_text()) if company_el else "Unknown",
                    location=location_text or "Remote/Berlin",
                    url=href.split("?")[0],
                )

                if not self._passes_filters(listing):
                    continue

                description = self._fetch_description(href)
                listing.description = description

                if not self._passes_filters(listing):
                    continue

                yield listing

            except Exception as e:
                print(f"[wttj] card parse error: {e}")
                continue

    def _fetch_description(self, url: str) -> str:
        try:
            self.page.goto(url, timeout=20_000)
            time.sleep(2)
            desc_el = self.page.query_selector(
                "[data-testid='job-section-description'], "
                "[class*='job-description'], "
                "[class*='Description'], "
                "section[id*='description']"
            )
            return self._clean(desc_el.inner_text()) if desc_el else ""
        except Exception as e:
            print(f"[wttj] description fetch error: {e}")
            return ""
