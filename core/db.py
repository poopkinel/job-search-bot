"""
SQLite database layer.

Tables:
  jobs               — every discovered job listing
  applications       — submitted applications (form data, timestamp)
  linkedin_contacts  — people found at the company, for manual outreach
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,          -- linkedin | stepstone | wellfound | …
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    location         TEXT,
    url              TEXT UNIQUE NOT NULL,
    description      TEXT,
    match_score      REAL,                   -- 0–10 from LLM
    match_reasoning  TEXT,
    status           TEXT DEFAULT 'new',     -- new | reviewing | applied | skipped | interviewing | offer | rejected
    applied_at       TEXT,                   -- ISO-8601
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS applications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES jobs(id),
    form_data     TEXT,                      -- JSON: {field_name: filled_value}
    submitted_at  TEXT DEFAULT (datetime('now')),
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS linkedin_contacts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id             INTEGER NOT NULL REFERENCES jobs(id),
    name               TEXT NOT NULL,
    profile_url        TEXT,
    title              TEXT,
    connection_message TEXT,
    request_status     TEXT DEFAULT 'pending',    -- pending | sent
    message_status     TEXT DEFAULT 'not_sent',   -- not_sent | sent
    created_at         TEXT DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Jobs ──────────────────────────────────────────────────────────────────────

def upsert_job(source: str, title: str, company: str, location: str,
               url: str, description: str = "") -> int | None:
    """Insert a job. Returns new row id, or None if already exists."""
    with _conn() as conn:
        cur = conn.execute(
            "SELECT id FROM jobs WHERE url = ?", (url,)
        )
        row = cur.fetchone()
        if row:
            return None
        cur = conn.execute(
            """INSERT INTO jobs (source, title, company, location, url, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, title, company, location, url, description),
        )
        return cur.lastrowid


def set_match_score(job_id: int, score: float, reasoning: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET match_score=?, match_reasoning=? WHERE id=?",
            (score, reasoning, job_id),
        )


def set_job_status(job_id: int, status: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status=? WHERE id=?", (status, job_id)
        )


def mark_applied(job_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='applied', applied_at=datetime('now') WHERE id=?",
            (job_id,),
        )


def get_job(job_id: int) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()


def get_jobs(status: str | None = None, min_score: float = 0.0,
             limit: int = 100) -> list[sqlite3.Row]:
    with _conn() as conn:
        if status:
            return conn.execute(
                "SELECT * FROM jobs WHERE status=? AND (match_score IS NULL OR match_score>=?) "
                "ORDER BY match_score DESC LIMIT ?",
                (status, min_score, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM jobs WHERE match_score>=? ORDER BY match_score DESC LIMIT ?",
            (min_score, limit),
        ).fetchall()


def get_unscored_jobs(limit: int = 50) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE match_score IS NULL AND status='new' LIMIT ?",
            (limit,),
        ).fetchall()


# ── Applications ──────────────────────────────────────────────────────────────

def save_application(job_id: int, form_data: dict, notes: str = "") -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO applications (job_id, form_data, notes) VALUES (?, ?, ?)",
            (job_id, json.dumps(form_data), notes),
        )
        return cur.lastrowid


# ── LinkedIn contacts ─────────────────────────────────────────────────────────

def save_contact(job_id: int, name: str, profile_url: str, title: str,
                 connection_message: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO linkedin_contacts
               (job_id, name, profile_url, title, connection_message)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, name, profile_url, title, connection_message),
        )
        return cur.lastrowid


def set_contact_request_status(contact_id: int, status: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE linkedin_contacts SET request_status=? WHERE id=?",
            (status, contact_id),
        )


def set_contact_message_status(contact_id: int, status: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE linkedin_contacts SET message_status=? WHERE id=?",
            (status, contact_id),
        )


def get_contacts_for_job(job_id: int) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM linkedin_contacts WHERE job_id=?", (job_id,)
        ).fetchall()


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with _conn() as conn:
        stats = {}
        for status in ("new", "reviewing", "applied", "skipped",
                       "interviewing", "offer", "rejected"):
            row = conn.execute(
                "SELECT COUNT(*) as n FROM jobs WHERE status=?", (status,)
            ).fetchone()
            stats[status] = row["n"]
        stats["total"] = sum(stats.values())

        row = conn.execute(
            "SELECT COUNT(*) as n FROM linkedin_contacts WHERE request_status='sent'"
        ).fetchone()
        stats["linkedin_sent"] = row["n"]

        row = conn.execute(
            "SELECT COUNT(*) as n FROM linkedin_contacts WHERE request_status='pending'"
        ).fetchone()
        stats["linkedin_pending"] = row["n"]

        return stats
