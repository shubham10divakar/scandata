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


def test_python_api_reports_engine_pending(tmp_path):
    with pytest.raises(NotImplementedError):
        scandata.scan(tmp_path, type="image-cls")


def test_catalog_is_consistent():
    checks = list_checks()
    ids = [c.id for c in checks]
    assert len(ids) == len(set(ids))
    assert {c.section for c in checks} == set(SECTIONS)
    assert get_check("lab.suspected_mislabel").deep_only
    assert get_check("nope") is None
