"""Applicant Tracking System public JSON feeds.

These are the endpoints the companies' own career pages call. No key, no
proxy, no login. This is the most reliable, lowest-maintenance source: you
just maintain a list of company handles per ATS in config.yaml.
"""
from __future__ import annotations

import logging
import urllib.request
import xml.etree.ElementTree as ET

from ..models import Job
from .base import UA, http_json

log = logging.getLogger("jobradar.sources.ats")


def _greenhouse(handle: str) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{handle}/jobs?content=true"
    data = http_json(url)
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(
            Job(
                source=f"greenhouse:{handle}",
                external_id=str(j.get("id", "")),
                title=j.get("title", ""),
                company=handle,
                url=j.get("absolute_url", ""),
                location=(j.get("location") or {}).get("name", ""),
                posted_at=j.get("updated_at", ""),
                description=j.get("content", "")[:500],
                raw=j,
            )
        )
    return jobs


def _lever(handle: str) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{handle}?mode=json"
    data = http_json(url)
    jobs = []
    for j in data:
        cat = j.get("categories", {}) or {}
        jobs.append(
            Job(
                source=f"lever:{handle}",
                external_id=str(j.get("id", "")),
                title=j.get("text", ""),
                company=handle,
                url=j.get("hostedUrl", ""),
                location=cat.get("location", ""),
                posted_at=str(j.get("createdAt", "")),
                description=(j.get("descriptionPlain") or "")[:500],
                # Lever exposes workplaceType = remote / hybrid / onsite.
                work_mode=(j.get("workplaceType") or "").lower(),
                raw=j,
            )
        )
    return jobs


def _ashby(handle: str) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{handle}"
    data = http_json(url)
    jobs = []
    for j in data.get("jobs", []):
        # Ashby gives workplaceType (Remote/Hybrid/On-site) and an isRemote bool.
        wt = (j.get("workplaceType") or "").lower().replace("-", "").replace(" ", "")
        mode = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}.get(wt, "")
        if not mode and j.get("isRemote") is True:
            mode = "remote"
        jobs.append(
            Job(
                source=f"ashby:{handle}",
                external_id=str(j.get("id", "")),
                title=j.get("title", ""),
                company=handle,
                url=j.get("jobUrl") or j.get("applyUrl", ""),
                location=j.get("location", ""),
                posted_at=j.get("publishedAt", ""),
                description=(j.get("descriptionPlain") or "")[:500],
                work_mode=mode,
                raw=j,
            )
        )
    return jobs


def _personio(handle: str) -> list[Job]:
    """Personio XML feed — very common for German companies.

    `handle` is the subdomain (e.g. "westwing"); we try .de then .com.
    """
    for tld in ("de", "com"):
        host = f"{handle}.jobs.personio.{tld}"
        try:
            req = urllib.request.Request(f"https://{host}/xml",
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except Exception:
            continue
        if "<position>" not in text:
            continue
        root = ET.fromstring(text)
        jobs = []
        for pos in root.iter("position"):
            def field(tag: str) -> str:
                el = pos.find(tag)
                return el.text or "" if el is not None else ""
            pid = field("id")
            jobs.append(
                Job(
                    source=f"personio:{handle}",
                    external_id=pid,
                    title=field("name"),
                    company=field("subcompany") or handle,
                    url=f"https://{host}/job/{pid}",
                    location=field("office"),
                    posted_at=field("createdAt"),
                    raw={},
                )
            )
        return jobs
    return []


_HANDLERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "personio": _personio,
}


def fetch(cfg: dict) -> list[Job]:
    """cfg['sources']['ats'] = {greenhouse: [..handles..], lever: [...], ...}"""
    ats_cfg = (cfg.get("sources", {}) or {}).get("ats", {}) or {}
    out: list[Job] = []
    for platform, handles in ats_cfg.items():
        handler = _HANDLERS.get(platform)
        if not handler:
            log.warning("Unknown ATS platform '%s' in config", platform)
            continue
        for handle in handles or []:
            try:
                found = handler(handle)
                log.info("ats %s:%s -> %d postings", platform, handle, len(found))
                out.extend(found)
            except Exception as exc:  # noqa: BLE001 - isolate per-company failures
                log.warning("ats %s:%s failed: %s", platform, handle, exc)
    return out
