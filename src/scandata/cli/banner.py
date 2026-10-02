"""Welcome banner and credit line."""

from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from scandata import __version__
from scandata.cli.theme import BRAND, heart

LOGO = r"""
   ____                  ____        _
  / ___|  ___ __ _ _ __ |  _ \  __ _| |_ __ _
  \___ \ / __/ _` | '_ \| | | |/ _` | __/ _` |
   ___) | (_| (_| | | | | |_| | (_| | || (_| |
  |____/ \___\__,_|_| |_|____/ \__,_|\__\__,_|
""".strip("\n")

TAGLINE = "audit your dataset before you train on it"
AUTHOR = "Subham Divakar"


def credit(console: Console) -> str:
    return f"Built with {heart(console)} by [bold]{AUTHOR}[/bold]"


def render_banner(console: Console) -> None:
    body = Group(
        Text(LOGO, style=f"bold {BRAND}"),
        Text(""),
        Text.from_markup(f"[bold]ScanData[/bold] v{__version__} · {TAGLINE}"),
        Text.from_markup(credit(console)),
    )
    console.print(Panel(Align.left(body), border_style=BRAND, padding=(0, 2), expand=False))


def render_compact(console: Console) -> None:
    console.print(
        f"[bold {BRAND}]ScanData[/bold {BRAND}] v{__version__} · {credit(console)}"
    )
