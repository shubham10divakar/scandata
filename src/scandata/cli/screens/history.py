from __future__ import annotations

from pathlib import Path

from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Stay
from scandata.cli.prompter import Option
from scandata.core.config import load_history


class HistoryScreen:
    title = "Recent scans"

    def show(self, app: App) -> NavAction:
        history = load_history()
        if not history:
            app.info("No scans recorded yet. Finished scans are listed here so you can "
                     "reopen their reports.")
            app.console.print()
            return app.menu("Recent scans", [])
        options = []
        for i, entry in enumerate(history[:20]):
            when = str(entry.get("when", ""))[:16].replace("T", " ")
            name = Path(str(entry.get("path", ""))).name
            exists = Path(str(entry.get("out", ""))).is_file()
            options.append(Option(
                f"{when}  {name:<24}{entry.get('verdict', ''):<20}"
                f"{entry.get('blockers', 0)}B {entry.get('warnings', 0)}W",
                i, disabled=None if exists else "report file moved or deleted",
            ))
        choice = app.menu("Open a report", options)
        if isinstance(choice, NavAction):
            return choice
        try:
            app.opener(history[choice]["out"])
        except OSError as exc:
            app.info(f"Couldn't open the report: {exc}", style="red")
            app.prompter.pause()
        return Stay()
