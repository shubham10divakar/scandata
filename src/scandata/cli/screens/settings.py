from __future__ import annotations

from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Push, Stay
from scandata.cli.prompter import Option
from scandata.cli.screens.validators import is_dir
from scandata.cli.theme import make_console
from scandata.cli.views import thresholds_table
from scandata.core.config import Settings, home_dir


class SettingsScreen:
    title = "Settings"

    def show(self, app: App) -> NavAction:
        s = app.settings
        app.console.print(f"[dim]Saved to {home_dir() / 'settings.json'}[/dim]\n")
        options = [
            Option(f"{'Default mode':<22}{s.default_mode}", "mode"),
            Option(f"{'Default output folder':<22}{s.default_out_dir}", "out_dir"),
            Option(f"{'Color':<22}{'on' if s.color else 'off'}", "color"),
            Option("View effective thresholds ▸", "thresholds"),
            Option("Reset to defaults", "reset"),
        ]
        choice = app.menu("Settings", options)
        if isinstance(choice, NavAction):
            return choice

        if choice == "thresholds":
            return Push(ThresholdsScreen())
        if choice == "mode":
            value = app.prompter.select(
                "Default mode:",
                [Option("fast", "fast"), Option("deep", "deep", disabled="coming in v0.2")],
                default=s.default_mode,
            )
            if value is not None:
                s.default_mode = value
        elif choice == "out_dir":
            value = app.prompter.path(
                "Default output folder:", default=s.default_out_dir, only_directories=True,
                validate=is_dir,
            )
            if value is not None:
                s.default_out_dir = value.strip().strip('"')
        elif choice == "color":
            s.color = not s.color
            app.console = make_console(color=s.color)
        elif choice == "reset":
            if app.prompter.confirm("Reset all settings to defaults?", default=False):
                app.settings = s = Settings()
                app.console = make_console(color=s.color)
        s.save()
        app.options = app.fresh_options() if app.options.path is None else app.options
        return Stay()


class ThresholdsScreen:
    title = "Thresholds"

    def show(self, app: App) -> NavAction:
        app.console.print(thresholds_table())
        app.console.print("\n[dim]Override any of these with --config thresholds.yaml.[/dim]\n")
        return app.menu("Thresholds", [])
