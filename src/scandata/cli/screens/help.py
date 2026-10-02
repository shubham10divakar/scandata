from __future__ import annotations

from rich.table import Table

from scandata import __version__
from scandata.cli.banner import credit
from scandata.cli.context import App
from scandata.cli.navigator import NavAction
from scandata.cli.theme import BRAND

KEYS = [
    ("↑ / ↓", "move"),
    ("Enter", "select"),
    ("Esc or Ctrl+C", "back one screen"),
    ("← Back / ⌂ Main menu", "at the bottom of every screen"),
]
COMMANDS = [
    ("scandata", "this menu"),
    ("scandata scan ./data --type image-cls", "scan without the menu (scripts, CI)"),
    ("scandata list-checks", "all checks in a table"),
    ("scandata explain leak.near_dup", "what one check does and why"),
    ("scandata --help", "every flag"),
]


def _grid(rows: list[tuple[str, str]]) -> Table:
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style=f"bold {BRAND}", no_wrap=True)
    grid.add_column()
    for row in rows:
        grid.add_row(*row)
    return grid


class HelpScreen:
    title = "Help & about"

    def show(self, app: App) -> NavAction:
        c = app.console
        c.print("[bold]Keys[/bold]")
        c.print(_grid(KEYS))
        c.print("\n[bold]Commands[/bold]")
        c.print(_grid(COMMANDS))
        c.print(
            f"\n[bold]About[/bold]\nScanData v{__version__} · MIT license\n"
            "Audits a dataset for leakage, label problems, shortcuts and quality issues "
            "before you train on it.\n"
            f"{credit(c)}\n"
        )
        return app.menu("Help", [])
