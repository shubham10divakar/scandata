import io

from rich.console import Console

from scandata import __version__
from scandata.cli.banner import render_banner, render_compact


def _console(encoding: str = "utf-8") -> tuple[Console, io.StringIO]:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    console = Console(file=stream, width=100, color_system=None, legacy_windows=False)
    return console, stream


def _text(stream: io.TextIOWrapper) -> str:
    stream.flush()
    return stream.buffer.getvalue().decode(stream.encoding)


def test_banner_shows_name_version_and_credit():
    console, stream = _console()
    render_banner(console)
    text = _text(stream)
    assert "ScanData" in text
    assert __version__ in text
    assert "Built with ❤ by Subham Divakar" in text


def test_heart_falls_back_when_terminal_cannot_encode_it():
    console, stream = _console("cp1252")
    render_compact(console)
    text = _text(stream)
    assert "Built with <3 by Subham Divakar" in text
