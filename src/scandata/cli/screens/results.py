from __future__ import annotations

from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Replace
from scandata.cli.prompter import Option


class ResultsScreen:
    title = "Results"

    def show(self, app: App) -> NavAction:
        if app.last_report is None:
            app.info(
                "No scan has run in this session yet.\n"
                "[dim]Verdict, scorecard and findings by section will show here (v0.1).[/dim]"
            )
            app.console.print()
            choice = app.menu("Next", [Option("Scan a dataset ▸", "scan")])
            if isinstance(choice, NavAction):
                return choice
            from scandata.cli.screens.scan_wizard import ScanWizard

            return Replace(ScanWizard())

        # Phase 1: verdict + scorecard, browse findings by section, fix-first list, open report.
        app.console.print(app.last_report)
        return app.menu("Results", [])
