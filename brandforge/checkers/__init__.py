"""Availability checkers: domain, GitHub, trademark report helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from brandforge.config import Settings


class Availability(str, Enum):
    AVAILABLE = "available"
    TAKEN = "taken"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(slots=True)
class CheckResult:
    name: str
    domain: Availability = Availability.UNKNOWN
    domain_detail: str = ""
    github: Availability = Availability.UNKNOWN
    github_detail: str = ""
    trademark: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


def _headers(settings: Settings, extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    if extra:
        h.update(extra)
    return h


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.4, min=0.4, max=4), reraise=True)
async def check_domain_com(client: httpx.AsyncClient, name: str, settings: Settings) -> tuple[Availability, str]:
    """
    Check .com via Verisign RDAP.
    404 → likely available; 200 → registered; other → unknown.
    """
    slug = name.lower()
    url = f"https://rdap.verisign.com/com/v1/domain/{quote(slug)}.com"
    try:
        resp = await client.get(url, headers=_headers(settings), timeout=settings.request_timeout)
    except httpx.HTTPError as exc:
        return Availability.UNKNOWN, f"rdap error: {exc}"

    if resp.status_code == 404:
        return Availability.AVAILABLE, f"{slug}.com appears unregistered"
    if resp.status_code == 200:
        return Availability.TAKEN, f"{slug}.com is registered"
    return Availability.UNKNOWN, f"rdap status {resp.status_code}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.4, min=0.4, max=4), reraise=True)
async def check_github(client: httpx.AsyncClient, name: str, settings: Settings) -> tuple[Availability, str]:
    """GitHub username/org availability via Users API (404 = free)."""
    slug = name.lower()
    url = f"https://api.github.com/users/{quote(slug)}"
    try:
        resp = await client.get(
            url,
            headers=_headers(settings, {"Accept": "application/vnd.github+json"}),
            timeout=settings.request_timeout,
        )
    except httpx.HTTPError as exc:
        return Availability.UNKNOWN, f"github error: {exc}"

    if resp.status_code == 404:
        return Availability.AVAILABLE, f"github.com/{slug} appears free"
    if resp.status_code == 200:
        return Availability.TAKEN, f"github.com/{slug} exists"
    if resp.status_code == 403:
        return Availability.UNKNOWN, "github rate limited — set BRANDFORGE_GITHUB_TOKEN"
    return Availability.UNKNOWN, f"github status {resp.status_code}"


def trademark_report(name: str) -> dict[str, Any]:
    """
    Build a trademark research report with search links + heuristic risk.

    Full USPTO/EUIPO similarity requires paid APIs; this prepares a structured
    manual-review package and a light linguistic risk estimate.
    """
    slug = name.lower()
    uspto_url = (
        "https://tmsearch.uspto.gov/search/search-information"
        f"?query={quote(name)}"
    )
    # Public USPTO TESS-style deep link alternative
    uspto_tess = f"https://tmsearch.uspto.gov/?tn={quote(name)}"
    euipo_url = (
        "https://euipo.europa.eu/eSearch/#details/trademarks/"
        f"{quote(name)}"
    )
    euipo_search = (
        "https://euipo.europa.eu/eSearch/#basic/"
        f"1+1+1+1/{quote(name)}"
    )
    wipo_url = f"https://branddb.wipo.int/en/similarname/results?name={quote(name)}"

    # Heuristic: longer unique blends tend to be safer; ultra-short common roots riskier
    risk_points = 0
    notes: list[str] = []
    common_roots = {
        "nova",
        "apex",
        "pulse",
        "forge",
        "cloud",
        "smart",
        "data",
        "pay",
        "shop",
        "care",
        "tech",
        "soft",
        "ware",
        "hub",
        "lab",
    }
    for root in common_roots:
        if root in slug:
            risk_points += 1
            notes.append(f"Contains common brand root '{root}'")

    if len(slug) <= 5:
        risk_points += 2
        notes.append("Very short names collide more often")
    elif len(slug) >= 8:
        risk_points -= 1
        notes.append("Longer coined name — usually safer")

    if slug.endswith(("ly", "ify", "io", "ai")):
        risk_points += 1
        notes.append("Popular startup suffix — check crowded classes")

    if risk_points <= 0:
        risk = "LOW"
        uspto_stars = 5
        euipo_stars = 4
    elif risk_points == 1:
        risk = "LOW"
        uspto_stars = 4
        euipo_stars = 4
    elif risk_points == 2:
        risk = "MEDIUM"
        uspto_stars = 3
        euipo_stars = 3
    else:
        risk = "HIGH"
        uspto_stars = 2
        euipo_stars = 2

    return {
        "name": name,
        "uspto_similarity_stars": uspto_stars,
        "euipo_similarity_stars": euipo_stars,
        "risk": risk,
        "notes": notes,
        "links": {
            "uspto": uspto_url,
            "uspto_alt": uspto_tess,
            "euipo": euipo_search,
            "euipo_alt": euipo_url,
            "wipo": wipo_url,
        },
        "disclaimer": (
            "Heuristic only — not legal advice. Always verify on USPTO, EUIPO, "
            "and with a trademark attorney before filing or launching."
        ),
    }


async def check_candidate(
    client: httpx.AsyncClient,
    name: str,
    settings: Settings,
    *,
    check_domain: bool = True,
    check_gh: bool = True,
    check_tm: bool = True,
    semaphore: asyncio.Semaphore | None = None,
) -> CheckResult:
    sem = semaphore or asyncio.Semaphore(settings.concurrency)

    async with sem:
        domain_status, domain_detail = Availability.UNKNOWN, "skipped"
        github_status, github_detail = Availability.UNKNOWN, "skipped"

        tasks = []
        if check_domain:
            tasks.append(("domain", check_domain_com(client, name, settings)))
        if check_gh:
            tasks.append(("github", check_github(client, name, settings)))

        results: dict[str, tuple[Availability, str]] = {}
        if tasks:
            gathered = await asyncio.gather(
                *(t[1] for t in tasks),
                return_exceptions=True,
            )
            for (label, _), outcome in zip(tasks, gathered):
                if isinstance(outcome, Exception):
                    results[label] = (Availability.ERROR, str(outcome))
                else:
                    results[label] = outcome

        if "domain" in results:
            domain_status, domain_detail = results["domain"]
        if "github" in results:
            github_status, github_detail = results["github"]

        tm = trademark_report(name) if check_tm else {}

        score = 0.0
        if domain_status == Availability.AVAILABLE:
            score += 50
        elif domain_status == Availability.UNKNOWN:
            score += 10
        if github_status == Availability.AVAILABLE:
            score += 30
        elif github_status == Availability.UNKNOWN:
            score += 5
        if tm:
            risk = tm.get("risk", "MEDIUM")
            score += {"LOW": 20, "MEDIUM": 10, "HIGH": 0}.get(risk, 5)

        return CheckResult(
            name=name,
            domain=domain_status,
            domain_detail=domain_detail,
            github=github_status,
            github_detail=github_detail,
            trademark=tm,
            score=score,
        )


async def check_many(
    names: list[str],
    settings: Settings,
    *,
    check_domain: bool = True,
    check_gh: bool = True,
    check_tm: bool = True,
    require_domain_free: bool = True,
    require_github_free: bool = True,
    on_progress: Any | None = None,
) -> list[CheckResult]:
    """
    Concurrently check candidates. Optionally drop taken domains/usernames early.
    """
    sem = asyncio.Semaphore(settings.concurrency)
    limits = httpx.Limits(max_connections=settings.concurrency, max_keepalive_connections=10)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        results: list[CheckResult] = []
        # Process in batches to allow early filtering feedback
        batch_size = max(settings.concurrency * 2, 20)
        for i in range(0, len(names), batch_size):
            batch = names[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[
                    check_candidate(
                        client,
                        n,
                        settings,
                        check_domain=check_domain,
                        check_gh=check_gh,
                        check_tm=check_tm,
                        semaphore=sem,
                    )
                    for n in batch
                ]
            )
            for r in batch_results:
                if require_domain_free and r.domain == Availability.TAKEN:
                    if on_progress:
                        on_progress(r, rejected=True)
                    continue
                if require_github_free and r.github == Availability.TAKEN:
                    if on_progress:
                        on_progress(r, rejected=True)
                    continue
                results.append(r)
                if on_progress:
                    on_progress(r, rejected=False)
        return results
