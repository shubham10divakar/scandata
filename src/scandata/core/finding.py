"""Findings and severities (design doc §4.1 and §5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    PASS = 0
    INFO = 1
    WARN = 2
    BLOCKER = 3

    @property
    def icon(self) -> str:
        return {"PASS": "🟢", "INFO": "ℹ️", "WARN": "🟡", "BLOCKER": "🔴"}[self.name]

    @property
    def style(self) -> str:
        return {"PASS": "green", "INFO": "blue", "WARN": "yellow", "BLOCKER": "red"}[self.name]

    @classmethod
    def parse(cls, value: str | Severity) -> Severity:
        return value if isinstance(value, Severity) else cls[str(value).upper()]


@dataclass
class Finding:
    check_id: str
    section: str
    severity: Severity
    title: str
    metric: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    fix: str = ""
    details: str = ""  # extra Markdown (tables, code snippets) rendered under the finding

    def to_dict(self) -> dict:
        data = asdict(self)
        data["severity"] = self.severity.name
        return data
