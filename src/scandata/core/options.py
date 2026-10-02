"""Scan options shared by the interactive wizard, the direct CLI and the Python API."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

DATA_TYPES: dict[str, str | None] = {
    # type id -> None if available, else the reason it is disabled
    "image-cls": None,
    "image-det": "coming in v0.5",
    "image-seg": "coming in v0.5",
    "tabular": "coming in v0.6",
    "timeseries": "coming in v0.7",
    "text": "coming in v0.7",
}
MODES = ("fast", "deep")
DEVICES = ("auto", "cpu", "cuda", "mps")
FAIL_ON = ("blocker", "warn")
DEFAULT_OUT = "scandata_report.md"


class OptionsError(ValueError):
    pass


@dataclass
class ScanOptions:
    path: Path | None = None
    type: str = "image-cls"
    mode: str = "fast"
    splits: str = "auto"
    group_regex: str | None = None
    target_size: int | None = None
    sample: int | None = None
    config: Path | None = None
    out: Path = field(default_factory=lambda: Path(DEFAULT_OUT))
    json: Path | None = None
    fail_on: str | None = None
    seed: int = 42
    device: str = "auto"

    def validate(self) -> None:
        if self.path is None:
            raise OptionsError("No dataset folder chosen.")
        if not Path(self.path).is_dir():
            raise OptionsError(f"Not a folder: {self.path}")
        if self.type not in DATA_TYPES:
            raise OptionsError(f"Unknown data type: {self.type}")
        if DATA_TYPES[self.type] is not None:
            raise OptionsError(f"Data type {self.type} is {DATA_TYPES[self.type]}.")
        if self.mode not in MODES:
            raise OptionsError(f"Mode must be one of {', '.join(MODES)}")
        if self.device not in DEVICES:
            raise OptionsError(f"Device must be one of {', '.join(DEVICES)}")
        if self.fail_on is not None and self.fail_on not in FAIL_ON:
            raise OptionsError(f"--fail-on must be one of {', '.join(FAIL_ON)}")
        if self.config is not None and not Path(self.config).is_file():
            raise OptionsError(f"Config file not found: {self.config}")

    def to_command(self) -> str:
        """The equivalent one-line `scandata scan` command."""
        parts = ["scandata", "scan", str(self.path or "<folder>"), "--type", self.type]
        defaults = ScanOptions()
        optional = [
            ("--mode", self.mode, defaults.mode),
            ("--splits", self.splits, defaults.splits),
            ("--group-regex", self.group_regex, None),
            ("--target-size", self.target_size, None),
            ("--sample", self.sample, None),
            ("--config", self.config, None),
            ("--out", self.out, defaults.out),
            ("--json", self.json, None),
            ("--fail-on", self.fail_on, None),
            ("--seed", self.seed, defaults.seed),
            ("--device", self.device, defaults.device),
        ]
        for flag, value, default in optional:
            if value is not None and value != default:
                parts += [flag, str(value)]
        return " ".join(shlex.quote(p) for p in parts)
