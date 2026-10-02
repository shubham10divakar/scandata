"""Feature cache in ~/.scandata/cache, so re-runs only process new or changed files.

Keyed by (absolute path, size, mtime, extractor version, target size). Nothing is ever
written inside the dataset folder.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from scandata.core.config import home_dir


class FeatureCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or home_dir() / "cache" / "features.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.execute("CREATE TABLE IF NOT EXISTS features (key TEXT PRIMARY KEY, data TEXT)")

    @staticmethod
    def key(path: str, version: int, target_size: int | None) -> str | None:
        try:
            st = os.stat(path)
        except OSError:
            return None
        return f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}|v{version}|t{target_size}"

    def get_many(self, keys: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for start in range(0, len(keys), 500):
            chunk = keys[start : start + 500]
            marks = ",".join("?" * len(chunk))
            rows = self._db.execute(
                f"SELECT key, data FROM features WHERE key IN ({marks})", chunk
            )
            found.update({k: json.loads(d) for k, d in rows})
        return found

    def put_many(self, items: dict[str, dict]) -> None:
        self._db.executemany(
            "INSERT OR REPLACE INTO features (key, data) VALUES (?, ?)",
            [(k, json.dumps(v)) for k, v in items.items()],
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
