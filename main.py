"""TradeMind Harness — CLI entry point.

Usage:
    python main.py analyse "Analyze RELIANCE for intraday"
    python main.py history --symbol RELIANCE
    python main.py setup
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure the project directory is on sys.path so all internal imports work
_project_root = Path(__file__).parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents.coordinator import CoordinatorAgent
from config import settings
from context.memory import MemoryStore

console = Console()
store = MemoryStore()


# ═══════════════════════════════════════════════════════════════════════
# CLI commands
# ═══════════════════════════════════════════════════════════════════════


@click.group()
@click.version_option(version="0.1.0", prog_name="trademind")
def cli() -> None:
    """TradeMind Harness — AI-powered Intraday Trading Research."""


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option(
    "--symbol",
    "-s",
    help="Stock symbol override (if not in query)",
)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option(
    "--show-browser", "--visible", is_flag=True,
    help="Run browser in visible mode (not headless) for debugging",
)
def analyse(
    query: tuple[str, ...],
    symbol: str | None,
    json_output: bool,
    show_browser: bool,
) -> None:
    """Analyse a stock for intraday opportunity."""
    full_query = " ".join(query)
    if symbol:
        full_query = f"{full_query} ({symbol})"

    # If --show-browser is passed, force visible. Otherwise, fall back to setting.
    headless = False if show_browser else settings.browser_headless
    coordinator = CoordinatorAgent(browser_headless=headless)

    async def _run_and_close() -> Any:
        try:
            return await coordinator.run(query=full_query)
        finally:
            await coordinator.close()

    try:
        report = asyncio.run(_run_and_close())

        if json_output:
            console.print(json.dumps(report.model_dump(), indent=2, default=str))
            return

        # Rich-formatted output
        bias_str = report.bias.value if hasattr(report.bias, "value") else str(report.bias)
        bias_color = "green" if bias_str == "bullish" else "red" if bias_str == "bearish" else "yellow"

        console.print()
        console.print(
            Panel(
                f"[bold]{report.symbol}[/bold]\n\n"
                f"[{bias_color}]Bias: {bias_str.title()}[/{bias_color}] "
                f"({report.confidence:.0%} confidence)\n\n"
                f"[bold]Evidence:[/bold]",
                title="TradeMind Analysis",
                border_style="blue",
            )
        )

        if report.evidence:
            for e in report.evidence:
                console.print(f"  [green]✔[/green] {e}")

        if report.risks:
            console.print("\n[bold]Risks:[/bold]")
            for r in report.risks:
                console.print(f"  [red]✖[/red] {r}")

        if report.suggested_trade:
            t = report.suggested_trade
            table = Table(title="Suggested Trade", show_header=False)
            table.add_column("Field", style="bold")
            table.add_column("Value")
            if t.entry:
                table.add_row("Entry", t.entry)
            if t.stop_loss:
                table.add_row("Stop Loss", t.stop_loss)
            if t.target:
                table.add_row("Target", t.target)
            table.add_row("Rationale", t.rationale)
            console.print()
            console.print(table)

        console.print(f"\n[dim]Generated at: {report.generated_at}[/dim]")

    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--symbol", "-s", help="Filter by symbol")
@click.option("--limit", "-l", default=10, help="Number of records")
def history(symbol: str | None, limit: int) -> None:
    """Show past analysis history."""
    records = store.get_by_symbol(symbol.upper(), limit=limit) if symbol else store.get_recent(limit=limit)

    if not records:
        console.print("[yellow]No history found.[/yellow]")
        return

    table = Table(title=f"History ({'all' if not symbol else symbol})")
    table.add_column("ID")
    table.add_column("Query")
    table.add_column("Symbol")
    table.add_column("Bias")
    table.add_column("Confidence")
    table.add_column("Date")

    for r in records:
        confidence = f"{r['confidence']:.0%}" if r.get("confidence") else "-"
        bias = r.get("bias") or "-"
        date = (r.get("created_at") or "")[:19]
        symbol_val = r.get("symbol") or "-"
        query_val = (r.get("query") or "")[:50]

        table.add_row(
            str(r["id"]),
            query_val,
            symbol_val,
            bias,
            confidence,
            date,
        )

    console.print(table)


@cli.command()
@click.option(
    "--output", "-o", default=None,
    help="Path to write config (default: print to console)",
)
def show_config(output: str | None) -> None:
    """Show current configuration."""
    table = Table(title="Configuration")
    table.add_column("Key")
    table.add_column("Value")

    for key, value in settings.model_dump().items():
        table.add_row(key, str(value))

    console.print(table)

    if output:
        import json
        Path(output).write_text(
            json.dumps(settings.model_dump(), indent=2, default=str)
        )
        console.print(f"[green]Config written to {output}[/green]")


@cli.command()
def setup() -> None:
    """Run first-time setup checks."""
    console.print("[bold]TradeMind Harness — Setup[/bold]\n")

    # Check Ollama
    import httpx

    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            console.print(f"[green]✔[/green] Ollama running at {settings.ollama_base_url}")

            for required in [settings.reasoning_model, settings.vision_model, settings.fast_model]:
                if required in model_names:
                    console.print(f"   [green]✔[/green] Model {required} available")
                else:
                    console.print(f"   [yellow]⚠[/yellow] Model {required} not pulled yet")
                    console.print(f"      Run: ollama pull {required}")
        else:
            console.print(f"[red]✖[/red] Ollama returned status {resp.status_code}")
    except Exception as exc:
        console.print(f"[red]✖[/red] Cannot reach Ollama: {exc}")
        console.print(f"   Make sure Ollama is running: ollama serve")

    # Check data directory
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✔[/green] Data directory: {data_dir}")

    # Check Playwright
    try:
        import playwright
        import importlib.metadata
        try:
            version = importlib.metadata.version("playwright")
        except Exception:
            version = "unknown"
        console.print(f"[green]✔[/green] Playwright installed (v{version})")
    except ImportError:
        console.print("[yellow]⚠[/yellow] Playwright not installed")
        console.print("   Run: pip install playwright && playwright install chromium")

    # Check .env
    env_path = _project_root / ".env"
    if env_path.exists():
        console.print(f"[green]✔[/green] .env file found at {env_path}")
    else:
        console.print("[yellow]⚠[/yellow] No .env file found")
        console.print(f"   Copy .env.example to .env and customize")


if __name__ == "__main__":
    cli()
