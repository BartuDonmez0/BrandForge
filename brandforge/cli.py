"""BrandForge CLI."""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from brandforge import __app_name__, __version__
from brandforge.config import CATEGORY_PREFIXES, get_settings
from brandforge.logo import generate_logo_kit
from brandforge.pipeline import run_pipeline
from brandforge.report import availability_icon

app = typer.Typer(
    name="brandforge",
    help="Forge startup names: generate -> filter -> domain -> GitHub -> trademark -> logo.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console(legacy_windows=False, force_terminal=True)


class Category(str, Enum):
    ai = "ai"
    ecommerce = "ecommerce"
    healthcare = "healthcare"
    finance = "finance"
    cybersecurity = "cybersecurity"
    education = "education"
    cloud = "cloud"


def _banner() -> None:
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]{__app_name__}[/bold] v{__version__}\n"
                "[dim]Generate | Filter | Domain | GitHub | Trademark | Logo[/dim]"
            ),
            border_style="steel_blue",
        )
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    category: Optional[Category] = typer.Option(
        None,
        "--category",
        "-c",
        help="Project type for tuned roots (ai, ecommerce, healthcare, ...).",
    ),
    count: int = typer.Option(100_000, "--count", "-n", help="Name pool size to generate."),
    top: int = typer.Option(20, "--top", "-t", help="How many clean winners to keep."),
    max_check: int = typer.Option(
        400,
        "--max-check",
        help="Max candidates to probe online (domain/GitHub).",
    ),
    min_length: int = typer.Option(5, "--min-length", help="Minimum name length."),
    max_length: int = typer.Option(10, "--max-length", help="Maximum name length."),
    no_domain: bool = typer.Option(False, "--no-domain", help="Skip .com checks."),
    no_github: bool = typer.Option(False, "--no-github", help="Skip GitHub checks."),
    no_trademark: bool = typer.Option(False, "--no-trademark", help="Skip trademark reports."),
    no_logo: bool = typer.Option(False, "--no-logo", help="Skip logo kit generation."),
    seed: int = typer.Option(42, "--seed", help="RNG seed for reproducible runs."),
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit."),
) -> None:
    """Run the full BrandForge pipeline (default command)."""
    if version:
        console.print(f"{__app_name__} {__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    _banner()
    settings = get_settings()
    cat = category.value if category else None

    def progress(msg: str) -> None:
        console.print(f"[steel_blue]>[/steel_blue] {msg}")

    result = asyncio.run(
        run_pipeline(
            category=cat,
            target_count=count,
            top_n=top,
            min_length=min_length,
            max_length=max_length,
            check_domain=not no_domain,
            check_github=not no_github,
            check_trademark=not no_trademark,
            generate_logos=not no_logo,
            max_check=max_check,
            seed=seed,
            settings=settings,
            progress=progress,
        )
    )

    table = Table(title="Top Startup Names", show_lines=False, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column(".com")
    table.add_column("GitHub")
    table.add_column("TM Risk")
    table.add_column("Score", justify="right")

    for i, w in enumerate(result.winners, 1):
        risk = (w.trademark or {}).get("risk", "-")
        table.add_row(
            str(i),
            w.name,
            availability_icon(w.domain),
            availability_icon(w.github),
            str(risk),
            f"{w.score:.0f}",
        )

    console.print()
    if result.winners:
        console.print(table)
    else:
        console.print("[yellow]No fully free candidates in this batch. Try --max-check 800 or another --seed.[/yellow]")

    console.print()
    console.print(f"[dim]JSON[/dim]  {result.json_path}")
    console.print(f"[dim]MD[/dim]    {result.markdown_path}")
    if result.logos:
        console.print(f"[dim]Logos[/dim] {len(result.logos)} kits in output/logos/")


@app.command("categories")
def list_categories() -> None:
    """List supported project categories."""
    _banner()
    table = Table(title="Project categories")
    table.add_column("Key")
    table.add_column("Root count", justify="right")
    for key, prefixes in CATEGORY_PREFIXES.items():
        table.add_row(key, str(len(prefixes)))
    console.print(table)


@app.command("logo")
def logo_cmd(
    name: str = typer.Argument(..., help="Brand name to mark."),
    category: Optional[Category] = typer.Option(None, "--category", "-c"),
) -> None:
    """Generate SVG + PNG + AI logo prompt for a single name."""
    _banner()
    kit = generate_logo_kit(name, category.value if category else None)
    console.print(f"[green]SVG[/green]    {kit['svg']}")
    console.print(f"[green]PNG[/green]    {kit['png']}")
    console.print(f"[green]Prompt[/green] {kit['prompt']}")
    console.print()
    console.print(Panel(kit["prompt_text"], title="Logo prompt", border_style="steel_blue"))


@app.command("check")
def check_cmd(
    name: str = typer.Argument(..., help="Single name to probe."),
    no_trademark: bool = typer.Option(False, "--no-trademark"),
) -> None:
    """Check one name for .com + GitHub (+ trademark report)."""
    from brandforge.checkers import check_candidate
    import httpx

    _banner()
    settings = get_settings()

    async def _run():
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await check_candidate(
                client,
                name,
                settings,
                check_domain=True,
                check_gh=True,
                check_tm=not no_trademark,
            )

    r = asyncio.run(_run())
    console.print(f"[bold]{r.name}[/bold]  score={r.score:.0f}")
    console.print(f"  .com   {availability_icon(r.domain)} - {r.domain_detail}")
    console.print(f"  GitHub {availability_icon(r.github)} - {r.github_detail}")
    if r.trademark:
        tm = r.trademark
        console.print(f"  USPTO  {'*' * tm['uspto_similarity_stars']}")
        console.print(f"  EUIPO  {'*' * tm['euipo_similarity_stars']}")
        console.print(f"  Risk   {tm['risk']}")


if __name__ == "__main__":
    app()
