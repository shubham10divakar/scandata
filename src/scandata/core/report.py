"""The result of a scan: findings, verdict and scorecard, plus writers for Markdown and JSON."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from scandata.cli.theme import can_encode
from scandata.core.config import Config
from scandata.core.finding import Finding, Severity
from scandata.core.index import DatasetIndex
from scandata.core.options import ScanOptions
from scandata.core.registry import SECTION_ORDER

VERDICTS = {
    Severity.BLOCKER: ("NOT READY", "🔴"),
    Severity.WARN: ("READY WITH CAVEATS", "🟡"),
    Severity.INFO: ("READY", "🟢"),
}


@dataclass
class SectionScore:
    section: str
    title: str
    status: Severity
    blockers: int
    warnings: int
    info: int


@dataclass
class Report:
    all_findings: list[Finding]
    dataset: DatasetIndex
    options: ScanOptions
    config: Config
    runtime_s: float = 0.0
    fingerprint: str = ""
    created: str = ""
    versions: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    # ---- summary -----------------------------------------------------------------

    @property
    def index(self) -> pd.DataFrame:
        """Per-image table: path, label, split, group, domain and every extracted feature."""
        return self.dataset.df

    @property
    def counts(self) -> dict[Severity, int]:
        out = {s: 0 for s in Severity}
        for f in self.all_findings:
            out[f.severity] += 1
        return out

    @property
    def worst(self) -> Severity:
        return max((f.severity for f in self.all_findings), default=Severity.PASS)

    @property
    def verdict(self) -> str:
        return VERDICTS.get(self.worst, VERDICTS[Severity.INFO])[0]

    @property
    def verdict_icon(self) -> str:
        return VERDICTS.get(self.worst, VERDICTS[Severity.INFO])[1]

    def findings(
        self, severity: str | Severity | None = None, section: str | None = None
    ) -> list[Finding]:
        """Findings filtered by severity (and above, e.g. "warn" includes blockers) and section."""
        out = self.all_findings
        if severity is not None:
            floor = Severity.parse(severity)
            out = [f for f in out if f.severity >= floor]
        if section is not None:
            out = [f for f in out if f.section == section]
        return out

    def fix_first(self) -> list[Finding]:
        problems = [f for f in self.all_findings if f.severity >= Severity.WARN]
        return sorted(problems, key=lambda f: (-f.severity, SECTION_ORDER.index(f.section)))

    def scorecard(self) -> list[SectionScore]:
        rows = []
        for section in SECTION_ORDER:
            fs = [f for f in self.all_findings if f.section == section]
            if not fs:
                continue
            rows.append(SectionScore(
                section=section,
                title=section.capitalize(),
                status=max(f.severity for f in fs),
                blockers=sum(f.severity is Severity.BLOCKER for f in fs),
                warnings=sum(f.severity is Severity.WARN for f in fs),
                info=sum(f.severity is Severity.INFO for f in fs),
            ))
        return rows

    def headline(self, icons: bool = True) -> str:
        c = self.counts
        icon = self.verdict_icon if icons else f"[{self.worst.name}]"
        return (f"{icon} {self.verdict}: {c[Severity.BLOCKER]} blocker(s), "
                f"{c[Severity.WARN]} warning(s), {c[Severity.INFO]} info")

    def summary(self) -> str:
        """Print and return a plain-text summary (verdict, scorecard, top fixes)."""
        icons = can_encode("🔴🟡🟢ℹ️", getattr(sys.stdout, "encoding", None))
        df = self.dataset.df
        lines = [
            self.headline(icons),
            f"{len(df):,} images · {df['label'].nunique()} classes · "
            f"splits: {', '.join(self.dataset.splits) or 'none'}",
            "",
        ]
        for row in self.scorecard():
            mark = row.status.icon if icons else f"{row.status.name:<7}"
            lines.append(f"  {mark} {row.title:<12} blockers {row.blockers}  "
                         f"warnings {row.warnings}")
        fixes = self.fix_first()
        if fixes:
            lines += ["", "Fix these first:"]
            lines += [f"  {i}. [{f.severity.name}] {f.title}" for i, f in enumerate(fixes[:5], 1)]
        text = "\n".join(lines)
        print(text)
        return text

    # ---- writers -----------------------------------------------------------------

    def to_markdown(self, path: str | Path) -> Path:
        from scandata.report.markdown import render

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(self, path), encoding="utf-8")
        return path

    def to_json(self, path: str | Path) -> Path:
        from scandata.report.json_report import render_json

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_json(self), encoding="utf-8")
        return path
