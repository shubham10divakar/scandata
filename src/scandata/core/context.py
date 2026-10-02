"""Everything a check needs: the index, options, thresholds and shared computations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scandata.core.config import Config
from scandata.core.index import DatasetIndex
from scandata.core.options import ScanOptions


@dataclass
class ScanContext:
    index: DatasetIndex
    options: ScanOptions
    config: Config
    assets_dir: Path | None = None
    _memo: dict[str, Any] = field(default_factory=dict)

    @property
    def t(self) -> dict[str, float]:
        return self.config.thresholds

    @property
    def max_examples(self) -> int:
        return self.config.max_examples

    def memo(self, key: str, compute: Callable[[], Any]) -> Any:
        """Share an expensive result (e.g. duplicate groups) between checks."""
        if key not in self._memo:
            self._memo[key] = compute()
        return self._memo[key]

    def asset_path(self, name: str) -> Path | None:
        if self.assets_dir is None or not self.config.thumbnails:
            return None
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        return self.assets_dir / name
