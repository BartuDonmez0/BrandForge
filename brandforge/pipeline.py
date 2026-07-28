"""End-to-end BrandForge pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from brandforge.checkers import Availability, CheckResult, check_many
from brandforge.config import Settings, get_settings
from brandforge.filters import apply_basic_filters, filter_length, pronunciation_score
from brandforge.generators import GeneratedName, generate_names
from brandforge.logo import generate_logo_kit
from brandforge.report import write_json_report, write_markdown_report

ProgressCb = Callable[[str], None]


@dataclass
class PipelineResult:
    winners: list[CheckResult] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    json_path: str | None = None
    markdown_path: str | None = None
    logos: dict[str, dict[str, str]] = field(default_factory=dict)


async def run_pipeline(
    *,
    category: str | None = None,
    target_count: int | None = None,
    top_n: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    check_domain: bool = True,
    check_github: bool = True,
    check_trademark: bool | None = None,
    generate_logos: bool | None = None,
    max_check: int = 400,
    seed: int | None = 42,
    settings: Settings | None = None,
    progress: ProgressCb | None = None,
) -> PipelineResult:
    """
    Word Generator → Length → Pronunciation → .com → GitHub → Trademark → Top N.
    """
    cfg = settings or get_settings()
    target = target_count if target_count is not None else cfg.target_count
    winners_n = top_n if top_n is not None else cfg.top_n
    min_len = min_length if min_length is not None else cfg.min_length
    max_len = max_length if max_length is not None else cfg.max_length
    do_tm = cfg.check_trademark if check_trademark is None else check_trademark
    do_logos = cfg.generate_logos if generate_logos is None else generate_logos

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    log(f"Generating up to {target:,} names...")
    pool: list[GeneratedName] = generate_names(
        category=category,
        target_count=target,
        seed=seed,
    )
    log(f"Pool size: {len(pool):,}")

    after_length = filter_length(pool, min_len=min_len, max_len=max_len)
    log(f"After length filter ({min_len}-{max_len}): {len(after_length):,}")

    filtered = apply_basic_filters(
        pool,
        min_len=min_len,
        max_len=max_len,
        min_pronunciation=55.0,
    )
    filtered.sort(key=lambda n: pronunciation_score(n.name), reverse=True)
    log(f"After pronunciation filter: {len(filtered):,}")

    # Cap live network checks - checking 100k domains would take hours
    to_check = [n.name for n in filtered[:max_check]]
    log(f"Checking availability for {len(to_check):,} candidates...")

    kept_count = 0
    rej_count = 0

    def on_progress(result: CheckResult, rejected: bool = False) -> None:
        nonlocal kept_count, rej_count
        if rejected:
            rej_count += 1
        else:
            kept_count += 1
        total = kept_count + rej_count
        if total % 25 == 0 or total == len(to_check):
            log(f"  checked {total}/{len(to_check)} - kept={kept_count} rejected={rej_count}")

    checked = await check_many(
        to_check,
        cfg,
        check_domain=check_domain,
        check_gh=check_github,
        check_tm=do_tm,
        require_domain_free=check_domain,
        require_github_free=check_github,
        on_progress=on_progress,
    )

    def sort_key(r: CheckResult) -> tuple:
        risk_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(
            (r.trademark or {}).get("risk", "MEDIUM"), 1
        )
        domain_ok = 0 if r.domain == Availability.AVAILABLE else 1
        gh_ok = 0 if r.github == Availability.AVAILABLE else 1
        return (domain_ok, gh_ok, risk_rank, -r.score, len(r.name))

    checked.sort(key=sort_key)
    winners = checked[:winners_n]
    log(f"Selected top {len(winners)} names")

    meta = {
        "category": category,
        "generated": len(pool),
        "after_length": len(after_length),
        "after_pronunciation": len(filtered),
        "checked": len(to_check),
        "kept_after_availability": len(checked),
        "top_n": winners_n,
        "seed": seed,
    }

    json_path = write_json_report(winners, meta)
    md_path = write_markdown_report(winners, meta)
    log(f"Reports -> {json_path.name}, {md_path.name}")

    logos: dict[str, dict[str, str]] = {}
    if do_logos and winners:
        log("Generating logo kits...")
        for w in winners:
            logos[w.name] = generate_logo_kit(w.name, category)

    return PipelineResult(
        winners=winners,
        meta=meta,
        json_path=str(json_path),
        markdown_path=str(md_path),
        logos=logos,
    )
