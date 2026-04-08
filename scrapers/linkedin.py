"""
LinkedIn Jobs scraper.

Uses Playwright with your logged-in session (persistent browser profile).
LinkedIn has two DOM variants — logged-in and logged-out — with different class names.
We try both sets of selectors so the scraper survives session issues.

NOTE: Run `python main.py login linkedin` once to save your session.
"""

from __future__ import annotations

import time
from typing import Iterator
from urllib.parse import urlencode

from scrapers.base import BaseScraper, JobListing


class LinkedInScraper(BaseScraper):
    source_key = "linkedin"

    BASE_URL = "https://www.linkedin.com/jobs/search/"

    def scrape(self, query: str) -> Iterator[JobListing]:
        params = urlencode({
            "keywords": query,
            "location": "Berlin, Germany",
            "f_WT": "1,2,3",       # on-site, remote, hybrid
            "sortBy": "DD",        # most recent
            "start": "0",
        })
        url = f"{self.BASE_URL}?{params}"
        self.page.goto(url, timeout=30_000)
        time.sleep(3)

        # Scroll to trigger lazy-loading
        for _ in range(4):
            self.page.keyboard.press("End")
            time.sleep(1.5)

        # LinkedIn uses different class names for logged-in vs logged-out sessions
        # and changes them frequently — try several in order
        cards = (
            self.page.query_selector_all(".scaffold-layout__list-item")
            or self.page.query_selector_all(".jobs-search-results__list-item")
            or self.page.query_selector_all(".job-card-container--clickable")
            or self.page.query_selector_all(".jobs-search__results-list li")
            or self.page.query_selector_all("li[class*='jobs-search']")
        )

        if not cards:
            print(f"[linkedin] no cards found for query '{query}' — are you logged in?")
            return

        print(f"[linkedin] found {len(cards)} cards for '{query}'")

        for card in cards:
            try:
                title_el = self._find(card, [
                    ".job-card-list__title--link",
                    ".job-card-container__link span[aria-hidden='true']",
                    ".artdeco-entity-lockup__title span",
                    ".base-search-card__title",
                    "h3 a", "h3",
                ])
                company_el = self._find(card, [
                    ".job-card-container__company-name",
                    ".artdeco-entity-lockup__subtitle span",
                    ".base-search-card__subtitle",
                    "h4 a", "h4",
                ])
                location_el = self._find(card, [
                    ".job-card-container__metadata-item",
                    ".artdeco-entity-lockup__caption span",
                    ".job-search-card__location",
                ])
                link_el = self._find(card, [
                    "a.job-card-container__link",
                    "a.job-card-list__title--link",
                    "a[href*='/jobs/view/']",
                    "a[href*='linkedin.com/jobs']",
                ])

                if not link_el:
                    continue

                href = link_el.get_attribute("href") or ""
                job_url = href.split("?")[0] if href else ""
                if not job_url:
                    continue

                title = self._clean(title_el.inner_text()) if title_el else ""
                if not title:
                    title = self._clean(link_el.inner_text())
                if not title:
                    continue

                company = self._clean(company_el.inner_text()) if company_el else "Unknown"
                location = self._clean(location_el.inner_text()) if location_el else "Berlin"

                listing = JobListing(
                    source=self.source_key,
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                )

                if not self._passes_filters(listing):
                    continue

                description = self._fetch_description(job_url)
                listing.description = description

                if not self._passes_filters(listing):
                    continue

                yield listing

            except Exception as e:
                print(f"[linkedin] card parse error: {e}")
                continue

    def _fetch_description(self, url: str) -> str:
        try:
            self.page.goto(url, timeout=20_000)
            time.sleep(1.5)
            # Expand truncated description if present
            for btn_sel in [
                "button.show-more-less-html__button--more",
                "button[aria-label*='more']",
                ".jobs-description__content button",
            ]:
                btn = self.page.query_selector(btn_sel)
                if btn:
                    btn.click()
                    time.sleep(0.5)
                    break
            desc_el = self._find(self.page, [
                ".jobs-description__content .show-more-less-html__markup",
                ".jobs-description-content__text",
                ".description__text",
                ".jobs-description",
            ])
            return self._clean(desc_el.inner_text()) if desc_el else ""
        except Exception as e:
            print(f"[linkedin] description fetch error: {e}")
            return ""

    @staticmethod
    def _find(parent, selectors: list[str]):
        """Try selectors in order, return first match."""
        for sel in selectors:
            try:
                el = parent.query_selector(sel)
                if el:
                    return el
            except Exception:
                continue
        return None
