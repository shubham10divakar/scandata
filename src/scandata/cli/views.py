"""Rich renderables shared by the menu screens and the direct subcommands."""

from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from scandata.checks.catalog import SECTION_WHY, SECTIONS, CheckInfo
from scandata.cli.theme import BRAND
from scandata.core.config import DEFAULT_THRESHOLDS
from scandata.core.finding import Finding, Severity
from scandata.core.options import ScanOptions
from scandata.core.report import Report


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


SEVERITY_STYLE = {
    Severity.BLOCKER: "bold red", Severity.WARN: "yellow", Severity.INFO: "blue",
    Severity.PASS: "green",
}


def severity_tag(sev: Severity) -> str:
    return f"[{SEVERITY_STYLE[sev]}]{sev.name}[/{SEVERITY_STYLE[sev]}]"


def verdict_panel(report: Report) -> Panel:
    c = report.counts
    style = SEVERITY_STYLE.get(report.worst, "green")
    df = report.dataset.df
    body = Text.from_markup(
        f"[{style}]{report.verdict}[/{style}]\n"
        f"{c[Severity.BLOCKER]} blocker(s) · {c[Severity.WARN]} warning(s) · "
        f"{c[Severity.INFO]} info\n"
        f"[dim]{len(df):,} images · {df['label'].nunique()} classes · "
        f"splits: {', '.join(report.dataset.splits) or 'none'} · {report.runtime_s:.1f}s[/dim]"
    )
    return Panel(body, title="Verdict", border_style=style.split()[-1], expand=False)


def scorecard_table(report: Report) -> Table:
    table = Table(header_style=f"bold {BRAND}")
    table.add_column("Section")
    table.add_column("Status")
    table.add_column("Blockers", justify="right")
    table.add_column("Warnings", justify="right")
    for row in report.scorecard():
        table.add_row(row.title, severity_tag(row.status), str(row.blockers), str(row.warnings))
    return table


def fix_first_lines(report: Report, limit: int = 10) -> list[str]:
    return [f"{i}. {severity_tag(f.severity)} {escape(f.title)}"
            for i, f in enumerate(report.fix_first()[:limit], 1)]


def finding_panel(f: Finding, max_examples: int = 10) -> Panel:
    parts: list = [Text.from_markup(f"[dim]{f.check_id}[/dim]")]
    shown = {k: v for k, v in f.metric.items() if not isinstance(v, (dict, list)) and k != "skipped"}
    if shown:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column()
        for k, v in shown.items():
            grid.add_row(k, str(v))
        parts += [Text(""), grid]
    if f.evidence:
        parts += [Text(""), Text("Examples", style="bold")]
        parts += [Text(f"  {e}") for e in f.evidence[:max_examples]]
        if len(f.evidence) > max_examples:
            parts.append(Text(f"  ... {len(f.evidence) - max_examples} more in the report",
                              style="dim"))
    if f.fix:
        parts += [Text(""), Text.from_markup(f"[bold]Fix:[/bold] {escape(f.fix)}")]
    style = SEVERITY_STYLE[f.severity].split()[-1]
    return Panel(Group(*parts), title=f"{severity_tag(f.severity)} {escape(f.title)}",
                 border_style=style, expand=False)


OUTPUT_NAMES = {
    "report": "Report", "json": "Findings JSON", "suggested_splits": "Suggested splits",
    "index": "Per-image table", "duplicates": "Duplicate clusters",
}


def short_path(path: str) -> str:
    """Relative to the current folder when it's inside it, else absolute."""
    try:
        return str(Path(path).resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def outputs_lines(report: Report) -> list[str]:
    return [f"[bold]{name}:[/bold] {short_path(report.outputs[key])}"
            for key, name in OUTPUT_NAMES.items() if key in report.outputs]


class ScanProgress:
    """Rich progress bar driven by api.run's progress(stage, done, total) callback."""

    def __init__(self, console) -> None:
        self.progress = Progress(
            SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
            MofNCompleteColumn(), TimeRemainingColumn(), console=console, transient=True,
        )
        self.task = self.progress.add_task("Starting", total=1)

    def __enter__(self) -> ScanProgress:
        self.progress.start()
        return self

    def __exit__(self, *exc) -> None:
        self.progress.stop()

    def __call__(self, stage: str, done: int, total: int) -> None:
        self.progress.update(self.task, description=stage, completed=done, total=max(total, 1))
