"""Rich renderables shared by the menu screens and the direct subcommands."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from scandata.checks.catalog import SECTION_WHY, SECTIONS, CheckInfo
from scandata.cli.theme import BRAND
from scandata.core.config import DEFAULT_THRESHOLDS
from scandata.core.options import ScanOptions


def checks_table(checks: list[CheckInfo]) -> Table:
    table = Table(header_style=f"bold {BRAND}", show_lines=False)
    table.add_column("ID", no_wrap=True)
    table.add_column("Section", no_wrap=True)
    table.add_column("Check")
    table.add_column("Mode", no_wrap=True)
    for c in checks:
        table.add_row(c.id, SECTIONS[c.section].split(". ", 1)[1], c.title, c.modes)
    return table


def check_panel(check: CheckInfo) -> Panel:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold", no_wrap=True)
    grid.add_column()
    grid.add_row("What", check.title)
    grid.add_row("Section", SECTIONS[check.section])
    grid.add_row("Why it matters", SECTION_WHY[check.section])
    grid.add_row("Method", check.method)
    grid.add_row("Severity", check.severity)
    grid.add_row("Modes", check.modes)
    return Panel(grid, title=f"[bold]{check.id}[/bold]", border_style=BRAND, expand=False)


def options_table(options: ScanOptions) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    rows = [
        ("Dataset folder", options.path or "[red](not set)[/red]"),
        ("Data type", options.type),
        ("Mode", options.mode),
        ("Splits", options.splits),
        ("Group regex", options.group_regex or "-"),
        ("Target size", options.target_size or "-"),
        ("Sample per class", options.sample or "all"),
        ("Seed", options.seed),
        ("Device", options.device),
        ("Config YAML", options.config or "-"),
        ("Report", options.out),
        ("JSON findings", options.json or "-"),
        ("Fail on", options.fail_on or "-"),
    ]
    for name, value in rows:
        table.add_row(name, str(value))
    return table


def command_panel(options: ScanOptions) -> Panel:
    return Panel(
        Syntax(options.to_command(), "bash", word_wrap=True, background_color="default"),
        title="Equivalent command",
        border_style="dim",
        expand=False,
    )


def thresholds_table() -> Table:
    table = Table(header_style=f"bold {BRAND}")
    table.add_column("Threshold")
    table.add_column("Default", justify="right")
    for name, value in DEFAULT_THRESHOLDS.items():
        table.add_row(name, str(value))
    return table


def engine_pending(options: ScanOptions) -> Panel:
    return Panel(
        Group(
            Text.from_markup(
                "The scan engine arrives in [bold]v0.1 (Phase 1)[/bold]. Your options are valid "
                "and will work unchanged once it lands."
            ),
            Text(""),
            Text(options.to_command(), style="bold"),
        ),
        title="Not built yet",
        border_style="yellow",
        expand=False,
    )
