"""
Greenhouse job board scraper.
https://boards-api.greenhouse.io/v1/boards/{token}/jobs

Many Berlin startups use Greenhouse as their ATS.
Their board API is public — no auth, no Playwright, no bot detection.

Add or remove companies from BERLIN_COMPANIES below as needed.
The board token is usually the company slug visible in their job URL:
  https://boards.greenhouse.io/babbel → token is "babbel"
"""

from __future__ import annotations

from typing import Iterator

import requests

from scrapers.base import BaseScraper, JobListing

API_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"

# Berlin companies known to use Greenhouse — extend freely
BERLIN_COMPANIES: dict[str, str] = {
    "babbel":           "Babbel",
    "getyourguide":     "GetYourGuide",
    "personio":         "Personio",
    "contentful":       "Contentful",
    "ecosia":           "Ecosia",
    "pitchdotcom":      "Pitch",
    "commercetools":    "commercetools",
    "clark-germany":    "Clark",
    "forto":            "Forto",
    "billie":           "Billie",
    "rasa":             "Rasa",
    "moonfare":         "Moonfare",
    "signavio":         "Signavio (SAP)",
    "solaris":          "Solaris",
    "tier":             "TIER Mobility",
    "helsing":          "Helsing",
    "taxfix":           "Taxfix",
    "wefox":            "wefox",
    "thermondo":        "Thermondo",
    "n26":              "N26",
}


class GreenhouseScraper(BaseScraper):
    source_key = "greenhouse"

    def scrape(self, query: str) -> Iterator[JobListing]:
        query_words = query.lower().split()

        for token, company_name in BERLIN_COMPANIES.items():
            try:
                resp = requests.get(
                    API_BASE.format(token=token),
                    timeout=15,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 404:
                    # Company no longer uses Greenhouse or token changed
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[greenhouse] {company_name}: {e}")
                continue

            for job in data.get("jobs", []):
                title = job.get("title", "")
                if not title:
                    continue

                # Keyword filter against query
                title_lower = title.lower()
                content = job.get("content", "") or ""
                searchable = f"{title_lower} {content.lower()}"
                if not any(w in searchable for w in query_words):
                    continue

                # Location filter — keep Berlin, remote, or unspecified
                offices = job.get("offices", [])
                location = ", ".join(o.get("name", "") for o in offices) if offices else ""
                if location and not any(
                    kw in location.lower()
                    for kw in ("berlin", "germany", "remote", "anywhere")
                ):
                    continue

                url = job.get("absolute_url", "")
                if not url:
                    continue

                description = self._clean(
                    # Greenhouse returns HTML in content; strip tags roughly
                    content.replace("<br>", "\n").replace("<p>", "\n")
                )
                # Strip remaining HTML tags
                import re
                description = re.sub(r"<[^>]+>", " ", description)
                description = self._clean(description)

                listing = JobListing(
                    source=self.source_key,
                    title=title,
                    company=company_name,
                    location=location or "Berlin",
                    url=url,
                    description=description,
                )

                if not self._passes_filters(listing):
                    continue

                yield listing
