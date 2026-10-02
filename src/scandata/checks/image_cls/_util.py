"""Helpers shared by the image-classification checks."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

from scandata.core.context import ScanContext
from scandata.core.finding import Finding, Severity


def finding(check, severity: Severity, title: str, **kwargs) -> Finding:
    return Finding(check_id=check.id, section=check.section, severity=severity, title=title,
                   **kwargs)


def passed(check, title: str, **kwargs) -> list[Finding]:
    return [finding(check, Severity.PASS, title, **kwargs)]


def skipped(check, reason: str) -> list[Finding]:
    return [finding(check, Severity.PASS, f"Skipped: {reason}", metric={"skipped": reason})]


def pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def md_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return "\n".join(lines)


def _cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.3g}" if abs(value) < 1000 else f"{value:,.0f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return str(value).replace("|", "\\|")


def examples(df: pd.DataFrame, ctx: ScanContext, note: str | None = None) -> list[str]:
    rows = df.head(ctx.max_examples)
    if note is None:
        return rows["relpath"].tolist()
    return [f"{r.relpath}  ({getattr(r, note)})" for r in rows.itertuples()]


def held_out_split(ctx: ScanContext) -> str | None:
    """The split used for "% of test" metrics: test if present, else val."""
    held = ctx.index.held_out
    return "test" if "test" in held else (held[0] if held else None)


def counts_table(df: pd.DataFrame, by_split: bool) -> str:
    if by_split and df["split"].notna().any():
        table = pd.crosstab(df["label"], df["split"])
        order = [c for c in ("train", "val", "test") if c in table] + [
            c for c in table if c not in ("train", "val", "test")
        ]
        table = table[order]
        table["total"] = table.sum(axis=1)
        return md_table(["class", *table.columns], [[i, *r] for i, r in zip(
            table.index, table.to_numpy().tolist(), strict=True)])
    counts = df["label"].value_counts().sort_index()
    return md_table(["class", "images"], counts.items())
