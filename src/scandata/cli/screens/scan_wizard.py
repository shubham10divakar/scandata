"""Scan wizard: a hub of fields you can edit in any order, then review and run."""

from __future__ import annotations

from pathlib import Path

from scandata import api
from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Pop, Push, Replace, Stay
from scandata.cli.prompter import Option
from scandata.cli.screens.advanced import AdvancedOptions
from scandata.cli.screens.validators import is_dir, not_blank
from scandata.cli.views import ScanProgress, command_panel, options_table
from scandata.core.config import ConfigError
from scandata.core.options import DATA_TYPES, OptionsError
from scandata.loaders.image_folder import LoaderError


def field(name: str, value: object) -> str:
    return f"{name:<18}{value}"


class ScanWizard:
    title = "Scan a dataset"

    def show(self, app: App) -> NavAction:
        o = app.options
        app.console.print("[dim]Pick a field to edit. Choices are kept when you go back.[/dim]\n")
        options = [
            Option(field("Dataset folder", o.path or "(not set)"), "path"),
            Option(field("Data type", o.type), "type"),
            Option(field("Mode", o.mode), "mode"),
            Option(field("Output report", o.out), "out"),
            Option("Advanced options ▸", "advanced"),
            Option.sep(),
            Option(
                "Review & run ▸",
                "review",
                disabled=None if o.path else "choose a dataset folder first",
            ),
        ]
        choice = app.menu("Scan settings", options, default="review" if o.path else "path")
        if isinstance(choice, NavAction):
            return choice

        if choice == "path":
            value = app.prompter.path(
                "Dataset folder:", default=str(o.path or ""), only_directories=True,
                validate=is_dir,
            )
            if value is not None:
                o.path = Path(value.strip().strip('"')).expanduser()
        elif choice == "type":
            value = app.prompter.select(
                "Data type:",
                [Option(t, t, disabled=reason) for t, reason in DATA_TYPES.items()],
                default=o.type,
            )
            if value is not None:
                o.type = value
        elif choice == "mode":
            value = app.prompter.select(
                "Mode:",
                [
                    Option("fast  hashes and pixel stats, CPU, minutes", "fast"),
                    Option("deep  adds embeddings and mislabel detection", "deep",
                           disabled="coming in v0.2"),
                ],
                default=o.mode,
            )
            if value is not None:
                o.mode = value
        elif choice == "out":
            value = app.prompter.text("Report path (.md):", default=str(o.out), validate=not_blank)
            if value is not None:
                o.out = Path(value.strip())
        elif choice == "advanced":
            return Push(AdvancedOptions())
        elif choice == "review":
            return Push(ReviewScreen())
        return Stay()


class ReviewScreen:
    title = "Review & run"

    def show(self, app: App) -> NavAction:
        app.console.print(options_table(app.options))
        app.console.print()
        app.console.print(command_panel(app.options))
        app.console.print()
        choice = app.menu(
            "Ready?",
            [Option("▶ Run scan", "run"), Option("✎ Edit options", "edit")],
            default="run",
        )
        if isinstance(choice, NavAction):
            return choice
        if choice == "edit":
            return Pop()

        try:
            with ScanProgress(app.console) as progress:
                app.last_report = api.run(app.options, progress=progress)
        except (OptionsError, LoaderError, ConfigError) as exc:
            app.info(str(exc), style="red", title="Can't run the scan")
            app.prompter.pause()
            return Stay()
        from scandata.cli.screens.results import ResultsScreen

        return Replace(ResultsScreen())
