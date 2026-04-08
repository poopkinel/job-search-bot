"""
LinkedIn contact finder — zero-risk mode.

Does NOT send any requests automatically.
Finds relevant people at the company, generates personalised connection messages,
and presents them for you to send manually.

Prioritises: Engineering Managers, CTOs, Hiring Managers, Tech Leads, Recruiters.
"""

from __future__ import annotations

import time
from urllib.parse import quote

from rich.console import Console
from rich.table import Table

from core import db, matcher

console = Console()

# Roles most likely to lead to a response
TARGET_TITLES = [
    "CTO",
    "VP Engineering",
    "Head of Engineering",
    "Engineering Manager",
    "Tech Lead",
    "Lead Engineer",
    "Senior Engineer",
    "Software Engineer",
    "Recruiter",
    "Technical Recruiter",
    "Talent Acquisition",
    "Hiring Manager",
]


def find_contacts(page, job_id: int, company: str, job_title: str,
                  max_contacts: int = 5) -> list[dict]:
    """
    Search LinkedIn People for employees at `company` with relevant titles.
    Returns a list of contact dicts. Saves them to the DB.
    Does NOT send any connection requests.
    """
    contacts = []

    for title_kw in TARGET_TITLES[:4]:   # search top 4 role types
        results = _search_linkedin_people(page, company, title_kw)
        for r in results[:2]:            # up to 2 per role type
            if len(contacts) >= max_contacts:
                break
            # Generate connection message via LLM
            message = matcher.generate_linkedin_message(
                contact_name=r["name"],
                contact_title=r["title"],
                company=company,
                job_title=job_title,
            )
            r["connection_message"] = message

            contact_id = db.save_contact(
                job_id=job_id,
                name=r["name"],
                profile_url=r["profile_url"],
                title=r["title"],
                connection_message=message,
            )
            r["id"] = contact_id
            contacts.append(r)

        if len(contacts) >= max_contacts:
            break

    return contacts


def _search_linkedin_people(page, company: str, title_kw: str) -> list[dict]:
    """
    Search LinkedIn for people matching company + title.
    Returns list of {name, title, profile_url}.
    """
    results = []
    query = f"{company} {title_kw}"
    url = f"https://www.linkedin.com/search/results/people/?keywords={quote(query)}&origin=GLOBAL_SEARCH_HEADER"

    try:
        page.goto(url, timeout=20_000)
        time.sleep(2)

        cards = page.query_selector_all(
            ".reusable-search__result-container, .entity-result__item"
        )

        for card in cards[:3]:
            name_el = card.query_selector(
                ".entity-result__title-text span[aria-hidden='true'], "
                ".actor-name, .entity-result__title-line span"
            )
            title_el = card.query_selector(
                ".entity-result__primary-subtitle, .subline-level-1"
            )
            link_el = card.query_selector(
                "a.app-aware-link[href*='/in/'], a[href*='linkedin.com/in/']"
            )

            if not (name_el and link_el):
                continue

            name = name_el.inner_text().strip()
            title = title_el.inner_text().strip() if title_el else ""
            href = link_el.get_attribute("href") or ""
            # Clean tracking params
            profile_url = href.split("?")[0]

            if name and profile_url:
                results.append({
                    "name": name,
                    "title": title,
                    "profile_url": profile_url,
                })
    except Exception:
        pass

    return results


def display_contacts(contacts: list[dict], company: str, job_title: str) -> None:
    """Print the contact list with pre-written messages for manual sending."""
    console.print(f"\n[bold cyan]─── LinkedIn Contacts @ {company} ───[/bold cyan]")
    console.print(f"[dim]Applied for: {job_title}[/dim]\n")

    if not contacts:
        console.print("[yellow]No contacts found. Try searching manually.[/yellow]")
        return

    for i, c in enumerate(contacts, 1):
        console.print(f"[bold]{i}. {c['name']}[/bold]  [dim]{c['title']}[/dim]")
        console.print(f"   [blue]{c['profile_url']}[/blue]")
        console.print(f"   [green]Message:[/green] {c.get('connection_message', '')}")
        console.print()

    console.print("[dim]──────────────────────────────────────────────[/dim]")
    console.print("[dim]Send requests manually. Mark as sent with:[/dim]")
    console.print("[dim]  python main.py contacts mark-sent <contact_id>[/dim]\n")


def mark_request_sent(contact_id: int) -> None:
    db.set_contact_request_status(contact_id, "sent")
    console.print(f"[green]Contact #{contact_id} marked as request sent.[/green]")


def mark_message_sent(contact_id: int) -> None:
    db.set_contact_message_status(contact_id, "sent")
    console.print(f"[green]Contact #{contact_id} marked as message sent.[/green]")
