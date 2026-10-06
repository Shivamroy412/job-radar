"""Best-effort, free, keyless title translation (German -> English).

Deliberately tiny and fail-open: used only to make German job titles (mostly
from Arbeitsagentur) readable in the Telegram alert. If a translation endpoint
is blocked, slow, or errors, we just return the original text — nothing breaks,
the message simply stays in German. Results are cached per process so repeated
titles in one run cost one call.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from functools import lru_cache

log = logging.getLogger("jobradar.translate")

_TIMEOUT = 5  # seconds per endpoint; short so a hang can't stall the run

# Cheap "is this German?" signal, so we don't waste calls on English titles
# (and don't risk mangling them by forcing a de->en translation).
_GERMAN_HINTS = (
    "und", "für", "mit", "der", "die", "das", "bei", "im", "zur", "zum",
    "kaufmann", "kauffrau", "mitarbeiter", "sachbearbeiter", "leiter",
    "leitung", "vertrieb", "einkauf", "buchhaltung", "zahlungsverkehr",
    "referent", "fachkraft", "angestellte", "stellv", "gmbh", "wirtschaft",
)


def looks_german(text: str) -> bool:
    t = (text or "").lower()
    if any(ch in t for ch in "äöüß"):
        return True
    words = set(t.replace("/", " ").replace("-", " ").split())
    return any(h in words for h in _GERMAN_HINTS)


def _google(text: str) -> str:
    q = urllib.parse.urlencode(
        {"client": "gtx", "sl": "de", "tl": "en", "dt": "t", "q": text}
    )
    url = "https://translate.googleapis.com/translate_a/single?" + q
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        data = json.loads(r.read().decode())
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def _mymemory(text: str) -> str:
    q = urllib.parse.urlencode({"q": text, "langpair": "de|en"})
    url = "https://api.mymemory.translated.net/get?" + q
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as r:
        data = json.loads(r.read().decode())
    return data["responseData"]["translatedText"]


@lru_cache(maxsize=512)
def to_english(text: str) -> str:
    """Return an English rendering of a German title, or the original on any
    failure / if it doesn't look German."""
    if not text or not looks_german(text):
        return text
    for fn in (_google, _mymemory):
        try:
            out = fn(text).strip()
            if out:
                return out
        except Exception as exc:  # noqa: BLE001 - never let translation break a run
            log.info("translate via %s failed: %s", fn.__name__, exc)
    return text
