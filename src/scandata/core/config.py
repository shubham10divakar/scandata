"""Default thresholds and persisted user settings (~/.scandata/settings.json)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

# Every threshold is overridable via --config YAML (Phase 1). Values from the design doc.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "near_dup_hamming": 6,
    "semantic_dup_cosine": 0.95,
    "imbalance_warn": 10,
    "min_test_per_class": 30,
    "stratification_pp_warn": 5,
    "mislabel_pct_warn": 2,
    "class_confusion_warn": 0.30,
    "shortcut_auc_warn": 0.70,
    "shortcut_auc_block": 0.85,
    "thumbnail_auc_warn": 0.80,
    "border_auc_warn": 0.75,
    "border_auc_block": 0.90,
    "adv_val_auc_warn": 0.60,
    "adv_val_auc_block": 0.75,
    "blank_std": 2,
    "blank_entropy": 0.5,
    "tiny_min_side": 32,
    "exposure_clipped_frac": 0.20,
    "resize_edge_loss": 0.50,
}


def home_dir() -> Path:
    return Path(os.environ.get("SCANDATA_HOME", Path.home() / ".scandata"))


@dataclass
class Settings:
    default_mode: str = "fast"
    default_out_dir: str = "."
    color: bool = True

    @classmethod
    def load(cls) -> Settings:
        path = home_dir() / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        path = home_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def load_history() -> list[dict]:
    """Recent scans, newest first. Written by the engine from Phase 2."""
    try:
        data = json.loads((home_dir() / "history.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []
