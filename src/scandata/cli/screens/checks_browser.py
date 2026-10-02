from __future__ import annotations

from scandata.checks.catalog import SECTION_WHY, SECTIONS, CheckInfo, list_checks
from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Push, Replace
from scandata.cli.prompter import Option
from scandata.cli.views import check_panel


class ChecksBrowser:
    title = "Browse checks"

    def show(self, app: App) -> NavAction:
        app.console.print("[dim]Data type: image-cls[/dim]\n")
        options = [
            Option(f"{name:<36}{len(list_checks(section=key))} checks", key)
            for key, name in SECTIONS.items()
        ]
        choice = app.menu("Pick a section", options)
        if isinstance(choice, NavAction):
            return choice
        return Push(SectionChecks(choice))


class SectionChecks:
    def __init__(self, section: str) -> None:
        self.section = section
        self.title = SECTIONS[section]

    def show(self, app: App) -> NavAction:
        app.console.print(f"[italic]{SECTION_WHY[self.section]}[/italic]\n")
        checks = list_checks(section=self.section)
        options = [
            Option(f"{c.id:<24}{c.title}{'  (deep)' if c.deep_only else ''}", i)
            for i, c in enumerate(checks)
        ]
        choice = app.menu("Pick a check", options)
        if isinstance(choice, NavAction):
            return choice
        return Push(CheckDetail(checks, choice))


class CheckDetail:
    def __init__(self, checks: list[CheckInfo], index: int) -> None:
        self.checks = checks
        self.index = index
        self.title = checks[index].id

    def show(self, app: App) -> NavAction:
        app.console.print(check_panel(self.checks[self.index]))
        app.console.print()
        options = []
        if self.index + 1 < len(self.checks):
            options.append(Option(f"Next: {self.checks[self.index + 1].id} ▸", "next"))
        if self.index > 0:
            options.append(Option(f"◂ Previous: {self.checks[self.index - 1].id}", "prev"))
        choice = app.menu("Navigate", options, default="next")
        if isinstance(choice, NavAction):
            return choice
        step = 1 if choice == "next" else -1
        return Replace(CheckDetail(self.checks, self.index + step))
