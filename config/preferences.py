"""
Job search preferences and filters.
"""

PREFERENCES = {
    # ── Location ──────────────────────────────────────────────────────────────
    "locations": ["Berlin", "Germany"],
    "remote_ok": True,           # Remote-within-Germany is fine
    "on_site_ok": True,          # On-site Berlin is fine
    "relocation_from": "",       # City / Country to relocate from

    # ── Language ──────────────────────────────────────────────────────────────
    "require_german": False,     # To filter OUT jobs that require German
    "language_keywords_exclude": [
        "Deutsch erforderlich",
        "German required",
        "German is a must",
        "C1 German",
        "B2 German",
        "native German",
        "Deutschkenntnisse",
        "Deutschkenntnisse erforderlich",
        "fließend Deutsch",
        "Sprachkenntnisse Deutsch",
    ],

    # ── Job boards to scrape ──────────────────────────────────────────────────
    # Keys must match scraper module names
    "sources": [
        "linkedin",
        "wellfound",
        "berlinstartupjobs",
        "arbeitnow",
        "greenhouse",
        "relocateme",
    ],

    # ── Matching thresholds ───────────────────────────────────────────────────
    "min_match_score": 6.0,       # 0–10: only surface jobs above this score
    "top_k_per_run": 20,          # How many new matches to present per run

    # ── Search keywords ───────────────────────────────────────────────────────
    # Used as query terms on each job board
    "search_queries": [
        "software engineer",
        "python developer",
        "AI engineer",
        "full stack engineer",
        "lead developer",
        "backend engineer",
        "product engineer",
    ],

    # ── Seniority (specify your seniority) ───────────────────────────────────
    "seniority": ["mid", "senior", "lead", "principal", "staff"],

    # ── Salary (EUR, optional — leave None to skip filter) ───────────────────
    "min_salary_eur": None,

    # ── Exclude ───────────────────────────────────────────────────────────────
    "exclude_companies": [],      # Add company names to never apply to
    "exclude_keywords": [
        "intern",
        "internship",
        "student",
        "junior",
        "werkstudent",
        "praktikum",
        "praktikant",
    ],
}


# ── Job board URLs ─────────────────────────────────────────────────────────────

SOURCES = {
    "linkedin": {
        "name": "LinkedIn Jobs",
        "base_search_url": "https://www.linkedin.com/jobs/search/",
        "params": {
            "keywords": "{query}",
            "location": "Berlin, Germany",
            "f_WT": "1,2,3",   # on-site, remote, hybrid
        },
    },
    "stepstone": {
        "name": "StepStone",
        "base_search_url": "https://www.stepstone.de/en/jobs/",
        "params": {
            "q": "{query}",
            "loc": "Berlin",
        },
    },
    "wellfound": {
        "name": "Wellfound (AngelList)",
        "base_search_url": "https://wellfound.com/jobs",
        "params": {
            "q": "{query}",
            "locations[]": "Berlin",
            "remote": "true",
        },
    },
    "berlinstartupjobs": {
        "name": "Berlin Startup Jobs",
        "base_search_url": "https://berlinstartupjobs.com/engineering/",
        "params": {},
    },
    "arbeitnow": {
        "name": "Arbeitnow",
        "base_search_url": "https://www.arbeitnow.com/api/job-board-api",
        "params": {"search": "{query}"},
    },
    "greenhouse": {
        "name": "Greenhouse (Berlin companies)",
        "base_search_url": "https://boards-api.greenhouse.io/v1/boards/",
        "params": {},
    },
    "relocateme": {
        "name": "Relocate.me",
        "base_search_url": "https://relocate.me/search",
        "params": {
            "query": "{query}",
            "location": "Germany",
        },
    },
}
