# Run job-radar in the cloud (GitHub Actions)

Run job-radar 24/7 on GitHub's free runners — no always-on laptop needed. A
ready-made workflow lives at [`.github/workflows/schedule.yml`](../.github/workflows/schedule.yml);
it runs hourly and pings your Telegram on new matches.

> **Two facts that decide the setup**
> - Scheduled (cron) Actions run **only on the default branch** (`main`). You
>   can't schedule a run from a side branch — put your search on `main`.
> - Free **scheduled** Actions need a **public** repo.

Your personal `config.yaml` is gitignored, so it never reaches GitHub. The cloud
run therefore uses a **committed** file: a profile under `profiles/`, or the
generic `config.example.yaml`. Pick one with the `CONFIG_PATH` repo variable
(below). No secrets ever go in these files — only the Telegram token/chat ID,
which live in encrypted repo Secrets.

---

## Option A — run it in your own repo

1. **Make the repo public** (Settings → General → Danger Zone → Change visibility),
   if it isn't already.
2. **Add your Telegram secrets** — Settings → *Secrets and variables* → *Actions*
   → **Secrets** tab → *New repository secret*, twice:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. **Pick the search** (optional) — same page, **Variables** tab → *New
   repository variable*:
   - `CONFIG_PATH` = `profiles/payments.yaml` (or `profiles/ml.yaml`, or your own
     committed file). Leave it unset to use `config.example.yaml`.
4. **Enable + test** — open the **Actions** tab, enable workflows if prompted,
   click **job-radar** → **Run workflow** to fire one now. Check the log and your
   Telegram. After that it runs hourly on its own.

> **First-run flood is handled for you.** The workflow detects the very first
> cloud run (no "seen" state yet) and seeds a baseline — it sends a single
> "✅ job-radar is live" confirmation (so you know it works), **not** a flood of
> every open job, then alerts only on postings that appear *after*. To start
> fresh later, go to **Actions → job-radar → Run workflow** and tick **seed**.

---

## Option B — your wife runs her own copy (fork)

She gets her own copy on her account, her own alerts, and can tweak her search
without touching yours.

1. **Fork** — on your repo page she clicks **Fork** (top-right) → *Create fork*.
   She now has `github.com/<her-username>/job-radar`.
2. **Enable Actions on the fork** — open the **Actions** tab on *her* fork and
   click **"I understand my workflows, go ahead and enable them."** (Forks start
   with Actions off; scheduled runs stay off until this click.)
3. **Add her Telegram secrets** — her repo → Settings → *Secrets and variables*
   → *Actions* → **Secrets** → add:
   - `TELEGRAM_BOT_TOKEN` — she can **reuse the same bot** you already made (same
     token), or make her own via @BotFather (see the main README).
   - `TELEGRAM_CHAT_ID` — **hers** (message the bot, then ask `@userinfobot` for
     her ID). This is what makes alerts land in *her* chat.
4. **Pick / edit her search** — either:
   - set the `CONFIG_PATH` variable (Variables tab) to `profiles/payments.yaml`, or
   - edit a committed file directly on GitHub: open e.g. `profiles/payments.yaml`,
     click the ✏️ pencil, change keywords/locations, **Commit changes**. (Editing
     on GitHub is the easy no-terminal way, and a commit also resets the 60-day
     clock below.)
5. **Test** — Actions tab → **job-radar** → **Run workflow**. Confirm the log and
   her Telegram. Hourly from then on.

### Keep a fork alive (one gotcha)
GitHub **auto-disables scheduled workflows after 60 days of no activity** in the
repo. She'll get an email with a one-click **"Enable"** button. Any commit (like
editing her search terms) resets the 60-day timer, so active users rarely hit it.

---

## Changing the schedule
Edit the `cron` line in [`.github/workflows/schedule.yml`](../.github/workflows/schedule.yml):
`"0 * * * *"` = hourly, `"*/30 * * * *"` = every 30 min, `"0 */4 * * *"` = every
4 hours. Times are **UTC**. (GitHub cron can lag a few minutes under load; job
postings don't change by the minute, so hourly is plenty.)

## Troubleshooting
- **No Telegram message** — check the Actions run log, **Run one pass** step.
  - `Telegram send failed: HTTP Error 401` → the `TELEGRAM_BOT_TOKEN` secret is
    wrong. Get the live token from BotFather (`/mybots` → your bot → API Token),
    verify it at `https://api.telegram.org/bot<TOKEN>/getMe` (`"ok":true`), then
    re-paste it into the secret with no spaces/quotes/newline. (401 = bad token,
    not a bad chat id; and tokens don't expire — a dead one was revoked/mistyped.)
  - `no token` / `no chat id` → a Secret is missing or misnamed.
  - Runs fine but silent with `0 are new` → nothing new since the baseline (normal),
    **or** you're looking at a stale state — see Recovery below.
  - Make sure she messaged the bot once (bots can't start a chat).
- **Cron never fires** — the repo must be public, workflows enabled on the
  Actions tab, and (on a fork) not disabled by the 60-day rule. Also, `0 * * * *`
  (top of the hour) is the most contended slot and often delayed/dropped; a quieter
  minute like `17 * * * *` fires more reliably.
- **Re-alerted after a long idle gap** — the "seen" cache was evicted (best-effort,
  ~7 days). One-time noise; it re-seeds itself.

## Recovery — "it says N tracked, 0 new, but I never got those jobs"
This happens if runs sent against a **bad token**: the matches got marked "seen"
without ever reaching Telegram, so later runs see nothing new. (The current code
no longer marks un-delivered jobs as seen, so this can't recur — but you still
have to clear the state that the old runs left behind.) To re-deliver them:

1. **Sync the fork** so you're on the current code (Sync fork → Update branch).
2. **Fix the token** (see Troubleshooting above) — verify with `getMe`.
3. **Clear the stale "seen" state** — the Actions cache holding it:
   - Web: repo → Actions → left sidebar **Caches** → delete `jobradar-state-…`.
   - CLI: `gh cache delete --all -R <you>/job-radar`
4. **Force-deliver** — Actions → job-radar → **Run workflow** → leave **seed
   unchecked** → Run. A no-seed manual run does a real pass even from an empty
   state, so the matches are treated as new and sent (`max_per_run` at a time,
   the rest trickling in on later hourly runs).

Confirm in the **Run one pass** log: no `401`, and `state now tracks N` with N > 0.
