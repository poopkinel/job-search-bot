"""
LLM-based job matcher.

For each job, sends the description + Ophek's profile to Claude and gets back:
  - match_score (0–10)
  - reasoning (1–2 sentences)
  - recommended_action (apply | skip | maybe)
"""

from __future__ import annotations

import json
import os

import anthropic

from config.profile import as_cv_text
from config.preferences import PREFERENCES

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


SYSTEM_PROMPT = """\
You are a job matching assistant helping a software engineer find relevant jobs.
Use the scoring rubric below. Return ONLY a JSON object, no other text.
"""

USER_TEMPLATE = """\
## Candidate Profile
{cv}

## Job Listing
Title: {title}
Company: {company}
Location: {location}
Source: {source}

Description:
{description}

## Scoring Rubric
Score 0–10 using these anchors:

9–10  Near-perfect fit: strong skill overlap, right seniority, English-ok, Berlin/remote-DE
7–8   Good fit: most skills match, minor gaps, would likely get an interview
5–6   Partial fit: relevant background but missing 1-2 key requirements
3–4   Weak fit: adjacent domain, significant skill gaps
0–2   Poor fit: wrong domain, requires German, very junior/very senior

Key facts about the candidate:
- Strong Python + AI/LLM experience — weight this heavily for AI/backend/ML roles
- 4+ years, has led teams and client projects — qualifies for senior/lead roles
- Unity/C# background — direct match for game dev, simulation, XR roles
- Relocation to Berlin is CONFIRMED and in progress — do NOT penalize for it
- English-only is fine for Berlin's international tech scene — only flag if German is explicitly required

Return a JSON object with these exact keys:
{{
  "match_score": <float 0-10>,
  "reasoning": "<1-2 sentences explaining the score>",
  "recommended_action": "<apply|maybe|skip>",
  "german_required": <true|false>,
  "flags": ["<any actual concerns, e.g. 'requires German C1', 'needs 8+ years', etc.>"]
}}
"""


def score_job(job_id: int, title: str, company: str, location: str,
              source: str, description: str) -> dict:
    """
    Call Claude to score a job. Returns parsed dict with match_score, reasoning, etc.
    Raises on API error.
    """
    cv = as_cv_text()
    prompt = USER_TEMPLATE.format(
        cv=cv,
        title=title,
        company=company,
        location=location,
        source=source,
        description=description[:4000],  # stay well within token budget
    )

    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw)
    result["job_id"] = job_id
    return result


def generate_cover_letter(title: str, company: str, description: str,
                          extra_notes: str = "") -> str:
    """Generate a short, personalised cover letter / intro paragraph."""
    cv = as_cv_text()
    prompt = f"""\
Write a concise, professional cover letter opening (3–4 paragraphs) for:
Role: {title}
Company: {company}

Job description (excerpt):
{description[:3000]}

Candidate profile:
{cv}

Additional notes from candidate: {extra_notes or 'None'}

Guidelines:
- Do not use generic filler phrases
- Mention 1-2 specific, relevant achievements from the candidate's background
- Keep it under 250 words
- Mention that the candidate is relocating to Berlin
- End with a clear call to action
"""
    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def fill_form_fields(form_fields: list[dict], title: str, company: str,
                     description: str) -> dict[str, str]:
    """
    Given a list of form field descriptors, ask Claude to fill them in.

    form_fields: [{"name": "field_name", "label": "...", "type": "text|textarea|select",
                   "options": [...] or None}]
    Returns: {field_name: value_to_fill}
    """
    cv = as_cv_text()
    fields_json = json.dumps(form_fields, indent=2)
    prompt = f"""\
You are filling out a job application form on behalf of a candidate.

## Candidate Profile
{cv}

## Job
Title: {title}
Company: {company}
Description (excerpt): {description[:2000]}

## Form Fields
{fields_json}

Fill in each field appropriately based on the candidate profile.
For "select" fields, choose from the provided options.
For "textarea" fields, write 2–4 sentences.
For salary/expected_salary fields, use "65000-85000" or similar EUR range unless the candidate specified otherwise.

Return ONLY a JSON object mapping field names to filled values.
No extra text, no markdown fences.
"""
    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def generate_linkedin_message(contact_name: str, contact_title: str,
                              company: str, job_title: str) -> str:
    """Generate a short LinkedIn connection request note (300 chars max)."""
    prompt = f"""\
Write a LinkedIn connection request note from Ophek Ozelle to {contact_name} ({contact_title} at {company}).
Context: Ophek just applied for the {job_title} role there.
Keep it under 280 characters. Be genuine, not salesy. No emojis.
Just the message text, nothing else.
"""
    client = _get_client()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
