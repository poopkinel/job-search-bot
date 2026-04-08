"""
Yout professional profile.
Used by the LLM matcher to score jobs and generate application answers.
"""

PROFILE = {
    "name": "",
    "email": "",
    "linkedin": "",
    "portfolio": "",
    "location_current": "",
    "location_target": "Berlin, Germany",
    "relocation": True,
    "relocation_note": "Actively relocating to Berlin. Available to start once visa/relocation is arranged.",

    "title": "Software Engineer",
    "tagline": "Python • C#...",
    "summary": (
        "Software engineer with 4+ years of experience..."
    ),
    "years_experience": 4,

    "languages_spoken": {
        "English": "Fluent",
    },
    "german": False,  # Do you know German? — used to filter jobs

    "skills": {
        "languages": ["Python", "C#", "JavaScript", "TypeScript", "SQL", "Bash"],
        "frameworks": ["React", "Docker", "WebGL"],
        "ai": ["OpenAI API", "Claude API", "LLM workflows", "AI-assisted development"],
        "other": ["Git", "CI/CD"],
    },

    "experience": [
        { # Example:
            "title": "Lead Developer",
            "company": "Software Company",
            "period": "2025 - Present",
            "highlights": [
                "Led development of MVP applications for startups, academia, and clients under strict constraints",
                "Delivered production-ready web applications using AI-assisted workflows and open-source technologies",
                "Collaborated directly with stakeholders to define and iterate on product features",
                "Built AI-powered features and integrations",
            ],
        }, # Append professional experience
    ],

    "projects": [
        { # Example:
            "name": "AI-Driven Interactive 3D Systems",
            "description": "Built Unity game environments with LLM-powered agents (speech & text)",
        }, # Append personal / professional projects
    ],

    "education": [
        {
            "institution": "University",
            "program": "Computer Science and Informatics",
        },
    ],

    # Roles you are targeting
    "target_roles": [
        "Software Engineer",
        "Senior Software Engineer",
        "Lead Developer",
        "Full-Stack Engineer",
        "Backend Engineer",
        "AI Engineer",
    ],

    # Industries / company types that are a good fit
    "target_industries": [
        "startup",
        "AI",
        "gaming",
        "VR/AR",
        "edtech",
        "simulation",
        "product",
        "SaaS",
        "deep tech",
    ],
}


def as_cv_text() -> str:
    """Return the profile as a compact text block suitable for LLM context."""
    p = PROFILE
    lines = [
        f"Name: {p['name']}",
        f"Email: {p['email']}",
        f"LinkedIn: {p['linkedin']}",
        f"Portfolio: {p['portfolio']}",
        f"Location: Relocating from {p['location_current']} to {p['location_target']}",
        f"Title: {p['title']}",
        "",
        "Summary:",
        p["summary"],
        "",
        "Skills:",
        f"  Languages: {', '.join(p['skills']['languages'])}",
        f"  Frameworks: {', '.join(p['skills']['frameworks'])}",
        f"  AI: {', '.join(p['skills']['ai'])}",
        f"  Other: {', '.join(p['skills']['other'])}",
        "",
        "Experience:",
    ]
    for exp in p["experience"]:
        lines.append(f"  {exp['title']} @ {exp['company']} ({exp['period']})")
        for h in exp["highlights"]:
            lines.append(f"    - {h}")
    lines += [
        "",
        "Spoken Languages:",
    ]
    for lang, level in p["languages_spoken"].items():
        lines.append(f"  {lang}: {level}")
    lines += [
        "",
        "Education:",
    ]
    for edu in p["education"]:
        lines.append(f"  {edu['institution']} — {edu['program']}")
    return "\n".join(lines)
