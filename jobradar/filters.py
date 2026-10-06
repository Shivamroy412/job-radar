"""Keyword / location matching. Config-driven, deliberately simple."""
from __future__ import annotations

import re
from typing import Any

from .models import Job

# A job outside Munich is kept only when its location is recognizably
# Germany/EU/EEA (or bare "remote" with no place named). This allow-list is
# more reliable than a non-EU denylist: postings often give only a city with no
# country ("San Francisco", "New York"), and there are far too many non-EU
# cities to enumerate — so we keep what we can place in Europe and drop the
# rest. Extend via `region_locations` in config (e.g. a German town not listed).
DEFAULT_REGION_LOCATIONS = [
    # region words
    "germany", "deutschland", "europe", "european union", " eu", "(eu", "eu)",
    "eea", "emea", "schengen", "dach",
    # EU / EEA / Switzerland country names (English + common German)
    "austria", "österreich", "belgium", "belgique", "belgië", "bulgaria",
    "croatia", "cyprus", "czech", "czechia", "tschechien", "denmark", "dänemark",
    "estonia", "finland", "finnland", "france", "frankreich", "greece",
    "griechenland", "hungary", "ungarn", "ireland", "irland", "italy", "italien",
    "latvia", "lithuania", "luxembourg", "luxemburg", "malta", "netherlands",
    "niederlande", "holland", "poland", "polen", "portugal", "romania",
    "rumänien", "slovakia", "slovenia", "spain", "spanien", "sweden", "schweden",
    "norway", "norwegen", "iceland", "liechtenstein", "switzerland", "schweiz",
    # major German cities (non-Munich) + Munich-area towns
    "berlin", "hamburg", "cologne", "köln", "frankfurt", "stuttgart",
    "düsseldorf", "dusseldorf", "dortmund", "essen", "leipzig", "dresden",
    "hannover", "hanover", "nürnberg", "nuremberg", "bremen", "bonn", "mannheim",
    "karlsruhe", "wiesbaden", "münster", "freiburg", "augsburg", "walldorf",
    "eschborn", "ismaning", "garching", "dachau", "unterföhring", "planegg",
    # other major EU/EEA cities commonly seen in postings
    "amsterdam", "rotterdam", "the hague", "den haag", "eindhoven", "paris",
    "lyon", "madrid", "barcelona", "valencia", "lisbon", "lisboa", "porto",
    "milan", "milano", "rome", "roma", "dublin", "vienna", "wien", "zurich",
    "zürich", "geneva", "genève", "basel", "brussels", "bruxelles", "brussel",
    "antwerp", "stockholm", "copenhagen", "kopenhagen", "oslo", "helsinki",
    "warsaw", "warszawa", "krakow", "kraków", "prague", "prag", "budapest",
    "athens", "tallinn", "riga", "vilnius", "bratislava", "ljubljana", "zagreb",
    "sofia", "bucharest", "luxembourg city",
]

# Words that, alone, mean "remote with no place named" -> treated as EU-eligible.
_REMOTE_FILLERS = {
    "remote", "anywhere", "fully", "hybrid", "home", "office", "homeoffice",
    "wfh", "work", "from", "based", "flexible", "first",
}


def _is_bare_remote(loc: str) -> bool:
    """True when the location is empty or only remote-ish words (no place)."""
    tokens = [t for t in re.split(r"[^a-zäöüß]+", loc) if t]
    return all(t in _REMOTE_FILLERS for t in tokens)  # also True when empty


class Matcher:
    def __init__(self, cfg: dict[str, Any]):
        kw = cfg.get("keywords", {}) or {}
        self.include = [k.lower() for k in kw.get("include", [])]
        self.exclude = [k.lower() for k in kw.get("exclude", [])]
        # exclude_title: negative words checked against the TITLE ONLY. Use this
        # to kill false positives like "Payment Platform Engineer" without also
        # dropping finance roles whose *description* happens to mention engineers
        # (which a plain `exclude` would, since it scans title + snippet).
        self.exclude_title = [k.lower() for k in kw.get("exclude_title", [])]
        # title_only: require include keywords to appear in the TITLE, not just
        # anywhere in the description (cuts a lot of noise).
        self.title_only = bool(kw.get("title_only", True))
        self.locations = [l.lower() for l in cfg.get("locations", [])]
        self.remote_ok = bool(cfg.get("remote_ok", True))
        # home_locations: home base, kept regardless of work mode. When set, we
        # switch to the "Munich always; elsewhere in DE/EU only if remote/hybrid"
        # policy. When empty, the classic `locations` allow-list is used.
        self.home_locations = [l.lower() for l in cfg.get("home_locations", [])]
        # region_locations = recognizably Germany/EU/EEA places (allow-list).
        self.region_locations = [
            l.lower() for l in cfg.get("region_locations", DEFAULT_REGION_LOCATIONS)
        ]
        # drop_locations = optional extra denylist, applied even inside the
        # region (e.g. a city she'd never commute to). Default: none.
        self.drop_locations = [l.lower() for l in cfg.get("drop_locations", [])]

    def matches(self, job: Job) -> bool:
        # Exclude keywords always apply (drop interns/working students etc.).
        if self.exclude and any(k in job.haystack() for k in self.exclude):
            return False

        title = job.title.lower()
        # Title-only excludes: drop off-domain roles that merely share a keyword
        # (e.g. an engineering role with "payment" in its title).
        if self.exclude_title and any(k in title for k in self.exclude_title):
            return False

        hay = title if self.title_only else job.haystack()
        if self.include and not any(k in hay for k in self.include):
            return False

        # Location filter — skipped for prefiltered sources (Arbeitsagentur
        # already did a radius search, so nearby towns are wanted).
        if job.prefiltered:
            return True
        if self.home_locations:
            return self._location_ok_tiered(job)
        if self.locations:
            loc = job.location.lower()
            is_remote = "remote" in loc or "anywhere" in loc
            if self.remote_ok and is_remote:
                return True
            if not any(l in loc for l in self.locations):
                return False
        return True

    def _location_ok_tiered(self, job: Job) -> bool:
        """Munich always; elsewhere in Germany/EU only if remote or hybrid.

        - Home (Munich) -> keep, any work mode.
        - Explicit drop_locations match -> drop.
        - Known ONSITE outside home -> drop.
        - Recognizably Germany/EU/EEA, or bare "remote" -> keep
          (remote / hybrid / unknown work mode all pass here, per the choice to
          keep city-only postings whose mode a source doesn't report).
        - Anything we can't place in Europe (e.g. "San Francisco", "Kazakhstan")
          -> drop.
        """
        loc = job.location.lower()
        if any(h in loc for h in self.home_locations):
            return True
        if self.drop_locations and any(d in loc for d in self.drop_locations):
            return False
        if job.effective_work_mode() == "onsite":
            return False
        if any(r in loc for r in self.region_locations):
            return True
        if self.remote_ok and _is_bare_remote(loc):
            return True
        return False

    def score(self, job: Job) -> int:
        """Rough relevance score — higher = more relevant. Explainable on purpose.

        - each include keyword found in the TITLE adds points (multi-word
          phrases like "payment operations" count for more than "payment")
        - a preferred city/country in the location adds points
        - Munich gets an extra nudge (home base)
        """
        title = job.title.lower()
        s = 0
        for kw in self.include:
            if kw in title:
                s += 2 + kw.count(" ")  # phrase bonus
        loc = job.location.lower()
        for l in self.locations:
            if l != "europe" and l in loc:  # a specific place, not the whole continent
                s += 3
                break
        if any(h in loc for h in self.home_locations) or "munich" in loc or "münchen" in loc:
            s += 2
        # Prefer flexible roles when we're including Germany/EU postings.
        if job.effective_work_mode() in ("remote", "hybrid"):
            s += 1
        return s

    def filter(self, jobs: list[Job]) -> list[Job]:
        """Return matching jobs, most relevant first."""
        matched = [j for j in jobs if self.matches(j)]
        matched.sort(key=self.score, reverse=True)
        return matched
