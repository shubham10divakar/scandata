"""Default thresholds and persisted user settings (~/.scandata/settings.json)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# Every threshold is overridable via --config YAML (Phase 1). Values from the design doc.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "near_dup_hamming": 6,
    "near_dup_dhash": 10,
    "near_dup_edge_corr": 0.65,
    "near_dup_pct_test_block": 0.5,
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
    "resize_flag_frac": 0.05,
    "aspect_distort_frac": 0.10,
    "blur_z": -3.0,
    "empty_class_warn": 10,
    "slice_min_frac": 0.05,
    "max_probe_per_class": 2000,
    "adv_val_min_images": 50,
}


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    """Effective scan configuration: default thresholds merged with a YAML file."""

    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    disabled: set[str] = field(default_factory=set)
    max_examples: int = 20
    thumbnails: bool = True

    @classmethod
    def load(cls, path: Path | None) -> Config:
        cfg = cls()
        if path is None:
            return cfg
        import yaml

        try:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigError(f"Could not read config {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"Config {path} must be a mapping")
        unknown = set(data.get("thresholds") or {}) - set(DEFAULT_THRESHOLDS)
        if unknown:
            raise ConfigError(f"Unknown thresholds in {path}: {', '.join(sorted(unknown))}")
        cfg.thresholds.update(data.get("thresholds") or {})
        cfg.disabled = set((data.get("checks") or {}).get("disable") or [])
        report = data.get("report") or {}
        cfg.max_examples = int(report.get("max_examples", cfg.max_examples))
        cfg.thumbnails = bool(report.get("thumbnails", cfg.thumbnails))
        return cfg


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


def append_history(entry: dict, keep: int = 50) -> None:
    path = home_dir() / "history.json"
    history = [entry, *load_history()][:keep]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except OSError:
        pass  # history is a convenience; never fail a scan over it
