"""
Arbeitnow scraper — arbeitnow.com public API
https://www.arbeitnow.com/api/job-board-api

Free, no auth, Germany-focused, includes English-language filter.
API-based: no Playwright needed, no bot detection issues.
"""

from __future__ import annotations

from typing import Iterator

import requests

from scrapers.base import BaseScraper, JobListing

API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowScraper(BaseScraper):
    source_key = "arbeitnow"

    def scrape(self, query: str) -> Iterator[JobListing]:
        for page_num in range(1, 5):  # up to 4 pages (~100 results)
            try:
                resp = requests.get(
                    API_URL,
                    params={"search": query, "page": page_num},
                    timeout=15,
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[arbeitnow] API error (page {page_num}): {e}")
                break

            jobs = data.get("data", [])
            if not jobs:
                break

            for job in jobs:
                location = job.get("location", "")
                remote = job.get("remote", False)

                # Keep Berlin jobs and remote jobs
                is_berlin = "berlin" in location.lower()
                is_germany = "germany" in location.lower() or "deutschland" in location.lower()
                if not (is_berlin or is_germany or remote):
                    continue

                url = job.get("url", "") or f"https://www.arbeitnow.com/jobs/{job.get('slug', '')}"

                listing = JobListing(
                    source=self.source_key,
                    title=job.get("title", ""),
                    company=job.get("company_name", "Unknown"),
                    location=location or ("Remote" if remote else "Germany"),
                    url=url,
                    description=self._clean(job.get("description", "")),
                )

                if not listing.title or not listing.url:
                    continue

                if not self._passes_filters(listing):
                    continue

                yield listing

            # API returns fewer than expected → last page
            if len(jobs) < 25:
                break
