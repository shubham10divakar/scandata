from __future__ import annotations

from scandata.cli.context import App
from scandata.cli.navigator import Exit, NavAction, Push, Stay
from scandata.cli.prompter import Option
from scandata.cli.screens.checks_browser import ChecksBrowser
from scandata.cli.screens.help import HelpScreen
from scandata.cli.screens.history import HistoryScreen
from scandata.cli.screens.results import ResultsScreen
from scandata.cli.screens.scan_wizard import ScanWizard
from scandata.cli.screens.settings import SettingsScreen

ITEMS = [
    ("1. Scan a dataset", ScanWizard),
    ("2. Results (last scan)", ResultsScreen),
    ("3. Browse checks", ChecksBrowser),
    ("4. Recent scans", HistoryScreen),
    ("5. Settings", SettingsScreen),
    ("6. Help & about", HelpScreen),
]


class MainMenu:
    title = "ScanData"

    def show(self, app: App) -> NavAction:
        options = [Option(label, cls) for label, cls in ITEMS]
        options += [Option.sep(), Option("0. Exit", "exit")]
        choice = app.prompter.select("What would you like to do?", options)
        if choice == "exit":
            return Exit()
        if choice is None:  # Esc / Ctrl+C on the main menu
            return Exit() if app.prompter.confirm("Exit ScanData?", default=False) else Stay()
        return Push(choice())
