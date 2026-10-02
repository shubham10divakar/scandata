"""Console, colors and terminal capability fallbacks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

BRAND = "cyan"
HEART = "❤"


def make_console(color: bool = True, **kwargs) -> Console:
    no_color = not color or "NO_COLOR" in os.environ
    return Console(no_color=no_color, highlight=False, **kwargs)


def can_encode(text: str, encoding: str | None) -> bool:
    try:
        text.encode(encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def heart(console: Console) -> str:
    """Red heart, or `<3` when the terminal's encoding can't show it (old cmd.exe code pages)."""
    symbol = HEART if can_encode(HEART, console.encoding) else "<3"
    return f"[red]{symbol}[/red]"


def symbol(console: Console, fancy: str, plain: str) -> str:
    return fancy if can_encode(fancy, console.encoding) else plain


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def open_path(path: str | Path) -> None:
    """Open a file with the OS default app."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
