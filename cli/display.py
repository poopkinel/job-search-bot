"""
Rich-based terminal display helpers.
"""

from __future__ import annotations

import sqlite3

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def print_banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]Job Search Bot[/bold cyan]  [dim]by Ophek Ozelle[/dim]",
        border_style="cyan",
    ))


def print_stats(stats: dict) -> None:
    table = Table(title="Application Tracker", box=box.ROUNDED, show_header=True,
                  header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Total jobs discovered", str(stats.get("total", 0)))
    table.add_row("─" * 20, "─" * 8)
    table.add_row("New (unreviewed)", str(stats.get("new", 0)))
    table.add_row("Reviewing", str(stats.get("reviewing", 0)))
    table.add_row("[green]Applied[/green]", str(stats.get("applied", 0)))
    table.add_row("Interviewing", str(stats.get("interviewing", 0)))
    table.add_row("[bold green]Offer[/bold green]", str(stats.get("offer", 0)))
    table.add_row("[dim]Skipped[/dim]", str(stats.get("skipped", 0)))
    table.add_row("[dim]Rejected[/dim]", str(stats.get("rejected", 0)))
    table.add_row("─" * 20, "─" * 8)
    table.add_row("LinkedIn requests sent", str(stats.get("linkedin_sent", 0)))
    table.add_row("LinkedIn requests pending", str(stats.get("linkedin_pending", 0)))

    console.print(table)


def print_jobs_table(jobs: list[sqlite3.Row], title: str = "Matched Jobs") -> None:
    table = Table(title=title, box=box.SIMPLE_HEAD, show_header=True,
                  header_style="bold")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Title", style="bold", width=35)
    table.add_column("Company", width=22)
    table.add_column("Location", width=18)
    table.add_column("Source", style="dim", width=14)
    table.add_column("Status", width=12)

    for job in jobs:
        score = job["match_score"]
        score_str = f"{score:.1f}" if score else "—"
        score_color = (
            "green" if score and score >= 8
            else "yellow" if score and score >= 6
            else "red"
        )
        status = job["status"]
        status_color = {
            "applied": "green",
            "offer": "bold green",
            "interviewing": "cyan",
            "skipped": "dim",
            "rejected": "red",
        }.get(status, "white")

        table.add_row(
            str(job["id"]),
            f"[{score_color}]{score_str}[/{score_color}]",
            job["title"][:34],
            job["company"][:21],
            (job["location"] or "")[:17],
            job["source"],
            f"[{status_color}]{status}[/{status_color}]",
        )

    console.print(table)


def print_job_detail(job: sqlite3.Row) -> None:
    score = job["match_score"]
    score_str = f"{score:.1f}/10" if score else "Not scored"

    console.print(Panel(
        f"[bold]{job['title']}[/bold]  @  [cyan]{job['company']}[/cyan]\n"
        f"[dim]{job['location']} | {job['source']} | Status: {job['status']}[/dim]\n"
        f"[dim]URL:[/dim] [blue]{job['url']}[/blue]\n\n"
        f"[bold]Match score:[/bold] {score_str}\n"
        f"[dim]{job['match_reasoning'] or 'No reasoning yet.'}[/dim]\n\n"
        f"[bold]Description:[/bold]\n{(job['description'] or '')[:600]}{'…' if job['description'] and len(job['description']) > 600 else ''}",
        title=f"Job #{job['id']}",
        border_style="cyan",
    ))


def print_contacts_table(contacts: list[sqlite3.Row]) -> None:
    table = Table(title="LinkedIn Contacts", box=box.SIMPLE_HEAD, show_header=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Name", style="bold", width=25)
    table.add_column("Title", width=28)
    table.add_column("Request", width=10)
    table.add_column("Message", width=10)
    table.add_column("Profile URL", style="blue", width=40)

    for c in contacts:
        req_color = "green" if c["request_status"] == "sent" else "yellow"
        msg_color = "green" if c["message_status"] == "sent" else "dim"
        table.add_row(
            str(c["id"]),
            c["name"][:24],
            c["title"][:27],
            f"[{req_color}]{c['request_status']}[/{req_color}]",
            f"[{msg_color}]{c['message_status']}[/{msg_color}]",
            (c["profile_url"] or "")[:39],
        )
    console.print(table)
