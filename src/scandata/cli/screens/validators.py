"""Prompt validators: return True, or an error message to show under the prompt."""

from __future__ import annotations

import re
from pathlib import Path


def _clean(value: str) -> str:
    return value.strip().strip('"')


def is_dir(value: str) -> bool | str:
    if not _clean(value):
        return "Enter a folder path"
    return True if Path(_clean(value)).expanduser().is_dir() else "Folder not found"


def optional_file(value: str) -> bool | str:
    if not _clean(value):
        return True
    return True if Path(_clean(value)).expanduser().is_file() else "File not found"


def not_blank(value: str) -> bool | str:
    return True if value.strip() else "Can't be empty"


def optional_positive_int(value: str) -> bool | str:
    if not value.strip():
        return True
    return True if value.strip().isdigit() and int(value) > 0 else "Enter a positive whole number"


def non_negative_int(value: str) -> bool | str:
    return True if value.strip().isdigit() else "Enter a whole number"


def group_regex(value: str) -> bool | str:
    if not value.strip():
        return True
    try:
        pattern = re.compile(value)
    except re.error as exc:
        return f"Invalid regex: {exc}"
    return True if "group" in pattern.groupindex else "Needs a named group: (?P<group>...)"


def splits(value: str) -> bool | str:
    v = _clean(value)
    if v in ("auto", "none"):
        return True
    return True if Path(v).is_file() else "Use auto, none, or a path to a manifest CSV"
