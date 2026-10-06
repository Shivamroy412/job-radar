"""Normalized job posting model shared by every source."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    # collapse whitespace and strip basic HTML tags that some ATS feeds include
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Job:
    """One normalized posting. Every source adapter must emit these."""

    source: str                      # e.g. "greenhouse:stripe", "jobspy:indeed"
    external_id: str                 # stable id from the source (or the url)
    title: str
    company: str
    url: str
    location: str = ""
    posted_at: str = ""              # ISO-ish string when available, else ""
    description: str = ""            # short snippet, optional
    # Work mode from a source's STRUCTURED field, when it has one:
    # "remote" / "hybrid" / "onsite". Empty = the source didn't say (we then
    # fall back to reading the text). Only a structured "onsite" is trusted
    # enough to drop a job; we never infer "onsite" from free text.
    work_mode: str = ""
    # True when the source already did a location/radius search server-side
    # (Arbeitsagentur, etc.) — such results skip our location filter so nearby
    # towns are kept, but keyword include/exclude filters still apply.
    prefiltered: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.title = _clean(self.title)
        self.company = _clean(self.company)
        self.location = _clean(self.location)
        self.description = _clean(self.description)

    @property
    def uid(self) -> str:
        """Stable dedupe key.

        Prefer source+external_id (survives URL tracking-param churn); fall
        back to the URL when a source gives no id.
        """
        basis = f"{self.source}|{self.external_id}" if self.external_id else self.url
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def dupe_key(self) -> str:
        """Cross-source dedupe key: same role at same company on two sites.

        Normalizes the title (drops '(m/f/d)' etc. and punctuation) and the
        company. Conservative on purpose — if the company strings differ it
        won't merge, so we favour a rare double-alert over hiding a real job.
        """
        title = re.sub(r"\(.*?\)", " ", self.title.lower())
        title = re.sub(r"[^a-z0-9 ]", " ", title)
        title = re.sub(r"\s+", " ", title).strip()
        company = re.sub(r"[^a-z0-9]", "", self.company.lower())
        return f"{title}::{company}" if title and company else self.uid

    def haystack(self) -> str:
        """Lowercased text that filters match against."""
        return f"{self.title} {self.location} {self.description}".lower()

    def effective_work_mode(self) -> str:
        """Best guess at work mode: 'remote' / 'hybrid' / 'onsite' / '' (unknown).

        Trusts a source's structured `work_mode` first. Otherwise reads the
        text — but only ever infers 'remote' or 'hybrid' from wording, never
        'onsite' (too unreliable), so a missing signal stays 'unknown' rather
        than being wrongly treated as onsite.
        """
        if self.work_mode:
            return self.work_mode.lower()
        hay = f"{self.title} {self.location} {self.description}".lower()
        if "hybrid" in hay:
            return "hybrid"
        remote_terms = (
            "remote", "anywhere", "work from home", "home office", "homeoffice",
            "wfh", "fully remote", "remote-first", "telearbeit", "mobiles arbeiten",
        )
        if any(t in hay for t in remote_terms):
            return "remote"
        return ""
