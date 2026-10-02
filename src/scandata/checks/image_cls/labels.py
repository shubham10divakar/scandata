"""Section C: Labels."""

from __future__ import annotations

import math

import pandas as pd

from scandata.checks.image_cls._util import counts_table, finding, md_table, passed, skipped
from scandata.core.context import ScanContext
from scandata.core.finding import Severity
from scandata.core.registry import Check, register


def imbalance(df: pd.DataFrame) -> tuple[float, str, str]:
    counts = df["label"].value_counts()
    counts = counts[counts > 0]
    if len(counts) < 2:
        return 1.0, "", ""
    return float(counts.max() / counts.min()), str(counts.idxmax()), str(counts.idxmin())


@register
class Distribution(Check):
    id = "lab.distribution"
    section = "labels"
    title = "Class counts and imbalance"

    def run(self, ctx: ScanContext):
        df = ctx.index.df
        ratio, big, small = imbalance(df)
        details = counts_table(df, by_split=True)
        metric = {"classes": df["label"].nunique(), "imbalance_ratio": round(ratio, 2),
                  "counts": df["label"].value_counts().to_dict()}
        if ratio > ctx.t["imbalance_warn"]:
            return [finding(
                self, Severity.WARN,
                f"Classes are imbalanced {ratio:.1f}:1 ({big} vs {small})",
                metric=metric, details=details,
                fix="Don't report plain accuracy. Use macro-F1 or balanced accuracy, and "
                "consider class weights or a balanced sampler.",
            )]
        return [finding(
            self, Severity.INFO,
            f"{metric['classes']} classes, imbalance {ratio:.1f}:1",
            metric=metric, details=details,
        )]


@register
class SplitCoverage(Check):
    id = "lab.split_coverage"
    section = "labels"
    title = "Enough examples per class to evaluate"

    def run(self, ctx: ScanContext):
        index = ctx.index
        if not index.held_out:
            return skipped(self, "no validation or test split")
        df = index.df
        need = int(ctx.t["min_test_per_class"])
        rows, thin = [], []
        for split in index.held_out:
            counts = df[df["split"] == split]["label"].value_counts().reindex(index.labels,
                                                                               fill_value=0)
            for label, n in counts.items():
                if n < need:
                    width = 196 * math.sqrt(0.8 * 0.2 / n) if n else float("inf")
                    thin.append((split, label, int(n)))
                    rows.append([split, label, int(n),
                                 f"±{width:.0f} pp" if n else "can't evaluate"])
        if not thin:
            return passed(self, f"Every class has at least {need} images in "
                                + ", ".join(index.held_out))
        return [finding(
            self, Severity.WARN,
            f"{len(thin)} class/split combination(s) have fewer than {need} evaluation images",
            metric={"thin": [{"split": s, "class": c, "n": n} for s, c, n in thin]},
            details=md_table(["split", "class", "images", "95% CI of recall at 0.8"], rows),
            fix="Per-class scores on so few images are mostly noise (see the CI column). "
            "Move more data into evaluation or report pooled metrics only.",
        )]


@register
class Stratification(Check):
    id = "lab.stratification"
    section = "labels"
    title = "Class proportions differ across splits"

    def run(self, ctx: ScanContext):
        index = ctx.index
        if not index.has_splits:
            return skipped(self, "no splits")
        df = index.df
        props = pd.crosstab(df["label"], df["split"], normalize="columns") * 100
        ref = "train" if "train" in props else props.columns[0]
        diff = props.sub(props[ref], axis=0).abs()
        worst = float(diff.to_numpy().max())
        rows = [[label, *(f"{v:.1f}%" for v in props.loc[label])] for label in props.index]
        details = md_table(["class", *props.columns], rows)
        if worst > ctx.t["stratification_pp_warn"]:
            label, split = diff.stack().idxmax()
            return [finding(
                self, Severity.WARN,
                f"Class mix differs by up to {worst:.1f} pp ({label} in {split} vs {ref})",
                metric={"max_diff_pp": round(worst, 2)}, details=details,
                fix="Use a stratified split so every split has the same class proportions.",
            )]
        return passed(self, f"Class proportions match across splits (max diff {worst:.1f} pp)",
                      details=details)
