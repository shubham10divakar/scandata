"""Public Python entry point. The CLI (menu and direct mode) calls `run` too."""

from __future__ import annotations

import hashlib
import platform
import time
import traceback
from collections.abc import Callable
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from threadpoolctl import threadpool_limits

from scandata.core.config import Config, append_history
from scandata.core.context import ScanContext
from scandata.core.finding import Finding, Severity
from scandata.core.options import ScanOptions
from scandata.core.registry import get_checks
from scandata.core.report import Report

# progress(stage, done, total)
Progress = Callable[[str, int, int], None]
CHECK_THREADS = 4


def _run_checks(checks, ctx: ScanContext, has_readable: bool, progress: Progress | None):
    findings: list[Finding] = []
    errors: list[str] = []
    for i, check in enumerate(checks):
        if progress:
            progress(f"Checking {check.id}", i, len(checks))
        if not has_readable and check.section != "integrity":
            continue
        try:
            findings += check.run(ctx)
        except Exception as exc:  # one broken check must not sink the report
            errors.append(f"{check.id}: {type(exc).__name__}: {exc}")
            errors.append(traceback.format_exc(limit=3))
            findings.append(Finding(check.id, check.section, Severity.INFO,
                                    f"Check could not run: {type(exc).__name__}: {exc}"))
    return findings, errors


def scan(path: str | Path, type: str = "image-cls", write: bool = False, **kwargs) -> Report:
    """Scan a dataset folder and return a Report.

    Accepts the same options as ``scandata scan`` (see :class:`ScanOptions`). With
    ``write=True`` the Markdown report, assets and side outputs are written to ``out``.
    """
    for key in ("out", "json", "config"):
        if kwargs.get(key) is not None:
            kwargs[key] = Path(kwargs[key])
    options = ScanOptions(path=Path(path), type=type, **kwargs)
    return run(options, write=write)


def _versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for pkg in ("scandata", "numpy", "pandas", "pillow", "scikit-learn"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            pass
    return out


def _fingerprint(df) -> str:
    hashes = sorted(h for h in df.get("sha256", []) if isinstance(h, str))
    return hashlib.sha256("".join(hashes).encode()).hexdigest()


def _sample(index, n: int, seed: int):
    shuffled = index.df.sample(frac=1.0, random_state=seed)
    index.df = shuffled.groupby("label").head(n).sort_index()
    return index


def run(
    options: ScanOptions,
    write: bool = True,
    progress: Progress | None = None,
    use_cache: bool = True,
    workers: int | None = None,
) -> Report:
    from scandata.extractors import run_extractors
    from scandata.loaders import load
    from scandata.report.markdown import assets_dir_for

    options.validate()
    config = Config.load(options.config)
    started = time.perf_counter()

    if progress:
        progress("Finding images", 0, 1)
    index = load(options.path, splits=options.splits, group_regex=options.group_regex)
    if options.sample:
        index = _sample(index, options.sample, options.seed)

    def on_extract(done: int, total: int) -> None:
        if progress:
            progress("Reading images", done, total)

    run_extractors(index, options.target_size, use_cache=use_cache, workers=workers,
                   progress=on_extract)

    out = Path(options.out)
    assets_dir = assets_dir_for(out) if write else None
    ctx = ScanContext(index=index, options=options, config=config, assets_dir=assets_dir)
    checks = get_checks(options.type, options.mode, config.disabled)
    has_readable = bool(index.df["readable"].any())
    # Cap BLAS/OpenMP threads: numpy and scipy each bring an OpenBLAS pool, and on many-core
    # machines they oversubscribe (a 0.5 s probe took 27 s with 16 threads each).
    with threadpool_limits(limits=CHECK_THREADS):
        findings, errors = _run_checks(checks, ctx, has_readable, progress)
    if progress:
        progress("Checks done", len(checks), len(checks))

    report = Report(
        all_findings=findings, dataset=index, options=options, config=config,
        fingerprint=_fingerprint(index.df), created=datetime.now().isoformat(timespec="seconds"),
        versions=_versions(), errors=errors,
    )
    if write:
        _write_outputs(report, ctx, out)
    report.runtime_s = time.perf_counter() - started
    if write:
        report.outputs["report"] = str(out.resolve())
        report.to_markdown(out)
        if options.json:
            report.to_json(options.json)
        append_history({
            "when": report.created, "path": str(index.root), "verdict": report.verdict,
            "blockers": report.counts[Severity.BLOCKER], "warnings": report.counts[Severity.WARN],
            "out": str(out.resolve()),
        })
    return report


def _write_outputs(report: Report, ctx: ScanContext, out: Path) -> None:
    from scandata.splitting.group_stratified import (
        build_groups,
        suggest_splits,
        write_suggested_splits,
    )

    index = report.dataset
    options = report.options
    if options.json:
        report.outputs["json"] = str(Path(options.json).resolve())  # written after runtime is known

    # suggested splits: when no split exists, or leakage blockers were found
    leakage_blocker = any(
        f.severity is Severity.BLOCKER and f.check_id in ("leak.exact_dup", "leak.near_dup",
                                                           "leak.group", "leak.label_conflict")
        for f in report.all_findings
    )
    dups = ctx._memo.get("duplicates")
    if (not index.has_splits or leakage_blocker) and index.df["readable"].any():
        readable, dup_result = dups if dups else (index.readable, None)
        groups = build_groups(index.df, readable, dup_result)
        frame = suggest_splits(index.df, groups, seed=options.seed)
        if frame is not None:
            path = write_suggested_splits(frame, out.with_name("suggested_splits.csv"))
            report.outputs["suggested_splits"] = str(path.resolve())

    if ctx.assets_dir is not None:
        ctx.assets_dir.mkdir(parents=True, exist_ok=True)
        table = index.df.drop(columns=[c for c in ("thumb", "border") if c in index.df])
        table.to_csv(ctx.assets_dir / "index.csv", index=False)
        report.outputs["index"] = str((ctx.assets_dir / "index.csv").resolve())
        if dups and dups[1].n_components:
            readable, result = dups
            review = readable[["relpath", "label", "split"]].assign(cluster=result.component)
            review = review[review["cluster"] >= 0].sort_values("cluster")
            path = ctx.assets_dir / "review" / "duplicate_clusters.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            review.to_csv(path, index=False)
            report.outputs["duplicates"] = str(path.resolve())
