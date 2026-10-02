"""Machine-readable findings for CI (findings.json)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from scandata.core.report import Report


def _default(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def render_json(report: Report) -> str:
    df = report.dataset.df
    data = {
        "verdict": report.verdict,
        "counts": {s.name: n for s, n in report.counts.items()},
        "dataset": {
            "root": str(report.dataset.root),
            "images": len(df),
            "classes": sorted(df["label"].dropna().unique().tolist()),
            "splits": report.dataset.splits,
            "layout": report.dataset.layout,
            "fingerprint": report.fingerprint,
        },
        "scorecard": [
            {"section": r.section, "status": r.status.name, "blockers": r.blockers,
             "warnings": r.warnings}
            for r in report.scorecard()
        ],
        "findings": [f.to_dict() for f in report.all_findings],
        "command": report.options.to_command(),
        "thresholds": report.config.thresholds,
        "versions": report.versions,
        "runtime_s": round(report.runtime_s, 2),
        "created": report.created,
        "errors": report.errors,
    }
    return json.dumps(data, indent=2, default=_default)
