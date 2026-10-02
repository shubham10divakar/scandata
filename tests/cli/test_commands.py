import json

from typer.testing import CliRunner

from scandata import __version__
from scandata.cli.app import EXIT_FAIL_ON, EXIT_TOOL_ERROR, app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_no_args_without_tty_prints_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in result.output and "scan" in result.output


def test_list_checks_and_section_filter():
    result = runner.invoke(app, ["list-checks", "--section", "shortcuts"])
    assert result.exit_code == 0
    assert "short.border" in result.output
    assert "leak.near_dup" not in result.output


def test_explain_known_and_unknown():
    ok = runner.invoke(app, ["explain", "leak.near_dup"])
    assert ok.exit_code == 0 and "pHash" in ok.output

    bad = runner.invoke(app, ["explain", "leak.neardup"])
    assert bad.exit_code == EXIT_TOOL_ERROR
    assert "leak.near_dup" in bad.output


def test_scan_input_errors_exit_2(tmp_path):
    missing = runner.invoke(app, ["scan", str(tmp_path / "nope"), "--type", "image-cls"])
    assert missing.exit_code == EXIT_TOOL_ERROR
    assert "Not a folder" in missing.output

    empty = runner.invoke(app, ["scan", str(tmp_path), "--type", "image-cls", "-q"])
    assert empty.exit_code == EXIT_TOOL_ERROR
    assert "No images found" in empty.output

    deep = runner.invoke(app, ["scan", str(tmp_path), "--type", "image-cls", "--mode", "deep"])
    assert deep.exit_code == EXIT_TOOL_ERROR
    assert "v0.2" in deep.output


def test_scan_writes_report_and_json(clean_ds, tmp_path):
    out = tmp_path / "r" / "scandata_report.md"
    js = tmp_path / "r" / "findings.json"
    result = runner.invoke(app, ["scan", str(clean_ds), "--type", "image-cls", "-q",
                                 "--out", str(out), "--json", str(js)])
    assert result.exit_code == 0, result.output
    assert out.is_file() and js.is_file()
    assert "Verdict" in result.output
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["dataset"]["images"] == 80
    assert data["counts"]["BLOCKER"] == 0


def test_fail_on_blocker_exits_1(defect_ds, tmp_path):
    root, _ = defect_ds
    out = tmp_path / "scandata_report.md"
    result = runner.invoke(app, ["scan", str(root), "--type", "image-cls", "-q",
                                 "--out", str(out), "--fail-on", "blocker"])
    assert result.exit_code == EXIT_FAIL_ON, result.output
    assert "NOT READY" in result.output


def test_scan_rejects_disabled_type(tmp_path):
    result = runner.invoke(app, ["scan", str(tmp_path), "--type", "tabular", "-q"])
    assert result.exit_code == EXIT_TOOL_ERROR
    assert "coming in v0.6" in result.output
