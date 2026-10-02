from __future__ import annotations

from rich.table import Table

from scandata.cli.context import App
from scandata.cli.navigator import NavAction
from scandata.cli.theme import BRAND
from scandata.core.config import load_history


class HistoryScreen:
    title = "Recent scans"

    def show(self, app: App) -> NavAction:
        history = load_history()
        if not history:
            app.info(
                "No scans recorded yet.\n"
                "[dim]Finished scans are listed here so you can reopen their reports.[/dim]"
            )
        else:
            table = Table(header_style=f"bold {BRAND}")
            for col in ("When", "Dataset", "Verdict", "Report"):
                table.add_column(col)
            for entry in history[:20]:
                table.add_row(*(str(entry.get(k, "")) for k in ("when", "path", "verdict", "out")))
            app.console.print(table)
        app.console.print()
        return app.menu("Recent scans", [])
