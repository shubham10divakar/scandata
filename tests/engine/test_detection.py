"""Every injected defect must be found, and clean data must not raise false alarms."""

import pandas as pd
import pytest

import scandata
from scandata.core.finding import Severity


def by_check(report):
    out = {}
    for f in report.all_findings:
        out.setdefault(f.check_id, []).append(f)
    return out


def worst(findings):
    return max(f.severity for f in findings)


@pytest.fixture(scope="module")
def defect_report(defect_ds, tmp_path_factory):
    root, injected = defect_ds
    out = tmp_path_factory.mktemp("defect_out") / "scandata_report.md"
    return scandata.scan(root, write=True, out=out, target_size=64), injected, out


def test_no_check_crashes(defect_report):
    report, _, _ = defect_report
    assert report.errors == []


@pytest.mark.parametrize("check_id, severity, key", [
    ("int.unreadable", Severity.BLOCKER, "unreadable"),
    ("int.format_mismatch", Severity.WARN, "format_mismatch"),
    ("int.exif_rotation", Severity.WARN, "exif_rotation"),
    ("int.blank", Severity.WARN, "blank"),
    ("int.tiny", Severity.WARN, "tiny"),
    ("int.non_image", Severity.INFO, "non_image"),
])
def test_integrity_defects_found(defect_report, check_id, severity, key):
    report, injected, _ = defect_report
    fs = by_check(report)[check_id]
    assert worst(fs) == severity
    evidence = " ".join(e for f in fs for e in f.evidence)
    for path in injected[key]:
        assert path in evidence


def test_leakage_defects_found(defect_report):
    report, injected, _ = defect_report
    checks = by_check(report)
    assert worst(checks["leak.exact_dup"]) == Severity.BLOCKER
    assert worst(checks["leak.near_dup"]) == Severity.BLOCKER
    assert worst(checks["leak.label_conflict"]) == Severity.BLOCKER
    near = " ".join(checks["leak.near_dup"][0].evidence)
    assert injected["near_cross"][0] in near
    conflict = " ".join(checks["leak.label_conflict"][0].evidence)
    assert injected["label_conflict"][0] in conflict


def test_outputs_written(defect_report):
    report, _, out = defect_report
    assert report.verdict == "NOT READY"
    assets = out.parent / "scandata_report_assets"
    assert (assets / "index.csv").is_file()
    assert (assets / "leak_near_dup.png").is_file()
    assert (assets / "review" / "duplicate_clusters.csv").is_file()
    # leakage blockers -> a safe re-split is suggested; duplicate clusters stay together
    splits = pd.read_csv(out.parent / "suggested_splits.csv")
    assert set(splits["split"]) == {"train", "val", "test"}
    clusters = pd.read_csv(assets / "review" / "duplicate_clusters.csv")
    merged = clusters.merge(splits, left_on="relpath", right_on="path", suffixes=("", "_new"))
    assert (merged.groupby("cluster")["split_new"].nunique() == 1).all()
    text = out.read_text(encoding="utf-8")
    assert "NOT READY" in text and "## Scorecard" in text and "suggested_splits.csv" in text


def test_clean_dataset_has_no_false_alarms(clean_ds):
    report = scandata.scan(clean_ds)
    assert report.errors == []
    assert report.findings(severity="blocker") == []
    noisy = [f for f in report.findings(severity="warn")
             if f.section in ("integrity", "leakage", "shortcuts")]
    assert noisy == [], [f.title for f in noisy]


def test_planted_shortcuts_found(shortcut_ds, tmp_path):
    report = scandata.scan(shortcut_ds, write=True, out=tmp_path / "scandata_report.md")
    checks = by_check(report)
    assert worst(checks["short.metadata"]) >= Severity.WARN
    assert worst(checks["short.border"]) == Severity.BLOCKER
    assert worst(checks["short.filename"]) == Severity.PASS  # same naming in both classes
    assert worst(checks["leak.no_test_split"]) == Severity.INFO
    assert (tmp_path / "suggested_splits.csv").is_file()


def test_declared_group_leak_is_a_blocker(tmp_path):
    import synthetic

    root = synthetic.make_clean(tmp_path / "ds", per_class=30, splits=False)
    rows = []
    for i, p in enumerate(sorted(root.rglob("*.jpg"))):
        split = "test" if i % 5 == 0 else "train"
        rows.append({"path": p.relative_to(root).as_posix(), "label": p.parent.name,
                     "split": split, "group": f"src{i // 3}"})  # groups of 3 straddle splits
    pd.DataFrame(rows).to_csv(root / "labels.csv", index=False)
    report = scandata.scan(root)
    assert report.dataset.layout == "manifest"
    group = by_check(report)["leak.group"]
    assert worst(group) == Severity.BLOCKER


def test_cache_skips_unchanged_files(clean_ds):
    from scandata.extractors import run_extractors
    from scandata.loaders import load

    run_extractors(load(clean_ds))
    seen = []
    run_extractors(load(clean_ds), progress=lambda done, total: seen.append((done, total)))
    assert seen[0][0] == seen[0][1] == 80  # everything came from the cache


def test_resize_risk_passes_when_detail_survives(clean_ds):
    # regression: an empty flagged set used to resurrect every row via .assign()
    report = scandata.scan(clean_ds, target_size=96)
    resize = by_check(report)["qual.resize_risk"]
    assert worst(resize) == Severity.PASS
    assert report.errors == []
