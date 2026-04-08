"""
Application engine.

Flow:
  1. Open the job URL in the browser
  2. Detect form fields (labels, types, options)
  3. Call LLM to fill all fields
  4. Present the filled form to the user for review/edit
  5. On approval — submit. On reject — abort.
  6. Record the application in the DB.

Works best with LinkedIn Easy Apply; has best-effort support for other portals.
"""

from __future__ import annotations

import json
import time
from typing import Any

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from core import db, matcher

console = Console()


# ── Field detection ───────────────────────────────────────────────────────────

def _detect_fields(page) -> list[dict]:
    """
    Introspect the current page for input fields.
    Returns a list of {name, label, type, options, selector} dicts.
    """
    fields = []

    # Standard inputs
    inputs = page.query_selector_all(
        "input:not([type=hidden]):not([type=submit]):not([type=button]),"
        "textarea, select"
    )
    for el in inputs:
        tag = el.evaluate("el => el.tagName.toLowerCase()")
        field_type = el.get_attribute("type") or tag
        name = (
            el.get_attribute("name")
            or el.get_attribute("id")
            or el.get_attribute("aria-label")
            or ""
        )
        if not name:
            continue

        # Find associated label text
        label = ""
        el_id = el.get_attribute("id")
        if el_id:
            label_el = page.query_selector(f"label[for='{el_id}']")
            if label_el:
                label = label_el.inner_text().strip()
        if not label:
            label = el.get_attribute("placeholder") or el.get_attribute("aria-label") or name

        options = []
        if field_type == "select" or tag == "select":
            opts = el.query_selector_all("option")
            options = [o.inner_text().strip() for o in opts if o.inner_text().strip()]

        fields.append({
            "name": name,
            "label": label,
            "type": field_type,
            "options": options if options else None,
            "selector": f"[name='{name}']" if el.get_attribute("name") else f"#{el_id}" if el_id else None,
        })

    return fields


# ── LinkedIn Easy Apply ───────────────────────────────────────────────────────

def apply_linkedin_easy_apply(page, job_id: int, title: str, company: str,
                               description: str) -> bool:
    """
    Handle LinkedIn Easy Apply multi-step modal.
    Returns True if successfully submitted.
    """
    # Click the Easy Apply button
    btn = page.query_selector("button.jobs-apply-button, [aria-label*='Easy Apply']")
    if not btn:
        console.print("[yellow]No Easy Apply button found on this page.[/yellow]")
        return False

    btn.click()
    time.sleep(1.5)

    step = 0
    while True:
        step += 1
        console.print(f"[dim]Easy Apply — step {step}[/dim]")

        fields = _detect_fields(page)
        if not fields:
            # Likely a review/confirmation step
            pass
        else:
            filled = matcher.fill_form_fields(fields, title, company, description)
            if not _review_and_edit_fields(fields, filled):
                console.print("[red]Application cancelled by user.[/red]")
                # Close the modal
                close = page.query_selector("button[aria-label='Dismiss'], button[aria-label='Cancel']")
                if close:
                    close.click()
                return False
            _fill_page_fields(page, fields, filled)

        # Next / Review / Submit
        next_btn = page.query_selector(
            "button[aria-label='Continue to next step'], "
            "button[aria-label='Review your application'], "
            "footer button[aria-label*='Next']"
        )
        submit_btn = page.query_selector(
            "button[aria-label='Submit application'], "
            "button[aria-label*='Submit']"
        )

        if submit_btn:
            if _confirm_submit(title, company):
                submit_btn.click()
                time.sleep(2)
                db.mark_applied(job_id)
                db.save_application(job_id, filled if fields else {})
                console.print(f"[green]Applied to {title} @ {company}![/green]")
                return True
            else:
                console.print("[red]Application cancelled at final review.[/red]")
                return False

        if next_btn:
            next_btn.click()
            time.sleep(1.5)
            continue

        console.print("[yellow]Could not find Next or Submit button. Manual intervention needed.[/yellow]")
        return False


def apply_generic(page, job_id: int, title: str, company: str,
                  description: str, apply_url: str) -> bool:
    """
    Best-effort application on an arbitrary company career page.
    Detects fields, fills them, shows review, then submits if approved.
    """
    page.goto(apply_url, timeout=30_000)
    time.sleep(2)

    fields = _detect_fields(page)
    if not fields:
        console.print("[yellow]No form fields detected. You may need to apply manually.[/yellow]")
        return False

    filled = matcher.fill_form_fields(fields, title, company, description)

    if not _review_and_edit_fields(fields, filled):
        console.print("[red]Application cancelled.[/red]")
        return False

    _fill_page_fields(page, fields, filled)

    if not _confirm_submit(title, company):
        return False

    # Find and click submit
    submit = page.query_selector(
        "button[type=submit], input[type=submit], button:has-text('Apply'), button:has-text('Submit')"
    )
    if submit:
        submit.click()
        time.sleep(2)
        db.mark_applied(job_id)
        db.save_application(job_id, filled)
        console.print(f"[green]Applied to {title} @ {company}![/green]")
        return True
    else:
        console.print("[yellow]Could not find submit button. Check the browser and submit manually.[/yellow]")
        return False


# ── Field filling ─────────────────────────────────────────────────────────────

def _fill_page_fields(page, fields: list[dict], filled: dict[str, str]) -> None:
    for field in fields:
        name = field["name"]
        value = filled.get(name, "")
        if not value or not field.get("selector"):
            continue
        try:
            el = page.query_selector(field["selector"])
            if not el:
                continue
            if field["type"] in ("select",):
                el.select_option(value=value)
            elif field["type"] in ("checkbox", "radio"):
                if str(value).lower() in ("true", "yes", "1"):
                    el.check()
            else:
                el.fill(str(value))
        except Exception:
            pass


# ── User approval UIs ─────────────────────────────────────────────────────────

def _review_and_edit_fields(fields: list[dict], filled: dict[str, str]) -> bool:
    """
    Show filled fields to the user. They can edit values or cancel.
    Returns True to proceed, False to cancel.
    """
    console.print("\n[bold cyan]─── Form fields to fill ───[/bold cyan]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Field", style="bold")
    table.add_column("Type", style="dim")
    table.add_column("Value (LLM-generated)", style="green")

    for i, field in enumerate(fields):
        value = filled.get(field["name"], "")
        table.add_row(str(i + 1), field["label"], field["type"], str(value)[:80])

    console.print(table)
    console.print()
    console.print("[dim]Enter field number to edit, [bold]s[/bold] to submit as-is, [bold]c[/bold] to cancel:[/dim]")

    while True:
        raw = input("  > ").strip().lower()
        if raw == "s":
            return True
        if raw == "c":
            return False
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(fields):
                field = fields[idx]
                if field.get("options"):
                    console.print(f"  Options: {', '.join(field['options'])}")
                new_val = input(f"  New value for '{field['label']}': ").strip()
                filled[field["name"]] = new_val
                console.print(f"  [green]Updated.[/green]")
        except ValueError:
            console.print("  [red]Invalid input.[/red]")


def _confirm_submit(title: str, company: str) -> bool:
    console.print(f"\n[bold yellow]Ready to submit application:[/bold yellow]")
    console.print(f"  Role:    {title}")
    console.print(f"  Company: {company}")
    raw = input("\n  Type 'yes' to submit, anything else to cancel: ").strip().lower()
    return raw == "yes"
