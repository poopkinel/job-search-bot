"""
Job Search Bot — main entry point.

Usage:
  python main.py discover              # Scrape all boards, score new jobs
  python main.py review                # Interactively review matched jobs
  python main.py apply <job_id>        # Fill & submit application for a job
  python main.py contacts <job_id>     # Find LinkedIn contacts for a job
  python main.py contacts mark-sent <contact_id>
  python main.py track                 # Show stats + jobs table
  python main.py show <job_id>         # Show full job detail
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Load .env before anything else
try:
    from dotenv import load_dotenv
    current_dir = Path(__file__).parent
    parent_env = current_dir.parent / ".env" / ".env"
    load_dotenv(parent_env)
except ImportError:
    pass

from rich.console import Console
from rich.prompt import Confirm

console = Console()


def _require_env() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY is not set.[/red]")
        console.print("[dim]Copy .env.example to .env and fill in your API key.[/dim]")
        sys.exit(1)


def _get_browser_page(headless: bool = False):
    """
    Launch Playwright with a persistent browser context (keeps sessions alive).

    If PROXY_URL is set in .env (e.g. socks5://user:pass@host:port or http://host:port),
    all traffic is routed through it — useful when scraping from outside Germany.
    """
    from playwright.sync_api import sync_playwright

    profile_dir = os.environ.get("BROWSER_PROFILE_DIR", "./data/browser_profile")
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    proxy_url = os.environ.get("PROXY_URL", "").strip()
    proxy_config = {"server": proxy_url} if proxy_url else None
    if proxy_url:
        console.print(f"[dim]Using proxy: {proxy_url}[/dim]")

    pw = sync_playwright().start()
    kwargs = dict(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    if proxy_config:
        kwargs["proxy"] = proxy_config

    context = pw.chromium.launch_persistent_context(profile_dir, **kwargs)
    page = context.new_page()
    return pw, context, page


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_discover(args: list[str]) -> None:
    """Scrape all configured job boards and score new listings."""
    _require_env()
    from core import db
    from config.preferences import PREFERENCES, SOURCES
    from scrapers.linkedin import LinkedInScraper
    from scrapers.wellfound import WellfoundScraper
    from scrapers.berlinstartupjobs import BerlinStartupJobsScraper
    from scrapers.arbeitnow import ArbeitnowScraper
    from scrapers.greenhouse import GreenhouseScraper
    from scrapers.relocateme import RelocateMeScraper
    from core import matcher
    from cli.display import print_banner, print_jobs_table

    db.init_db()
    print_banner()

    SCRAPER_MAP = {
        "linkedin": LinkedInScraper,
        "wellfound": WellfoundScraper,
        "berlinstartupjobs": BerlinStartupJobsScraper,
        "arbeitnow": ArbeitnowScraper,
        "greenhouse": GreenhouseScraper,
        "relocateme": RelocateMeScraper,
    }

    # Allow filtering sources via CLI: python main.py discover linkedin stepstone
    sources_to_run = args if args else PREFERENCES["sources"]

    pw, context, page = _get_browser_page(headless=False)
    new_total = 0

    try:
        for source_key in sources_to_run:
            if source_key not in SCRAPER_MAP:
                console.print(f"[yellow]Unknown source: {source_key}[/yellow]")
                continue

            source_name = SOURCES.get(source_key, {}).get("name", source_key)
            console.print(f"\n[bold]Scraping {source_name}…[/bold]")

            scraper = SCRAPER_MAP[source_key](page)
            new_for_source = 0

            for query in PREFERENCES["search_queries"]:
                console.print(f"  [dim]Query: {query}[/dim]")
                try:
                    for listing in scraper.scrape(query):
                        job_id = db.upsert_job(
                            source=source_key,
                            title=listing.title,
                            company=listing.company,
                            location=listing.location,
                            url=listing.url,
                            description=listing.description,
                        )
                        if job_id:
                            new_for_source += 1
                            new_total += 1
                            console.print(f"    [green]+[/green] {listing.title} @ {listing.company}")
                except Exception as e:
                    console.print(f"  [red]Scraper error: {e}[/red]")

            console.print(f"  [cyan]{new_for_source} new jobs from {source_name}[/cyan]")

    finally:
        context.close()
        pw.stop()

    console.print(f"\n[bold green]{new_total} new jobs added to DB.[/bold green]")

    # Score unscored jobs
    if new_total > 0:
        console.print("\n[bold]Scoring new jobs with Claude…[/bold]")
        unscored = db.get_unscored_jobs(limit=50)
        for job in unscored:
            try:
                result = matcher.score_job(
                    job_id=job["id"],
                    title=job["title"],
                    company=job["company"],
                    location=job["location"] or "",
                    source=job["source"],
                    description=job["description"] or "",
                )
                db.set_match_score(job["id"], result["match_score"], result["reasoning"])
                score = result["match_score"]
                color = "green" if score >= 8 else "yellow" if score >= 6 else "red"
                console.print(
                    f"  [{color}]{score:.1f}[/{color}]  {job['title']} @ {job['company']}"
                    + (" [dim](german required)[/dim]" if result.get("german_required") else "")
                )
            except Exception as e:
                console.print(f"  [red]Scoring error for job #{job['id']}: {e}[/red]")

    # Show top matches
    from config.preferences import PREFERENCES as P
    top = db.get_jobs(status="new", min_score=P["min_match_score"], limit=20)
    if top:
        print_jobs_table(top, title="Top New Matches")


def cmd_review(args: list[str]) -> None:
    """Interactively review matched jobs one by one."""
    _require_env()
    from core import db
    from cli.display import print_banner, print_job_detail
    from config.preferences import PREFERENCES

    db.init_db()
    print_banner()

    jobs = db.get_jobs(status="new", min_score=PREFERENCES["min_match_score"], limit=50)
    if not jobs:
        console.print("[yellow]No new jobs above the score threshold. Run 'discover' first.[/yellow]")
        return

    console.print(f"[bold]{len(jobs)} jobs to review.[/bold]  [dim](a=apply, s=skip, k=keep for later, q=quit)[/dim]\n")

    for job in jobs:
        print_job_detail(job)
        console.print("[dim]Open in browser? (y/n) [/dim]", end="")
        if input().strip().lower() == "y":
            import webbrowser
            webbrowser.open(job["url"])

        console.print("[dim][a]pply  [s]kip  [k]eep  [q]uit > [/dim]", end="")
        choice = input().strip().lower()

        if choice == "a":
            db.set_job_status(job["id"], "reviewing")
            console.print(f"[green]Marked for application. Run: python main.py apply {job['id']}[/green]")
        elif choice == "s":
            db.set_job_status(job["id"], "skipped")
        elif choice == "k":
            pass  # leave as "new"
        elif choice == "q":
            break


def cmd_apply(args: list[str]) -> None:
    """Fill and submit an application for a specific job."""
    _require_env()
    if not args:
        console.print("[red]Usage: python main.py apply <job_id>[/red]")
        return

    from core import db, applicator
    from cli.display import print_banner, print_job_detail

    db.init_db()
    print_banner()

    job_id = int(args[0])
    job = db.get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found.[/red]")
        return

    print_job_detail(job)

    pw, context, page = _get_browser_page(headless=False)
    try:
        page.goto(job["url"], timeout=30_000)
        time.sleep(2)

        # Check if LinkedIn Easy Apply is available
        easy_apply_btn = page.query_selector("button.jobs-apply-button, [aria-label*='Easy Apply']")

        if easy_apply_btn and "linkedin.com" in job["url"]:
            console.print("[cyan]LinkedIn Easy Apply detected.[/cyan]")
            applicator.apply_linkedin_easy_apply(
                page, job_id=job_id,
                title=job["title"], company=job["company"],
                description=job["description"] or "",
            )
        else:
            console.print("[cyan]Generic application form.[/cyan]")
            # Look for an Apply link/button
            apply_link = page.query_selector(
                "a[href*='apply'], a:has-text('Apply'), button:has-text('Apply Now')"
            )
            apply_url = apply_link.get_attribute("href") if apply_link else job["url"]
            if apply_url and not apply_url.startswith("http"):
                from urllib.parse import urljoin
                apply_url = urljoin(job["url"], apply_url)
            applicator.apply_generic(
                page, job_id=job_id,
                title=job["title"], company=job["company"],
                description=job["description"] or "",
                apply_url=apply_url or job["url"],
            )
    finally:
        context.close()
        pw.stop()


def cmd_contacts(args: list[str]) -> None:
    """Find LinkedIn contacts for a job, or mark contacts as sent."""
    _require_env()
    from core import db, linkedin_helper
    from cli.display import print_banner, print_contacts_table

    db.init_db()
    print_banner()

    if not args:
        console.print("[red]Usage: python main.py contacts <job_id>[/red]")
        console.print("[red]       python main.py contacts mark-sent <contact_id>[/red]")
        console.print("[red]       python main.py contacts mark-msg-sent <contact_id>[/red]")
        return

    if args[0] == "mark-sent":
        linkedin_helper.mark_request_sent(int(args[1]))
        return

    if args[0] == "mark-msg-sent":
        linkedin_helper.mark_message_sent(int(args[1]))
        return

    job_id = int(args[0])
    job = db.get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found.[/red]")
        return

    # Check if we already have contacts for this job
    existing = db.get_contacts_for_job(job_id)
    if existing:
        console.print(f"[dim]Contacts already found for job #{job_id}. Showing existing.[/dim]")
        linkedin_helper.display_contacts(
            [dict(c) for c in existing], job["company"], job["title"]
        )
        print_contacts_table(existing)
        return

    pw, context, page = _get_browser_page(headless=False)
    try:
        contacts = linkedin_helper.find_contacts(
            page, job_id=job_id,
            company=job["company"], job_title=job["title"],
        )
        linkedin_helper.display_contacts(contacts, job["company"], job["title"])
    finally:
        context.close()
        pw.stop()


def cmd_track(args: list[str]) -> None:
    """Show the tracking dashboard.

    track              — stats + applied/reviewing tables
    track all          — every job in the DB, sorted by score
    track <status>     — filter by status (new, applied, skipped, …)
    """
    from core import db
    from cli.display import print_banner, print_stats, print_jobs_table

    db.init_db()
    print_banner()

    stats = db.get_stats()
    print_stats(stats)

    status_filter = args[0] if args else None

    if status_filter == "all":
        # Show every job regardless of score, most recent first
        import sqlite3 as _sqlite3
        from core.db import _conn
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY match_score DESC NULLS LAST, id DESC LIMIT 200"
            ).fetchall()
        print_jobs_table(rows, title=f"All Jobs ({len(rows)})")

    elif status_filter:
        jobs = db.get_jobs(status=status_filter, limit=50)
        print_jobs_table(jobs, title=f"Jobs — {status_filter}")

    else:
        applied = db.get_jobs(status="applied", limit=20)
        if applied:
            print_jobs_table(applied, title="Applied Jobs")
        reviewing = db.get_jobs(status="reviewing", limit=20)
        if reviewing:
            print_jobs_table(reviewing, title="In Review")


def cmd_clear_cookies(args: list[str]) -> None:
    """
    Clear cookies for a specific site without wiping the whole browser profile.
    Useful when a site migration (e.g. Otta → WTTJ) leaves stale auth cookies.

    Usage:
      python main.py clear-cookies otta
      python main.py clear-cookies linkedin
    """
    DOMAINS = {
        "otta":     ["app.otta.com", "otta.com", "welcometothejungle.com"],
        "linkedin": ["linkedin.com", "www.linkedin.com"],
        "wellfound":["wellfound.com", "angel.co"],
    }

    target = args[0] if args else None
    if not target or target not in DOMAINS:
        console.print(f"[red]Usage: python main.py clear-cookies <{'|'.join(DOMAINS)}>[/red]")
        return

    domains = DOMAINS[target]
    pw, context, page = _get_browser_page(headless=True)
    try:
        all_cookies = context.cookies()
        before = len(all_cookies)
        keep = [c for c in all_cookies if not any(d in c["domain"] for d in domains)]
        context.clear_cookies()
        context.add_cookies(keep)
        removed = before - len(keep)
        console.print(f"[green]Cleared {removed} cookies for {', '.join(domains)}.[/green]")
        console.print(f"[dim]Kept {len(keep)} cookies for other sites.[/dim]")
    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass


def cmd_login(args: list[str]) -> None:
    """
    Open the browser to a site so you can log in manually.
    The session is saved to the persistent browser profile for future scraping runs.

    Usage:
      python main.py login linkedin
      python main.py login wellfound
      python main.py login berlinstartupjobs
    """
    URLS = {
        "linkedin":          "https://www.linkedin.com/login",
        "wellfound":         "https://wellfound.com/login",
        "otta":              "https://www.welcometothejungle.com/en/signin",
        "berlinstartupjobs": "https://berlinstartupjobs.com",
        "relocateme":        "https://relocate.me",
    }

    target = args[0] if args else "linkedin"
    url = URLS.get(target, f"https://{target}.com")

    console.print(f"[cyan]Opening {target} — log in, then close the browser window.[/cyan]")
    console.print(f"[dim]Session will be saved to the browser profile for future runs.[/dim]")

    pw, context, page = _get_browser_page(headless=False)
    try:
        page.goto(url, timeout=30_000)
        console.print("[dim]Waiting for you to finish… press Ctrl+C when done.[/dim]")
        # Keep the browser open until user kills the process
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass
    console.print("[green]Session saved.[/green]")


def cmd_rescore(args: list[str]) -> None:
    """
    Re-score jobs with the current scoring prompt.

    rescore            — re-score all jobs (useful after tuning the prompt)
    rescore <job_id>   — re-score a single job
    rescore new        — re-score only jobs still in 'new' status
    """
    _require_env()
    from core import db, matcher
    from cli.display import print_banner, print_jobs_table
    from core.db import _conn

    db.init_db()
    print_banner()

    with _conn() as conn:
        if not args:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT 100"
            ).fetchall()
        elif args[0] == "new":
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' ORDER BY id DESC LIMIT 100"
            ).fetchall()
        else:
            try:
                job_id = int(args[0])
                rows = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchall()
            except ValueError:
                console.print("[red]Usage: python main.py rescore [new|<job_id>][/red]")
                return

    if not rows:
        console.print("[yellow]No jobs to rescore.[/yellow]")
        return

    console.print(f"[bold]Re-scoring {len(rows)} jobs…[/bold]")
    for job in rows:
        try:
            result = matcher.score_job(
                job_id=job["id"],
                title=job["title"],
                company=job["company"],
                location=job["location"] or "",
                source=job["source"],
                description=job["description"] or "",
            )
            db.set_match_score(job["id"], result["match_score"], result["reasoning"])
            score = result["match_score"]
            color = "green" if score >= 8 else "yellow" if score >= 6 else "red"
            flags = ", ".join(result.get("flags", [])) or ""
            console.print(
                f"  [{color}]{score:.1f}[/{color}]  {job['title']} @ {job['company']}"
                + (f"  [dim]{flags}[/dim]" if flags else "")
            )
        except Exception as e:
            console.print(f"  [red]Error on job #{job['id']}: {e}[/red]")

    from config.preferences import PREFERENCES as P
    top = db.get_jobs(min_score=P["min_match_score"], limit=20)
    if top:
        print_jobs_table(top, title=f"Jobs scoring ≥ {P['min_match_score']}")


def cmd_show(args: list[str]) -> None:
    """Show full detail for a specific job."""
    if not args:
        console.print("[red]Usage: python main.py show <job_id>[/red]")
        return
    from core import db
    from cli.display import print_job_detail, print_contacts_table
    db.init_db()
    job = db.get_job(int(args[0]))
    if not job:
        console.print(f"[red]Job #{args[0]} not found.[/red]")
        return
    print_job_detail(job)
    contacts = db.get_contacts_for_job(int(args[0]))
    if contacts:
        print_contacts_table(contacts)


# ── Dispatch ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "discover": cmd_discover,
    "review": cmd_review,
    "apply": cmd_apply,
    "contacts": cmd_contacts,
    "track": cmd_track,
    "show": cmd_show,
    "login": cmd_login,
    "clear-cookies": cmd_clear_cookies,
    "rescore": cmd_rescore,
}

HELP = """
[bold cyan]Job Search Bot[/bold cyan]

Commands:
  [bold]login[/bold] [source]               Log into a site and save the session
  [bold]clear-cookies[/bold] <source>       Clear stale cookies for a site (keeps others)
  [bold]discover[/bold] [source…]           Scrape job boards + score with Claude
  [bold]rescore[/bold] [new|<job_id>]       Re-score jobs with the current prompt
  [bold]review[/bold]                       Interactively review top matches
  [bold]apply[/bold] <job_id>               Fill & submit application (with approval gate)
  [bold]contacts[/bold] <job_id>            Find LinkedIn contacts + generate messages
  [bold]contacts mark-sent[/bold] <id>      Mark connection request as sent
  [bold]contacts mark-msg-sent[/bold] <id>  Mark follow-up message as sent
  [bold]track[/bold] [all|status]           Show stats & job table
  [bold]show[/bold] <job_id>                Show full job detail

Sources: linkedin  wellfound  berlinstartupjobs  arbeitnow  greenhouse  relocateme

Recommended first-run sequence:
  1. python main.py login linkedin     ← log in once, session persists
  2. python main.py login wellfound
  3. python main.py discover
  4. python main.py track all          ← see everything, diagnose scoring
  5. python main.py rescore            ← re-score if you tuned the prompt
  6. python main.py review
"""


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        console.print(HELP)
        return

    cmd = argv[0]
    rest = argv[1:]

    if cmd not in COMMANDS:
        console.print(f"[red]Unknown command: {cmd}[/red]")
        console.print(HELP)
        sys.exit(1)

    COMMANDS[cmd](rest)


if __name__ == "__main__":
    main()
