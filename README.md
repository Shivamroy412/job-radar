# job-radar 🛰️

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![deps](https://img.shields.io/badge/dependencies-minimal-brightgreen)
![cost](https://img.shields.io/badge/cost-%240-brightgreen)

A lightweight, **local-first** job-posting monitor. It checks many job sources
on a schedule, keeps only postings that match your keywords and location,
remembers what it has already seen, and pings you on **Telegram** when something
*new* shows up — most relevant first.

Free to run ($0), config-driven, and easy to point at any search — jobs at a
company's own careers page (via its ATS), a whole-market keyword sweep, or both.

**Watches:** Greenhouse · Lever · Ashby · Personio · Workday · Arbeitsagentur
(Germany) · Indeed · Google Jobs · LinkedIn · Amazon — all via official public
feeds or [JobSpy](https://pypi.org/project/python-jobspy/), no paid APIs.

---

## Table of contents

1. [What it watches](#what-it-watches)
2. [How it works](#how-it-works)
3. [Install](#install)
4. [Telegram bot setup](#telegram-bot-setup)
5. [First run & avoiding a flood](#first-run--avoiding-a-flood)
6. [Run it automatically](#run-it-automatically-hourly)
7. [Windows](#windows)
8. [Profiles (multiple searches)](#profiles-multiple-searches)
9. [Configuration reference](#configuration-reference)
10. [Adding more companies & sources](#adding-more-companies--sources)
11. [Tuning & FAQ](#tuning--faq)
12. [Project layout](#project-layout)

---

## What it watches

| Source | How | Reliability |
|---|---|---|
| Company career pages (Greenhouse, Lever, Ashby, Personio, **Workday**) | Official public feeds — no scraping, no keys | High |
| **Arbeitsagentur** (Germany's largest job DB) | Free official REST API — keyword + radius | High |
| Amazon | Native public search API (off by default) | High |
| Indeed + Google Jobs | [JobSpy](https://pypi.org/project/python-jobspy/) | Medium |
| LinkedIn | JobSpy (rate-limits hard, may break) | Low–Med |

Full breakdown — including what's *missing* and what we could add — in
[`docs/SOURCES.md`](docs/SOURCES.md).

**Company list vs general search:** the ATS/Workday feeds pull *every* role from
the companies you list; Indeed, Google Jobs, LinkedIn and Arbeitsagentur are
*general* searches that also find roles at companies **not** on your list.

## How it works

One `run.py` pass does: **fetch → filter (keywords + location) → rank by
relevance → drop already-seen (dedupe) → notify**. State lives in a local SQLite
file so you're never pinged twice. Each source is isolated — one failing only
logs a warning, the run continues.

## Install

Requires Python 3.10+ (macOS, Linux, or Windows — see the
[Windows section](#windows) for PowerShell commands).

```bash
cd job-radar
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp config.example.yaml config.yaml   # your personal search; stays local (gitignored)
```

Edit `config.yaml` to describe your own search (keywords, location, companies).
It's gitignored, so it never leaves your machine and `git pull` won't overwrite
it. If you skip this step, the tool falls back to `config.example.yaml`.

Verify it works (prints matches, sends nothing):

```bash
./.venv/bin/python run.py --dry-run
```

## Telegram bot setup

You need two values: a **bot token** and your **chat ID**. Both free, ~2 minutes,
done in the Telegram app.

**Get the bot TOKEN**
1. Open a chat with **@BotFather** (blue checkmark).
2. Send `/newbot`. Give it a name (e.g. `Job Radar`) and a username ending in
   `bot` (e.g. `myname_jobradar_bot`).
3. BotFather replies with a token like `8123456789:AAH1a2B3c4...` — copy it.

**Get your CHAT ID**
1. **Message your new bot** anything (it can't message you until you do).
2. Open **@userinfobot** and send `/start`. It replies with `Id: 123456789` —
   that's your chat ID.

**Save them** (never committed — `.env` is gitignored):

```bash
cp -n .env.example .env && open -e .env
```

Fill in and save:

```
TELEGRAM_BOT_TOKEN=8123456789:AAH1a2B3c4...
TELEGRAM_CHAT_ID=123456789
```

## First run & avoiding a flood

The very first real run would treat *everything* as new. Two ways to keep it
sane:

- **Seed a baseline (recommended)** — mark everything currently open as "seen"
  silently, so you only get postings that appear *after* now:

  ```bash
  ./.venv/bin/python run.py --seed
  ```

- **Or just run it** — `max_per_run` (default 40) caps how many are sent each
  run; the rest trickle in on later runs.

Then do a normal run (sends to Telegram):

```bash
./.venv/bin/python run.py
```

## Run it automatically (hourly)

```bash
bash scripts/install_launchd.sh          # hourly
bash scripts/install_launchd.sh 1800     # or every 30 min (seconds)
```

Runs immediately, then on that interval while your Mac is awake (a missed run
fires on wake). Logs: `data/jobradar.log`.

```bash
tail -f data/jobradar.log                                          # watch
launchctl unload ~/Library/LaunchAgents/com.jobradar.agent.plist  # stop
```

### Or run it in the cloud (GitHub Actions) — 24/7, no machine needed

A ready-made workflow lives at
[`.github/workflows/schedule.yml`](.github/workflows/schedule.yml). In short:
make the repo **public** (free private repos can't run scheduled Actions), add
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` under *Settings → Secrets and
variables → Actions*, optionally set a `CONFIG_PATH` variable to pick which
committed search runs (e.g. `profiles/payments.yaml`), and it runs hourly on
GitHub's runners. The "seen" state is cached between runs so you aren't
re-alerted.

Full step-by-step — including **forking it to run on someone else's account**
with their own alerts — is in [`docs/RUN_ON_GITHUB.md`](docs/RUN_ON_GITHUB.md).

## Windows

Everything works on Windows; only the macOS `launchd` auto-scheduler differs
(use Task Scheduler instead, below). In **PowerShell**:

```powershell
# One-time: install Python + Git if you don't have them, then reopen PowerShell
winget install -e --id Python.Python.3.12 ; winget install -e --id Git.Git

git clone https://github.com/Shivamroy412/job-radar.git
cd job-radar
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
notepad .env          # fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, save
```

Seed a silent baseline once (sends nothing), then do real runs. Point `--config`
at the search you want (omit it to use `config.yaml` → `config.example.yaml`):

```powershell
.venv\Scripts\python run.py --config profiles/payments.yaml --seed
.venv\Scripts\python run.py --config profiles/payments.yaml
```

### Run it automatically on Windows (hourly — Task Scheduler)

Run this **from inside the `job-radar` folder** in PowerShell. It schedules the
included [`scripts\run.bat`](scripts/run.bat) (which self-locates, runs one pass,
and appends to `data\jobradar.log`) every hour:

```powershell
$bat = Join-Path (Get-Location) "scripts\run.bat"
schtasks /Create /SC HOURLY /TN "job-radar" /TR "`"$bat`" --config profiles/payments.yaml" /F
```

Manage it:

```powershell
schtasks /Run    /TN "job-radar"        # run once now
schtasks /Delete /TN "job-radar" /F     # remove the schedule
Get-Content data\jobradar.log -Wait     # watch the log (Ctrl+C to stop)
```

Unlike macOS `launchd`, Task Scheduler needs the PC awake *and* can be set to
wake it or catch up on missed runs via *Task Scheduler (GUI) → job-radar →
Properties → Conditions/Settings*. For true 24/7 with the machine off, use the
[cloud route](#or-run-it-in-the-cloud-github-actions--247-no-machine-needed).

## Profiles (multiple searches)

Each search is a YAML file. The active one is `config.yaml` (what the scheduler
runs). Ready-made profiles are in [`profiles/`](profiles/):

| Profile | For |
|---|---|
| `profiles/payments.yaml` | Payment Operations / Finance (Munich) — **active** |
| `profiles/ml.yaml` | ML / AI Engineer (Munich) |

Run a profile ad-hoc without changing the active one:

```bash
./.venv/bin/python run.py --config profiles/ml.yaml --dry-run
```

Make one the scheduled default:

```bash
cp profiles/ml.yaml config.yaml
```

Each profile has its own `db_path`, so their "seen" histories don't mix.

## Configuration reference

Key fields in a config/profile file:

```yaml
db_path: data/seen-payments.db   # where "seen" state is stored
max_per_run: 40                  # cap alerts per run (0 = unlimited)
min_score: 0                     # drop matches below this relevance (0 = off)
dedupe_cross_source: true        # collapse the same role seen on 2 sites

keywords:
  include: [payment, reconciliation, ...]    # title must contain ANY (also DE terms)
  exclude: [intern, working student, ...]     # title + snippet must contain NONE
  exclude_title: [engineer, developer, ...]   # TITLE must contain NONE (kills false positives)
  title_only: true                            # match include in title only

locations: [munich, germany, berlin, europe] # a posting's location must match one
remote_ok: true                              # ...or be remote

# Or, for a "home base, but open to remote/hybrid elsewhere in the EU" search,
# use home_locations INSTEAD of locations:
#   home_locations: [munich, münchen]  # kept in ANY work mode (home base)
#   remote_ok: true                    # elsewhere: keep only remote/hybrid (and
#                                       # city-only EU postings whose mode is
#                                       # unknown); known-onsite & non-EU dropped.
# EU is recognised via a built-in allow-list (jobradar/filters.py); override
# with region_locations, or force-drop a place with drop_locations.

sources:
  ats:
    greenhouse: [adyen, n26, stripe, ...]
    ashby:      [pliant, ...]
    lever:      [binance, ...]
    personio:   [westwing, ...]              # subdomain only
  workday:
    limit: 20
    mastercard: { endpoint: "...", searches: [payment, ...] }
  arbeitsagentur:
    enabled: true
    location: München
    radius_km: 30
    searches: [payment, zahlungsverkehr, ...]
  bigtech:
    amazon: { enabled: false, queries: [payment operations] }
  jobspy:
    enabled: true
    sites: [indeed, google, linkedin]
    search_terms: [payment operations, ...]
    location: "Munich, Germany"
    country_indeed: germany
    company_sweep:                           # for companies w/o a clean feed
      roles: [payment operations, reconciliation]
      companies: [Revolut, Klarna, Visa, ...]
```

## Adding more companies & sources

**Add a company (no code):** find its ATS from the careers URL and add the
handle:

- `boards.greenhouse.io/<handle>` → `sources.ats.greenhouse`
- `jobs.lever.co/<handle>` → `sources.ats.lever`
- `jobs.ashbyhq.com/<handle>` → `sources.ats.ashby`
- `<handle>.jobs.personio.de` → `sources.ats.personio` (handle = subdomain)
- Workday (`<tenant>.wdN.myworkdayjobs.com/...`) → add an entry under
  `sources.workday` with its `/wday/cxs/<tenant>/<site>/jobs` endpoint

A bad handle just logs a warning and is skipped.

**Add a whole new source (SmartRecruiters, Recruitee, RemoteOK, …):** these have
free public APIs — see [`docs/SOURCES.md`](docs/SOURCES.md) for the shortlist.
Each is a small adapter in `jobradar/sources/`; ask and it can be wired in.

## Tuning & FAQ

**Frequency** — set when installing: `bash scripts/install_launchd.sh 1800`.

**Laptop asleep?** `launchd` doesn't run while asleep; it does one catch-up run
on wake. For true 24/7, move to a free GitHub Actions cron (public repo).

**Resources** — nothing when idle (not a server). A run lasts ~10–20s, peaks
~200 MB RAM, then exits. Disk: `.venv` ~240 MB; DB grows a few KB per 100 jobs.

**Relevance ranking** — matches are sent most-relevant first (more title-keyword
hits + a home-location bonus). Tune weights in `jobradar/filters.py`.

**Duplicates** — never alerted twice for the same posting; the same role at the
same company across two sites is also collapsed (`dedupe_cross_source`).

**Too many / too few alerts** — raise `min_score`, lower `max_per_run`, or
tighten `keywords`/`locations`. To broaden (e.g. more EU cities), add them to
`locations`.

**False positives (wrong-domain roles that share a keyword)** — e.g. a
"Payment Platform Engineer" matching a finance search. Add the off-domain words
to `keywords.exclude_title`. Unlike `exclude` (which scans title + description),
`exclude_title` only checks the title, so it won't drop a genuine role whose
description happens to mention, say, "engineering teams". The payments profile
ships with a starter list (engineer, developer, software, sales, recruiter, …).

## Project layout

```
run.py                 # entry point: fetch → filter → rank → dedupe → notify
config.yaml            # active search (safe to commit/fork; secrets stay in .env)
.env                   # TELEGRAM_* secrets (gitignored)
profiles/              # ready-made searches (payments, ml)
docs/SOURCES.md        # source audit: covered / missing / addable
jobradar/
  config.py models.py filters.py store.py notify.py
  sources/
    ats.py           # Greenhouse / Lever / Ashby / Personio
    workday.py       # Workday cxs feeds
    arbeitsagentur.py# Germany's federal job DB
    bigtech.py       # Amazon
    boards.py        # JobSpy: Indeed / Google / LinkedIn + company_sweep
scripts/             # launchd agent + installer (macOS); run.sh / run.bat wrappers
```

## Notes & limits

- JobSpy scrapes sites that discourage it — fine for personal use, but it can
  break; update with `./.venv/bin/pip install -U python-jobspy`.
- LinkedIn rate-limits aggressively; if it starts failing, drop it from
  `jobspy.sites`.
- WhatsApp can be added later via Meta's WhatsApp Business Cloud API (heavier
  setup). Telegram is the supported channel today.
