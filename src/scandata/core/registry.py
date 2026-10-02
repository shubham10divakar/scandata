"""Check registry. Checks register with @register; plugins via the `scandata.checks` entry point."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from scandata.core.context import ScanContext
    from scandata.core.finding import Finding

SECTION_ORDER = ["integrity", "leakage", "labels", "quality", "shortcuts", "baselines"]


class Check:
    id: ClassVar[str]
    section: ClassVar[str]
    title: ClassVar[str]
    modes: ClassVar[frozenset[str]] = frozenset({"fast", "deep"})
    data_types: ClassVar[frozenset[str]] = frozenset({"image-cls"})

    def run(self, ctx: ScanContext) -> list[Finding]:
        raise NotImplementedError


_REGISTRY: dict[str, type[Check]] = {}
_loaded = False


def register(cls: type[Check]) -> type[Check]:
    if cls.section not in SECTION_ORDER:
        raise ValueError(f"{cls.id}: unknown section {cls.section!r}")
    _REGISTRY[cls.id] = cls
    return cls


def _load() -> None:
    global _loaded
    if _loaded:
        return
    import scandata.checks.image_cls  # noqa: F401  (registers the built-in checks)

    for ep in entry_points(group="scandata.checks"):
        ep.load()
    _loaded = True


def all_checks() -> dict[str, type[Check]]:
    _load()
    return dict(_REGISTRY)


def get_checks(data_type: str, mode: str, disabled: set[str] | None = None) -> list[Check]:
    disabled = disabled or set()
    selected = [
        cls()
        for cls in all_checks().values()
        if data_type in cls.data_types and mode in cls.modes and cls.id not in disabled
    ]
    return sorted(selected, key=lambda c: SECTION_ORDER.index(c.section))
