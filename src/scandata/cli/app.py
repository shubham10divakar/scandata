"""`scandata` command: interactive menu with no arguments, direct subcommands otherwise."""

from __future__ import annotations

import difflib
from enum import Enum
from pathlib import Path

import typer

from scandata import __version__, api
from scandata.checks.catalog import SECTIONS, get_check, list_checks
from scandata.cli.banner import render_compact
from scandata.cli.theme import is_interactive, make_console
from scandata.cli.views import check_panel, checks_table, engine_pending
from scandata.core.options import DATA_TYPES, DEVICES, FAIL_ON, MODES, OptionsError, ScanOptions

DataType = Enum("DataType", {t: t for t in DATA_TYPES}, type=str)
Mode = Enum("Mode", {m: m for m in MODES}, type=str)
Device = Enum("Device", {d: d for d in DEVICES}, type=str)
FailOn = Enum("FailOn", {f: f for f in FAIL_ON}, type=str)
Section = Enum("Section", {s: s for s in SECTIONS}, type=str)


def _val(choice: Enum | None) -> str | None:
    return None if choice is None else choice.value


# Exit codes (design doc §5)
EXIT_OK, EXIT_FAIL_ON, EXIT_TOOL_ERROR = 0, 1, 2

app = typer.Typer(
    name="scandata",
    help="ScanData: audit your dataset before you train on it.\n\n"
    "Run with no arguments for the interactive menu.",
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


class State:
    def __init__(self, color: bool = True, debug: bool = False) -> None:
        self.color = color
        self.debug = debug
        self.console = make_console(color=color)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"scandata {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version, is_eager=True, help="Show version and exit."
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colors."),
    debug: bool = typer.Option(False, "--debug", help="Show full tracebacks."),
) -> None:
    ctx.obj = State(color=not no_color, debug=debug)
    if ctx.invoked_subcommand is not None:
        return
    if not is_interactive():
        typer.echo(ctx.get_help())
        raise typer.Exit(EXIT_OK)
    run_interactive(color=not no_color, debug=debug)


def run_interactive(color: bool = True, debug: bool = False) -> None:
    from scandata.cli.context import App
    from scandata.cli.prompter import QuestionaryPrompter
    from scandata.cli.screens import MainMenu
    from scandata.core.config import Settings

    settings = Settings.load()
    if not color:
        settings.color = False
    App(QuestionaryPrompter(color=settings.color), settings=settings, debug=debug).run(MainMenu())


@app.command()
def scan(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Dataset folder."),
    type: DataType = typer.Option(..., "--type", "-t", help="Data category."),
    mode: Mode = typer.Option(Mode.fast, help="fast or deep."),
    splits: str = typer.Option("auto", help="auto, none, or a manifest CSV."),
    group_regex: str | None = typer.Option(
        None, help="Regex with a named group 'group' that extracts the source ID."
    ),
    target_size: int | None = typer.Option(None, help="Training input resolution (px)."),
    sample: int | None = typer.Option(None, help="Audit only N images per class."),
    config: Path | None = typer.Option(None, help="YAML threshold overrides."),
    out: Path = typer.Option(Path("scandata_report.md"), help="Markdown report path."),
    json: Path | None = typer.Option(None, "--json", help="Write findings as JSON."),
    fail_on: FailOn | None = typer.Option(
        None, help="Exit 1 if findings at this level exist."
    ),
    seed: int = typer.Option(42, help="Seed for sampling and probes."),
    device: Device = typer.Option(Device.auto, help="Deep-mode device."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="No banner."),
) -> None:
    """Scan a dataset folder and write a report."""
    console = ctx.obj.console
    if not quiet:
        render_compact(console)
    options = ScanOptions(
        path=path, type=_val(type), mode=_val(mode), splits=splits, group_regex=group_regex,
        target_size=target_size, sample=sample, config=config, out=out, json=json,
        fail_on=_val(fail_on), seed=seed, device=_val(device),
    )
    try:
        api.run(options)
    except OptionsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(EXIT_TOOL_ERROR) from None
    except api.EngineNotReadyError:
        console.print(engine_pending(options))
        raise typer.Exit(EXIT_TOOL_ERROR) from None


@app.command("list-checks")
def list_checks_cmd(
    ctx: typer.Context,
    type: DataType = typer.Option("image-cls", "--type", "-t", help="Data category."),
    section: Section | None = typer.Option(None, "--section", "-s", help="Only one section."),
) -> None:
    """List the checks for a data type."""
    console = ctx.obj.console
    checks = list_checks(type.value, _val(section))
    if not checks:
        console.print(f"No checks for {type.value} yet ({DATA_TYPES[type.value]}).")
        return
    console.print(checks_table(checks))
    console.print(f"[dim]{len(checks)} checks · scandata explain <id> for details[/dim]")


@app.command()
def explain(
    ctx: typer.Context, check_id: str = typer.Argument(..., help="e.g. leak.near_dup")
) -> None:
    """Explain what a check does, why it matters, and its thresholds."""
    console = ctx.obj.console
    check = get_check(check_id)
    if check is None:
        all_ids = [c.id for c in list_checks()]
        close = difflib.get_close_matches(check_id, all_ids, n=3)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        console.print(f"[red]Unknown check:[/red] {check_id}.{hint}")
        raise typer.Exit(EXIT_TOOL_ERROR)
    console.print(check_panel(check))


@app.command()
def version() -> None:
    """Show the version."""
    typer.echo(f"scandata {__version__}")


def main() -> None:
    app(prog_name="scandata")
