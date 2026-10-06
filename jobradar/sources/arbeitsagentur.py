"""Bundesagentur für Arbeit (Arbeitsagentur) — Germany's largest job database.

Free, official REST API used by their own job-search app. No signup; the
well-known public app key below is what their frontend uses. This is a
keyword+radius SEARCH source (like Indeed), so results are marked prefiltered:
they may have German titles and include nearby towns by design.

Docs: https://github.com/bundesAPI/jobsuche-api
"""
from __future__ import annotations

import logging
import urllib.parse

from ..models import Job
from .base import http_json

log = logging.getLogger("jobradar.sources.arbeitsagentur")

ENDPOINT = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
API_KEY = "jobboerse-jobsuche"          # public app key from bundesAPI
DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/"


def _search(was: str, wo: str, radius: int, size: int) -> list[Job]:
    params = {"was": was, "size": size, "page": 1}
    if wo:
        params["wo"] = wo
        params["umkreis"] = radius
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    data = http_json(url, headers={"X-API-Key": API_KEY})
    jobs = []
    for j in data.get("ergebnisliste", []):
        locs = j.get("stellenlokationen") or []
        ort = ""
        if locs:
            ort = (locs[0].get("adresse") or {}).get("ort", "")
        ref = j.get("referenznummer", "")
        jobs.append(
            Job(
                source="arbeitsagentur",
                external_id=ref,
                title=j.get("stellenangebotsTitel") or j.get("hauptberuf", ""),
                company=j.get("firma", ""),
                url=DETAIL_URL + urllib.parse.quote(ref) if ref else DETAIL_URL,
                location=ort or ("Remote" if j.get("homeofficemoeglich") else ""),
                posted_at=j.get("datumErsteVeroeffentlichung", ""),
                work_mode="remote" if j.get("homeofficemoeglich") else "",
                prefiltered=True,
                raw={},
            )
        )
    return jobs


def fetch(cfg: dict) -> list[Job]:
    aa = (cfg.get("sources", {}) or {}).get("arbeitsagentur", {}) or {}
    if not aa.get("enabled"):
        return []
    wo = aa.get("location", "")
    radius = int(aa.get("radius_km", 25))
    size = int(aa.get("size", 50))
    out: list[Job] = []
    for was in aa.get("searches", []):
        try:
            found = _search(was, wo, radius, size)
            log.info("arbeitsagentur '%s' -> %d postings", was, len(found))
            out.extend(found)
        except Exception as exc:  # noqa: BLE001
            log.warning("arbeitsagentur '%s' failed: %s", was, exc)
    return out
