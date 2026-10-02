from typer.testing import CliRunner

from scandata import __version__
from scandata.cli.app import EXIT_TOOL_ERROR, app

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


def test_scan_validates_and_reports_engine_pending(tmp_path):
    missing = runner.invoke(app, ["scan", str(tmp_path / "nope"), "--type", "image-cls"])
    assert missing.exit_code == EXIT_TOOL_ERROR
    assert "Not a folder" in missing.output

    pending = runner.invoke(app, ["scan", str(tmp_path), "--type", "image-cls", "-q"])
    assert pending.exit_code == EXIT_TOOL_ERROR
    assert "Not built yet" in pending.output


def test_scan_rejects_disabled_type(tmp_path):
    result = runner.invoke(app, ["scan", str(tmp_path), "--type", "tabular", "-q"])
    assert result.exit_code == EXIT_TOOL_ERROR
    assert "coming in v0.6" in result.output
