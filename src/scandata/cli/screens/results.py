from __future__ import annotations

from scandata.checks.catalog import SECTIONS
from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Push, Replace, Stay
from scandata.cli.prompter import Option
from scandata.cli.views import finding_panel, outputs_lines, scorecard_table, verdict_panel
from scandata.core.finding import Finding, Severity
from scandata.core.registry import SECTION_ORDER


class ResultsScreen:
    title = "Results"

    def show(self, app: App) -> NavAction:
        report = app.last_report
        if report is None:
            app.info("No scan has run in this session yet.")
            app.console.print()
            choice = app.menu("Next", [Option("Scan a dataset ▸", "scan")])
            if isinstance(choice, NavAction):
                return choice
            from scandata.cli.screens.scan_wizard import ScanWizard

            return Replace(ScanWizard())

        c = app.console
        c.print(verdict_panel(report))
        c.print(scorecard_table(report))
        for line in outputs_lines(report):
            c.print(line)
        c.print()
        fixes = report.fix_first()
        options = [
            Option(f"Fix these first ({len(fixes)}) ▸", "fix",
                   disabled=None if fixes else "nothing to fix"),
            Option("Browse findings by section ▸", "browse"),
            Option("Open the Markdown report", "open",
                   disabled=None if "report" in report.outputs else "no report file written"),
        ]
        choice = app.menu("Results", options, default="fix" if fixes else "browse")
        if isinstance(choice, NavAction):
            return choice
        if choice == "fix":
            return Push(FindingList("Fix these first", fixes))
        if choice == "browse":
            return Push(SectionPicker())
        if choice == "open":
            try:
                app.opener(report.outputs["report"])
            except OSError as exc:
                app.info(f"Couldn't open the report: {exc}", style="red")
                app.prompter.pause()
        return Stay()


class SectionPicker:
    title = "Findings by section"

    def show(self, app: App) -> NavAction:
        report = app.last_report
        rows = {r.section: r for r in report.scorecard()}
        options = []
        for section in SECTION_ORDER:
            if section not in rows:
                continue
            r = rows[section]
            label = (f"{SECTIONS[section]:<36}{r.status.name:<8} "
                     f"{r.blockers} blocker(s), {r.warnings} warning(s)")
            options.append(Option(label, section))
        choice = app.menu("Pick a section", options)
        if isinstance(choice, NavAction):
            return choice
        findings = sorted(report.findings(section=choice), key=lambda f: -f.severity)
        return Push(FindingList(SECTIONS[choice], findings))


class FindingList:
    def __init__(self, title: str, findings: list[Finding]) -> None:
        self.title = title
        self.findings = findings

    def show(self, app: App) -> NavAction:
        options = [
            Option(f"{f.severity.name:<8}{f.title}", i)
            for i, f in enumerate(self.findings)
        ]
        if not options:
            app.info("No findings here.")
        choice = app.menu("Pick a finding", options)
        if isinstance(choice, NavAction):
            return choice
        return Push(FindingDetail(self.findings, choice))


class FindingDetail:
    def __init__(self, findings: list[Finding], index: int) -> None:
        self.findings = findings
        self.index = index
        self.title = findings[index].check_id

    def show(self, app: App) -> NavAction:
        f = self.findings[self.index]
        app.console.print(finding_panel(f, max_examples=app.last_report.config.max_examples))
        if f.severity is Severity.PASS and not f.fix:
            app.console.print("[dim]Nothing to do here.[/dim]")
        app.console.print()
        options = []
        if self.index + 1 < len(self.findings):
            options.append(Option("Next finding ▸", "next"))
        if self.index > 0:
            options.append(Option("◂ Previous finding", "prev"))
        choice = app.menu("Navigate", options, default="next")
        if isinstance(choice, NavAction):
            return choice
        step = 1 if choice == "next" else -1
        return Replace(FindingDetail(self.findings, self.index + step))

