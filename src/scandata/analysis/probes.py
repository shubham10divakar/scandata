"""Deliberately handicapped classifiers ("cheater" probes) for shortcut and split checks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

MIN_PER_CLASS = 5


@dataclass
class ProbeResult:
    auc: float  # macro one-vs-rest AUC
    balanced_accuracy: float
    n: int
    classes: int


def subsample(y: np.ndarray, max_per_class: int, seed: int) -> np.ndarray:
    """Positions to keep: at most `max_per_class` per class; classes below MIN_PER_CLASS dropped."""
    rng = np.random.default_rng(seed)
    keep = []
    for cls in np.unique(y):
        pos = np.flatnonzero(y == cls)
        if len(pos) < MIN_PER_CLASS:
            continue
        if len(pos) > max_per_class:
            pos = rng.choice(pos, max_per_class, replace=False)
        keep.append(pos)
    return np.sort(np.concatenate(keep)) if keep else np.array([], dtype=int)


def probe(
    X: np.ndarray,
    y: np.ndarray,
    seed: int = 42,
    max_per_class: int = 2000,
    model=None,
    categorical: list[bool] | None = None,
) -> ProbeResult | None:
    """5-fold CV of a small model predicting y from X. None if there isn't enough data."""
    keep = subsample(np.asarray(y), max_per_class, seed)
    if len(keep) == 0:
        return None
    X, y = X[keep], np.asarray(y)[keep]
    classes = np.unique(y)
    if len(classes) < 2:
        return None
    folds = min(5, int(np.bincount(np.unique(y, return_inverse=True)[1]).min()))
    if folds < 2:
        return None
    if model is None:
        model = HistGradientBoostingClassifier(
            max_iter=100, learning_rate=0.1, random_state=seed,
            categorical_features=categorical if categorical and any(categorical) else None,
        )
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")
    pred = classes[proba.argmax(axis=1)]
    if len(classes) == 2:
        auc = roc_auc_score(y == classes[1], proba[:, 1])
    else:
        auc = roc_auc_score(y, proba, multi_class="ovr", average="macro", labels=classes)
    return ProbeResult(
        auc=float(auc), balanced_accuracy=float(balanced_accuracy_score(y, pred)),
        n=len(y), classes=len(classes),
    )


def single_feature_auc(values: np.ndarray, y: np.ndarray) -> float:
    """How well one numeric feature separates the classes (macro OvR AUC, folded to >= 0.5)."""
    mask = ~np.isnan(values)
    values, y = values[mask], y[mask]
    classes = np.unique(y)
    if len(classes) < 2 or len(values) < 10:
        return 0.5
    aucs = []
    for cls in classes if len(classes) > 2 else classes[1:]:
        target = y == cls
        if target.all() or not target.any():
            continue
        auc = roc_auc_score(target, values)
        aucs.append(max(auc, 1 - auc))
    return float(np.mean(aucs)) if aucs else 0.5
