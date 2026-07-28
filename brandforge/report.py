"""Report writers: JSON + Markdown brand dossiers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brandforge.checkers import Availability, CheckResult
from brandforge.config import REPORTS_DIR


def _stars(n: int) -> str:
    return "*" * n + "-" * max(0, 5 - n)


def write_json_report(
    results: list[CheckResult],
    meta: dict[str, Any],
    path: Path | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = path or (REPORTS_DIR / f"brandforge-{stamp}.json")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta,
        "candidates": [
            {
                "name": r.name,
                "score": r.score,
                "domain": r.domain.value,
                "domain_detail": r.domain_detail,
                "github": r.github.value,
                "github_detail": r.github_detail,
                "trademark": r.trademark,
            }
            for r in results
        ],
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_markdown_report(
    results: list[CheckResult],
    meta: dict[str, Any],
    path: Path | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = path or (REPORTS_DIR / f"brandforge-{stamp}.md")

    lines: list[str] = [
        "# BrandForge — Top Startup Names",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Run summary",
        "",
        f"- Category: `{meta.get('category') or 'general'}`",
        f"- Generated pool: **{meta.get('generated', 0):,}**",
        f"- After length filter: **{meta.get('after_length', 0):,}**",
        f"- After pronunciation filter: **{meta.get('after_pronunciation', 0):,}**",
        f"- Availability checks: **{meta.get('checked', 0):,}**",
        f"- Clean winners: **{len(results)}**",
        "",
        "## Top candidates",
        "",
    ]

    for i, r in enumerate(results, 1):
        tm = r.trademark or {}
        lines.extend(
            [
                f"### {i}. {r.name}",
                "",
                f"- **Score:** {r.score:.0f}",
                f"- **Domain:** `{r.name.lower()}.com` — {r.domain.value} ({r.domain_detail})",
                f"- **GitHub:** `github.com/{r.name.lower()}` — {r.github.value} ({r.github_detail})",
            ]
        )
        if tm:
            lines.extend(
                [
                    f"- **USPTO similarity:** {_stars(int(tm.get('uspto_similarity_stars', 0)))}",
                    f"- **EUIPO similarity:** {_stars(int(tm.get('euipo_similarity_stars', 0)))}",
                    f"- **Trademark risk:** {tm.get('risk', 'N/A')}",
                ]
            )
            for note in tm.get("notes", []):
                lines.append(f"  - {note}")
            links = tm.get("links", {})
            if links:
                lines.append("- **Research links:**")
                for label, url in links.items():
                    lines.append(f"  - [{label}]({url})")
            if tm.get("disclaimer"):
                lines.append(f"- _{tm['disclaimer']}_")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "_BrandForge heuristic reports are not legal advice._",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def availability_icon(status: Availability) -> str:
    return {
        Availability.AVAILABLE: "OK free",
        Availability.TAKEN: "X taken",
        Availability.UNKNOWN: "? unknown",
        Availability.ERROR: "! error",
    }.get(status, status.value)
