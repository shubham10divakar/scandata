"""Public Python entry point. The CLI (menu and direct mode) calls this too."""

from __future__ import annotations

from pathlib import Path

from scandata.core.options import ScanOptions


class EngineNotReadyError(NotImplementedError):
    """Raised while the scan engine is still being built (Phase 0)."""


def scan(path: str | Path, type: str = "image-cls", **kwargs) -> None:
    """Scan a dataset folder and return a report.

    Accepts the same options as ``scandata scan`` (see :class:`ScanOptions`).
    """
    options = ScanOptions(path=Path(path), type=type, **kwargs)
    return run(options)


def run(options: ScanOptions) -> None:
    options.validate()
    raise EngineNotReadyError(
        "The scan engine arrives in v0.1 (Phase 1). "
        "The CLI shell, options and check catalog are ready."
    )
