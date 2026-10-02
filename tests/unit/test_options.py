from pathlib import Path

import pytest

import scandata
from scandata.checks.catalog import SECTIONS, get_check, list_checks
from scandata.core.options import OptionsError, ScanOptions


def test_to_command_only_includes_non_defaults():
    o = ScanOptions(path=Path("data"), target_size=224, group_regex="^(?P<group>\\d+)_")
    cmd = o.to_command()
    assert cmd.startswith("scandata scan data --type image-cls")
    assert "--target-size 224" in cmd
    assert "--mode" not in cmd and "--seed" not in cmd
    assert "'^(?P<group>\\d+)_'" in cmd


def test_validate(tmp_path):
    ScanOptions(path=tmp_path).validate()
    with pytest.raises(OptionsError):
        ScanOptions().validate()
    with pytest.raises(OptionsError):
        ScanOptions(path=tmp_path, mode="turbo").validate()


def test_python_api_returns_report_without_writing(clean_ds, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = scandata.scan(clean_ds, type="image-cls")
    assert report.verdict in ("READY", "READY WITH CAVEATS")
    assert len(report.index) == 80
    assert not (tmp_path / "scandata_report.md").exists()
    assert report.findings(severity="blocker") == []
    path = report.to_markdown(tmp_path / "r.md")
    assert "# ScanData report" in path.read_text(encoding="utf-8")


def test_deep_mode_is_not_available_yet(tmp_path):
    with pytest.raises(OptionsError, match="v0.2"):
        ScanOptions(path=tmp_path, mode="deep").validate()


def test_registry_matches_catalog():
    from scandata.core.registry import all_checks

    registered = all_checks()
    catalog = {c.id: c for c in list_checks()}
    assert set(registered) <= set(catalog)
    fast_planned = {cid for cid, c in catalog.items() if not c.deep_only}
    assert fast_planned == set(registered), fast_planned ^ set(registered)
    for cid, cls in registered.items():
        assert cls.section == catalog[cid].section


def test_catalog_is_consistent():
    checks = list_checks()
    ids = [c.id for c in checks]
    assert len(ids) == len(set(ids))
    assert {c.section for c in checks} == set(SECTIONS)
    assert get_check("lab.suspected_mislabel").deep_only
    assert get_check("nope") is None
