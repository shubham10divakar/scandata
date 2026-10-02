"""Section E: Shortcuts. Can the label be predicted from things that shouldn't predict it?

Each probe trains a deliberately handicapped model (5-fold CV) that can't see the actual
content. If it still predicts the label, the real model can learn that shortcut too.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kruskal
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from scandata.analysis.probes import probe, single_feature_auc
from scandata.checks.image_cls._util import finding, md_table, passed, skipped
from scandata.core.context import ScanContext
from scandata.core.finding import Severity
from scandata.core.registry import Check, register

TOKEN_RE = re.compile(r"[a-z]+")


def class_naming_tokens(stems: pd.Series, y: np.ndarray) -> set[str]:
    """Alphabetic tokens that mark one class's files (in >= 90% of that class, < 10% of others),
    e.g. "cat" in cat.123.jpg or "cr" in cr0001.jpg. Naming files by class is normal and the
    model never sees filenames, so these aren't shortcuts."""
    tokens = stems.map(lambda s: set(TOKEN_RE.findall(s)))
    labels = pd.Series(y, index=stems.index)
    found: set[str] = set()
    for cls in labels.unique():
        mine, rest = tokens[labels == cls], tokens[labels != cls]
        if mine.empty:
            continue
        candidates = set.union(*mine.tolist()) if len(mine) else set()
        for tok in candidates:
            in_mine = mine.map(lambda t, tok=tok: tok in t).mean()
            in_rest = rest.map(lambda t, tok=tok: tok in t).mean() if len(rest) else 0.0
            if in_mine >= 0.9 and in_rest < 0.1:
                found.add(tok)
    for cls in labels.unique():
        found |= set(TOKEN_RE.findall(str(cls).lower()))
    return found


def strip_tokens(stem: str, tokens: set[str]) -> str:
    return TOKEN_RE.sub(lambda m: " " if m.group(0) in tokens else m.group(0), stem)


PIXEL_FEATURES = [
    "brightness", "contrast", "saturation", "sharpness", "entropy", "clipped_frac",
    "edge_density", "mean_r", "mean_g", "mean_b", "std_r", "std_g", "std_b",
]


def _severity(auc: float, warn: float, block: float | None) -> Severity:
    if block is not None and auc > block:
        return Severity.BLOCKER
    if auc > warn:
        return Severity.WARN
    return Severity.PASS


def _result(check, ctx, res, what, warn, block, fix, top: list[tuple[str, float]] | None = None):
    if res is None:
        return skipped(check, "not enough images per class to train a probe")
    sev = _severity(res.auc, warn, block)
    metric = {"auc": round(res.auc, 3), "balanced_accuracy": round(res.balanced_accuracy, 3),
              "n": res.n}
    details = ""
    if top:
        metric["top_features"] = {f: round(a, 3) for f, a in top}
        details = md_table(["feature", "AUC on its own"], [[f, round(a, 3)] for f, a in top])
    if sev is Severity.PASS:
        # below-chance CV AUCs are artifacts of uninformative features; show them as chance
        return passed(check, f"{what} can't predict the label (AUC {max(res.auc, 0.5):.2f})",
                      metric=metric, details=details)
    lead = f"; strongest: {top[0][0]} (AUC {top[0][1]:.2f})" if top else ""
    return [finding(check, sev, f"{what} alone predicts the label (AUC {res.auc:.2f}){lead}",
                    metric=metric, details=details, fix=fix)]


def _codes(series: pd.Series) -> np.ndarray:
    codes = series.fillna("(none)").astype(str).astype("category").cat.codes.to_numpy()
    return np.minimum(codes.astype(float), 250.0)


@register
class Metadata(Check):
    id = "short.metadata"
    section = "shortcuts"
    title = "Label predictable from file metadata"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        y = df["label"].to_numpy()
        numeric = {
            "width": df["width"], "height": df["height"], "aspect": df["width"] / df["height"],
            "jpeg quality": df["jpeg_quality"],
        }
        cats = {"format": df["format"], "color mode": df["mode"], "camera": df["camera_model"]}
        X = np.column_stack([v.astype(float).to_numpy() for v in numeric.values()]
                            + [_codes(v) for v in cats.values()])
        categorical = [False] * len(numeric) + [True] * len(cats)
        res = probe(X, y, seed=ctx.options.seed, max_per_class=int(ctx.t["max_probe_per_class"]),
                    categorical=categorical)
        names = list(numeric) + list(cats)
        top = sorted(((n, single_feature_auc(X[:, i], y)) for i, n in enumerate(names)),
                     key=lambda kv: -kv[1])[:5]
        out = _result(
            self, ctx, res, "File metadata (resolution, format, mode, JPEG quality)",
            ctx.t["shortcut_auc_warn"], ctx.t["shortcut_auc_block"], top=top,
            fix="Classes were saved differently (resolution, compression, format). A model can "
            "learn that instead of the content. Re-encode all images the same way (same size, "
            "format and quality) before training.",
        )
        # File size is reported but not scored: it tracks image detail, so it differs
        # between classes whenever their content does (e.g. cracks add edges).
        size_auc = single_feature_auc(df["bytes"].astype(float).to_numpy(), y)
        if size_auc > ctx.t["shortcut_auc_warn"]:
            note = (f"File size also separates the classes (AUC {size_auc:.2f}). It isn't scored "
                    "because it grows with image detail, but if classes were compressed "
                    "differently it is part of the same shortcut.")
            out[0].details = f"{out[0].details}\n\n{note}".strip()
            out[0].metric["file_size_auc"] = round(size_auc, 3)
        return out


@register
class Filename(Check):
    id = "short.filename"
    section = "shortcuts"
    title = "Label predictable from filenames"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        y = df["label"].to_numpy()
        stems = df["path"].map(lambda p: Path(p).stem.lower())
        naming = class_naming_tokens(stems, y)
        cleaned = stems.map(lambda s: strip_tokens(s, naming))
        model = make_pipeline(
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=3000),
            LogisticRegression(max_iter=1000),
        )
        res = probe(cleaned.to_numpy(dtype=object), y, seed=ctx.options.seed,
                    max_per_class=int(ctx.t["max_probe_per_class"]), model=model)
        out = _result(
            self, ctx, res, "The filename (ignoring class-name tokens)",
            ctx.t["shortcut_auc_warn"], ctx.t["shortcut_auc_block"],
            fix="Beyond the class name, filenames still carry class information (source IDs, "
            "numbering ranges, dates). That usually means classes came from different sources "
            "or sessions; check for group leakage and source bias.",
        )
        if naming:
            note = ("Ignored per-class naming tokens: "
                    + ", ".join(f"`{t}`" for t in sorted(naming)) + ".")
            out[0].details = f"{out[0].details}\n\n{note}".strip()
            out[0].metric["ignored_tokens"] = sorted(naming)
        return out


def _vector_probe(check, ctx, column, what, warn, block, fix):
    df = ctx.index.readable
    vectors = df[column].dropna()
    if vectors.empty:
        return skipped(check, "no pixel features")
    X = np.stack(vectors.map(np.asarray).to_numpy()).astype(float)
    y = df.loc[vectors.index, "label"].to_numpy()
    # Raw pixel vectors: a scaled linear model is ~20x faster than boosting here and
    # catches the global color / background differences these probes look for.
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.1))
    res = probe(X, y, seed=ctx.options.seed, max_per_class=int(ctx.t["max_probe_per_class"]),
                model=model)
    return _result(check, ctx, res, what, warn, block, fix)


@register
class Thumbnail(Check):
    id = "short.thumbnail"
    section = "shortcuts"
    title = "Label predictable from global color and brightness"

    def run(self, ctx: ScanContext):
        return _vector_probe(
            self, ctx, "thumb", "An 8x8 color thumbnail", ctx.t["thumbnail_auc_warn"], None,
            fix="Global color or brightness differs by class. Fine if color really defines "
            "the classes; otherwise it points to different capture conditions per class. "
            "Color jitter augmentation reduces reliance on it.",
        )


@register
class Border(Check):
    id = "short.border"
    section = "shortcuts"
    title = "Label predictable from the background"

    def run(self, ctx: ScanContext):
        return _vector_probe(
            self, ctx, "border", "The image border (center masked out)",
            ctx.t["border_auc_warn"], ctx.t["border_auc_block"],
            fix="Backgrounds differ by class, so a model can classify without looking at the "
            "object. Collect classes against matching backgrounds, crop to the object, or "
            "check for class-specific framing/padding.",
        )


@register
class StatByClass(Check):
    id = "short.stat_by_class"
    section = "shortcuts"
    title = "Low-level features most tied to the label"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        if df["label"].nunique() < 2:
            return skipped(self, "needs at least two classes")
        y = df["label"].to_numpy()
        n = len(df)
        rows = []
        for feat in PIXEL_FEATURES + ["width", "height", "bytes"]:
            values = df[feat].astype(float)
            groups = [values[y == c].dropna().to_numpy() for c in np.unique(y)]
            groups = [g for g in groups if len(g) > 1]
            if len(groups) < 2 or all(np.ptp(g) == 0 for g in groups):
                continue
            h, p = kruskal(*groups)
            eps2 = float(h / (n - 1)) if n > 1 else 0.0
            medians = df.groupby("label")[feat].median()
            rows.append((feat, eps2, float(p), medians.idxmax(), medians.idxmin()))
        if not rows:
            return skipped(self, "no varying features")
        rows.sort(key=lambda r: -r[1])
        top = rows[:5]
        details = md_table(
            ["feature", "effect size (eps^2)", "p-value", "highest in", "lowest in"],
            [[f, round(e, 3), f"{p:.2g}", hi, lo] for f, e, p, hi, lo in top],
        )
        f, e, _, hi, lo = top[0]
        return [finding(
            self, Severity.INFO,
            f"Most label-correlated low-level feature: {f} (eps^2 {e:.2f}, highest in {hi})",
            metric={"top": {r[0]: round(r[1], 4) for r in top}}, details=details,
        )]
