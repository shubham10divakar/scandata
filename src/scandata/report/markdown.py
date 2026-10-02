"""Markdown report (design doc §7). Assets are linked relatively so it renders on GitHub,
VS Code and Obsidian."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from scandata.checks.catalog import SECTIONS
from scandata.checks.image_cls._util import counts_table, md_table
from scandata.core.finding import Finding, Severity
from scandata.core.registry import SECTION_ORDER

if TYPE_CHECKING:
    from scandata.core.report import Report


def assets_dir_for(report_path: Path) -> Path:
    stem = report_path.stem
    name = f"{stem}_assets" if stem.endswith("report") else f"{stem}_report_assets"
    return report_path.with_name(name)


def _rel(target: str | Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(target, base)).as_posix()
    except ValueError:  # different drive on Windows
        return Path(target).as_posix()


def _finding(f: Finding, assets_rel: str | None) -> str:
    out = [f"### {f.severity.icon} [{f.severity.name}] {f.title}", f"`{f.check_id}`", ""]
    shown = {k: v for k, v in f.metric.items() if not isinstance(v, (dict, list)) and k != "skipped"}
    if shown:
        out += [md_table(["metric", "value"], shown.items()), ""]
    if f.details:
        out += [f.details, ""]
    if f.assets and assets_rel:
        out += [f"![{f.check_id}]({assets_rel}/{a})" for a in f.assets] + [""]
    if f.evidence:
        out += ["<details><summary>Examples</summary>", "", "```"]
        out += f.evidence
        out += ["```", "", "</details>", ""]
    if f.fix:
        out += [f"**Fix:** {f.fix}", ""]
    return "\n".join(out)


def render(report: Report, path: Path) -> str:
    ds = report.dataset
    df = ds.df
    c = report.counts
    assets = assets_dir_for(path)
    assets_rel = _rel(assets, path.parent) if assets.is_dir() else None
    o = report.options

    n_domains = ds.df["domain"].nunique()
    lines = [
        f"# ScanData report: {ds.root.name}",
        "",
        f"## {report.verdict_icon} {report.verdict}",
        f"**{c[Severity.BLOCKER]} blocker(s), {c[Severity.WARN]} warning(s), "
        f"{c[Severity.INFO]} info**",
        "",
        f"Scanned {len(df):,} images · {df['label'].nunique()} classes · "
        + (f"{n_domains} domains · " if n_domains else "")
        + f"layout: {ds.layout} · "
        f"splits: {', '.join(ds.splits) or 'none'} · mode={o.mode} · "
        f"scandata {report.versions.get('scandata', '')} · seed {o.seed}",
        "",
        f"Dataset fingerprint: `{report.fingerprint[:12]}…{report.fingerprint[-4:]}` "
        "(sha256 of sorted file hashes)",
        "",
        "## Scorecard",
        "",
        md_table(["Section", "Status", "Blockers", "Warnings"],
                 [[r.title, r.status.icon, r.blockers, r.warnings] for r in report.scorecard()]),
        "",
    ]

    fixes = report.fix_first()
    if fixes:
        lines += ["## Fix these first", ""]
        for i, f in enumerate(fixes, 1):
            lines.append(f"{i}. **[{f.severity.name}] {f.title}**" + (f": {f.fix}" if f.fix else ""))
        lines.append("")

    if report.outputs.get("suggested_splits"):
        lines += [
            f"> A group-aware, stratified, duplicate-safe split was written to "
            f"`{_rel(report.outputs['suggested_splits'], path.parent)}`.",
            "",
        ]

    for section in SECTION_ORDER:
        fs = report.findings(section=section)
        if not fs:
            continue
        lines += [f"## {SECTIONS[section]}", ""]
        problems = [f for f in fs if f.severity >= Severity.INFO]
        passes = [f for f in fs if f.severity is Severity.PASS]
        for f in sorted(problems, key=lambda f: -f.severity):
            lines.append(_finding(f, assets_rel))
        if passes:
            lines += ["**Passed / skipped:**", ""]
            lines += [f"- 🟢 `{f.check_id}`: {f.title}" for f in passes]
            lines.append("")

    lines += [
        "## Dataset card",
        "",
        counts_table(df, by_split=True),
        "",
        f"- Layout: {ds.layout}; splits: {', '.join(ds.splits) or 'none'}",
        f"- Readable images: {int(df['readable'].sum()):,} of {len(df):,}",
    ]
    readable = ds.readable
    if not readable.empty:
        lines.append(
            f"- Resolution: median {int(readable.width.median())}x{int(readable.height.median())}, "
            f"range {int(readable.width.min())}x{int(readable.height.min())} to "
            f"{int(readable.width.max())}x{int(readable.height.max())}"
        )
    norm = next((f for f in report.all_findings if f.check_id == "qual.normalization"), None)
    if norm:
        mean = ", ".join(f"{v:.4f}" for v in norm.metric["mean"])
        std = ", ".join(f"{v:.4f}" for v in norm.metric["std"])
        lines.append(f"- Normalisation (RGB, 0-1): mean [{mean}], std [{std}]")
    lines.append("")

    t = report.config.thresholds
    lines += [
        "## Reproducibility",
        "",
        f"- Command: `{o.to_command()}`",
        f"- Created: {report.created} · runtime {report.runtime_s:.1f} s",
        "- Versions: " + ", ".join(f"{k} {v}" for k, v in report.versions.items()),
        f"- Disabled checks: {', '.join(sorted(report.config.disabled)) or 'none'}",
        "",
        "<details><summary>Effective thresholds</summary>",
        "",
        md_table(["threshold", "value"], t.items()),
        "",
        "</details>",
        "",
    ]
    if report.errors:
        lines += ["## Check errors", ""] + [f"- {e}" for e in report.errors] + [""]
    lines += ["---", "Generated by [ScanData](https://github.com/shubham10divakar/scandata)."]
    return "\n".join(lines) + "\n"
