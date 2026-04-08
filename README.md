# job-search-bot
Automated job hunting for Berlin's tech market

A personal job search automation tool that scrapes LinkedIn, Wellfound, Berlin Startup Jobs, Greenhouse, and Arbeitnow daily, scores each listing against my CV using Claude AI, and surfaces the best matches. Fills out application forms with LLM-generated answers (with a human approval gate before submitting), finds relevant LinkedIn contacts at target companies, and generates personalised connection messages for manual outreach. Tracks applications, contact status, and pipeline stage in a local SQLite database with a Rich terminal UI.

**Stack:** Python · Playwright · Anthropic Claude API · SQLite · Rich

---

## Setup

```bash
# 1. Clone and create virtualenv
git clone https://github.com/poopkinel/job-search-bot.git
cd job-search-bot
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies + Playwright browser
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and optionally SLACK_WEBHOOK_URL
```

Edit `config/profile.py` with your CV details and `config/preferences.py` to set your target roles, seniority, and any companies to exclude.

---

## Usage

### First-time login (saves session to browser profile)
```bash
python main.py login linkedin
python main.py login wellfound
```

### Discover & score jobs
```bash
python main.py discover                      # all sources
python main.py discover arbeitnow greenhouse # API-only (no browser needed)
```

### Review matches
```bash
python main.py review        # step through top matches, mark for apply/skip
python main.py track all     # see everything in the DB with scores
python main.py show 42       # full detail for job #42
```

### Apply
```bash
python main.py apply 42      # LLM fills the form — you review and approve before submit
```

### LinkedIn outreach (zero-risk — manual send)
```bash
python main.py contacts 42                  # find contacts at the company + generate messages
python main.py contacts mark-sent 7         # mark connection request as sent
python main.py contacts mark-msg-sent 7     # mark follow-up message as sent
```

### Re-score & maintenance
```bash
python main.py rescore           # re-score all jobs (useful after editing your profile)
python main.py rescore 42        # re-score a single job
python main.py clear-cookies otta  # clear stale cookies for a site
```

### Track pipeline
```bash
python main.py track             # stats + applied/reviewing tables
python main.py track applied     # filter by status
```
