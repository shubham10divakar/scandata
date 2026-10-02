from __future__ import annotations

from pathlib import Path

from scandata.cli.context import App
from scandata.cli.navigator import NavAction, Stay
from scandata.cli.prompter import Option
from scandata.cli.screens import validators as v
from scandata.core.options import DEVICES

FIELDS = [
    ("splits", "Splits", "auto, none, or a manifest CSV path", v.splits),
    ("group_regex", "Group regex", "e.g. ^(?P<group>[A-Z]+_\\d+)_  (blank = none)", v.group_regex),
    ("target_size", "Target size", "training resolution in px (blank = none)",
     v.optional_positive_int),
    ("sample", "Sample per class", "audit only N images per class (blank = all)",
     v.optional_positive_int),
    ("seed", "Seed", "seed for sampling and probes", v.non_negative_int),
    ("config", "Config YAML", "threshold overrides (blank = none)", v.optional_file),
    ("json", "JSON findings", "path for findings.json (blank = none)", None),
]
INT_FIELDS = {"target_size", "sample", "seed"}
PATH_FIELDS = {"config", "json"}


def _parse(name: str, raw: str):
    raw = raw.strip().strip('"')
    if name == "splits":
        return raw
    if not raw:
        return None
    if name in INT_FIELDS:
        return int(raw)
    if name in PATH_FIELDS:
        return Path(raw).expanduser()
    return raw


class AdvancedOptions:
    title = "Advanced options"

    def show(self, app: App) -> NavAction:
        o = app.options
        options = [
            Option(f"{label:<18}{getattr(o, name) if getattr(o, name) is not None else '-'}", name)
            for name, label, _, _ in FIELDS
        ]
        options += [
            Option(f"{'Device':<18}{o.device}", "device"),
            Option(f"{'Fail on':<18}{o.fail_on or '-'}", "fail_on"),
        ]
        choice = app.menu("Advanced options", options)
        if isinstance(choice, NavAction):
            return choice

        if choice == "device":
            value = app.prompter.select(
                "Device:", [Option(d, d) for d in DEVICES], default=o.device
            )
            if value is not None:
                o.device = value
        elif choice == "fail_on":
            value = app.prompter.select(
                "Exit with code 1 when findings reach:",
                [Option("never", "never"), Option("blocker", "blocker"), Option("warn", "warn")],
                default=o.fail_on or "never",
            )
            if value is not None:
                o.fail_on = None if value == "never" else value
        else:
            name, label, hint, validate = next(f for f in FIELDS if f[0] == choice)
            current = getattr(o, name)
            app.console.print(f"[dim]{hint}[/dim]")
            value = app.prompter.text(
                f"{label}:", default="" if current is None else str(current), validate=validate
            )
            if value is not None:
                setattr(o, name, _parse(name, value))
        return Stay()
