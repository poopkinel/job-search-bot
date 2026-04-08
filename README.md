# job-search-bot
Automated job hunting for Berlin's tech market

A personal job search automation tool that scrapes LinkedIn, Wellfound, Berlin Startup Jobs, Greenhouse, and Arbeitnow daily, scores each listing against my CV using Claude AI, and surfaces the best matches. Fills out application forms with LLM-generated answers (with a human approval gate before submitting), finds relevant LinkedIn contacts at target companies, and generates personalised connection messages for manual outreach. Tracks applications, contact status, and pipeline stage in a local SQLite database with a Rich terminal UI.

Stack: Python · Playwright · Anthropic Claude API · SQLite · Rich
