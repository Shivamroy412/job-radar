"""Notification sinks. Telegram now; WhatsApp can slot in later."""
from __future__ import annotations

import html
import logging
import urllib.parse
import urllib.request
from typing import Any

from .models import Job
from .translate import to_english

log = logging.getLogger("jobradar.notify")

TG_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 3800  # Telegram hard limit is 4096; leave headroom


def _format(job: Job, translate: bool = False) -> str:
    raw_title = job.title
    title = html.escape(raw_title)
    extra = ""
    if translate:
        en = to_english(raw_title)  # returns original on failure / if not German
        if en and en.strip().lower() != raw_title.strip().lower():
            title = html.escape(en)
            extra = f" <i>(DE: {html.escape(raw_title)})</i>"
    company = html.escape(job.company or "—")
    loc = html.escape(job.location or "—")
    src = html.escape(job.source)
    return (
        f"<b>{title}</b>{extra}\n"
        f"{company} · {loc}\n"
        f"<a href=\"{html.escape(job.url)}\">Apply / view</a>  <i>({src})</i>"
    )


def _batches(jobs: list[Job], translate: bool = False) -> list[list[Job]]:
    """Group jobs into batches that each fit one Telegram message.

    Returns the jobs per batch (not the rendered text) so the caller can tell
    exactly which jobs made it into a message that actually sent.
    """
    batches: list[list[Job]] = []
    buf: list[Job] = []
    length = 0
    for job in jobs:
        card = _format(job, translate)
        if length + len(card) + 2 > MAX_LEN and buf:
            batches.append(buf)
            buf, length = [], 0
        buf.append(job)
        length += len(card) + 2
    if buf:
        batches.append(buf)
    return batches


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, translate: bool = False):
        self.token = token
        self.chat_id = chat_id
        self.translate = translate

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, jobs: list[Job]) -> list[Job]:
        """Send jobs; return ONLY the ones actually delivered.

        If a message fails (e.g. a bad token -> HTTP 401), we stop and report
        what got through. The caller marks just those as seen, so undelivered
        jobs stay "new" and are retried next run instead of being silently lost.
        """
        if not jobs:
            return []
        header = f"🛰️ <b>{len(jobs)} new job match(es)</b>"
        delivered: list[Job] = []
        for i, batch in enumerate(_batches(jobs, self.translate)):
            body = "\n\n".join(_format(j, self.translate) for j in batch)
            text = f"{header}\n\n{body}" if i == 0 else body
            if not self._post(text):
                break  # bad token/outage — don't mark the rest as sent
            delivered.extend(batch)
        return delivered

    def send_text(self, text: str) -> bool:
        """Send one plain status message (HTML allowed), e.g. a baseline note."""
        return self._post(text)

    def _post(self, text: str) -> bool:
        data = urllib.parse.urlencode(
            {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
        ).encode()
        req = urllib.request.Request(TG_API.format(token=self.token), data=data)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
            return True
        except Exception as exc:  # noqa: BLE001 - don't let alerts crash the run
            log.error("Telegram send failed: %s", exc)
            return False


class ConsoleNotifier:
    """Dry-run sink: prints matches instead of messaging."""

    configured = True

    def send(self, jobs: list[Job]) -> list[Job]:
        if not jobs:
            print("(no new matches)")
            return []
        print(f"\n=== {len(jobs)} NEW MATCH(ES) ===")
        for j in jobs:
            print(f"- {j.title} | {j.company} | {j.location}\n  {j.url}  [{j.source}]")
        return jobs

    def send_text(self, text: str) -> bool:
        print(text)
        return True


def build_notifier(cfg: dict[str, Any], dry_run: bool):
    # Opt-in: translate German titles to English in the alert (best-effort).
    translate = bool(cfg.get("translate_titles", False))
    if dry_run:
        return ConsoleNotifier()
    tg = cfg.get("telegram", {})
    notifier = TelegramNotifier(
        tg.get("bot_token", ""), tg.get("chat_id", ""), translate=translate
    )
    if not notifier.configured:
        log.warning("Telegram not configured; falling back to console output.")
        return ConsoleNotifier()
    return notifier
