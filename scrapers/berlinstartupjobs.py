"""
Berlin Startup Jobs scraper — berlinstartupjobs.com
Focused purely on Berlin startups. Simpler HTML, easier to parse.

The /engineering/ section is already pre-filtered — no keyword matching needed.
We scrape it once per run (not once per query) to avoid redundant page loads.
"""

from __future__ import annotations

import time
from typing import Iterator

from scrapers.base import BaseScraper, JobListing

BASE_URL = "https://berlinstartupjobs.com/engineering/"


class BerlinStartupJobsScraper(BaseScraper):
    source_key = "berlinstartupjobs"

    def __init__(self, browser_page):
        super().__init__(browser_page)
        self._already_scraped = False  # scrape once per run regardless of query count

    def scrape(self, query: str) -> Iterator[JobListing]:
        # Site has no search — all engineering jobs are on the same pages.
        # Only scrape on the first query call; subsequent calls yield nothing
        # (deduplication happens anyway via DB unique URL constraint, but this
        # avoids 8× redundant HTTP requests per discover run).
        if self._already_scraped:
            return
        self._already_scraped = True

        for page_num in range(1, 6):  # up to 5 pages
            url = BASE_URL if page_num == 1 else f"{BASE_URL}page/{page_num}/"
            try:
                self.page.goto(url, timeout=20_000)
                time.sleep(1.5)
            except Exception as e:
                print(f"[berlinstartupjobs] failed to load {url}: {e}")
                break

            cards = self.page.query_selector_all(".bsj-job, article.job_listing")
            if not cards:
                # Try alternate structure
                cards = self.page.query_selector_all("li.job_listing, .job-listing")
            if not cards:
                break

            for card in cards:
                try:
                    # Try multiple selector patterns — site has changed layout over time
                    title_el = card.query_selector(
                        "h4 a, h3 a, .job-title a, a.job-title, "
                        ".position a, a[href*='berlinstartupjobs.com/']"
                    )
                    company_el = card.query_selector(
                        ".company-name, .bsj-company-name, "
                        ".company a, strong.company, .company"
                    )
                    link_el = title_el or card.query_selector("a[href]")

                    if not link_el:
                        continue

                    href = link_el.get_attribute("href") or ""
                    if not href:
                        continue

                    title = self._clean(title_el.inner_text()) if title_el else ""
                    if not title:
                        # Fall back: grab any visible text from the link
                        title = self._clean(link_el.inner_text())
                    if not title:
                        continue

                    company = self._clean(company_el.inner_text()) if company_el else "Unknown"

                    listing = JobListing(
                        source=self.source_key,
                        title=title,
                        company=company,
                        location="Berlin",
                        url=href,
                    )

                    if not self._passes_filters(listing):
                        continue

                    description = self._fetch_description(href)
                    listing.description = description

                    if not self._passes_filters(listing):
                        continue

                    yield listing

                except Exception as e:
                    print(f"[berlinstartupjobs] card parse error: {e}")
                    continue

    def _fetch_description(self, url: str) -> str:
        try:
            self.page.goto(url, timeout=20_000)
            time.sleep(1.5)
            desc_el = self.page.query_selector(
                ".job-description, .entry-content, article .content, "
                ".job_description, section.description"
            )
            return self._clean(desc_el.inner_text()) if desc_el else ""
        except Exception as e:
            print(f"[berlinstartupjobs] description fetch error: {e}")
            return ""
