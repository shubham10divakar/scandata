"""The interactive app: shared state across screens and the main loop."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from scandata.cli.banner import credit, render_banner
from scandata.cli.navigator import Exit, Home, NavAction, Navigator, Pop, Screen, Stay
from scandata.cli.prompter import Option, Prompter
from scandata.cli.theme import BRAND, make_console, open_path, symbol
from scandata.core.config import Settings
from scandata.core.options import DEFAULT_OUT, ScanOptions

BACK = "__back__"
HOME = "__home__"


class App:
    def __init__(
        self,
        prompter: Prompter,
        console: Console | None = None,
        settings: Settings | None = None,
        clear: bool = True,
        debug: bool = False,
    ) -> None:
        self.settings = settings or Settings.load()
        self.console = console or make_console(color=self.settings.color)
        self.prompter = prompter
        self.clear = clear
        self.debug = debug
        self.options = self.fresh_options()
        self.last_report: Any = None  # Report from the most recent scan
        self.nav: Navigator | None = None
        self.opener = open_path  # opens files with the OS default app (swappable in tests)

    def fresh_options(self) -> ScanOptions:
        return ScanOptions(
            mode=self.settings.default_mode,
            out=Path(self.settings.default_out_dir) / DEFAULT_OUT,
        )

    # ---- helpers for screens -------------------------------------------------

    def menu(self, message: str, options: list[Option], default: Any = None) -> Any:
        """Select with Back / Main menu appended. Returns a NavAction or the chosen value."""
        assert self.nav is not None
        back = Option(symbol(self.console, "← Back", "< Back"), BACK)
        items = [*options, Option.sep(), back]
        if self.nav.depth > 2:
            items.append(Option(symbol(self.console, "⌂ Main menu", "Main menu"), HOME))
        value = self.prompter.select(message, items, default=default)
        if value is None or value == BACK:
            return Pop()
        if value == HOME:
            return Home()
        return value

    def info(self, message: str, style: str = BRAND, title: str | None = None) -> None:
        self.console.print(Panel(message, border_style=style, title=title, expand=False))

    # ---- main loop -------------------------------------------------------------

    def _header(self, screen: Screen) -> None:
        assert self.nav is not None
        if self.clear:
            self.console.clear()
        if self.nav.depth == 1:
            render_banner(self.console)
        else:
            self.console.rule(f"[bold {BRAND}]{self.nav.breadcrumb}", align="left")
        self.console.print()

    def run(self, root: Screen) -> None:
        self.nav = Navigator(root)
        while self.nav.running:
            screen = self.nav.current
            self._header(screen)
            try:
                action: NavAction = screen.show(self)
            except KeyboardInterrupt:
                action = Pop() if self.nav.depth > 1 else Exit()
            except Exception as exc:  # keep the menu alive; show the error
                detail = traceback.format_exc() if self.debug else f"{type(exc).__name__}: {exc}"
                self.info(detail, style="red", title="Something went wrong")
                if not self.debug:
                    self.console.print("[dim]Run with --debug for the full traceback.[/dim]")
                self.prompter.pause()
                action = Pop() if self.nav.depth > 1 else Exit()
            self.nav.apply(action if action is not None else Stay())
        self.console.print(f"\nThanks for using ScanData. {credit(self.console)}\n")
