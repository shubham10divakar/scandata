"""Section F: Baselines and data sufficiency."""

from __future__ import annotations

from scandata.checks.image_cls._util import finding, held_out_split
from scandata.checks.image_cls.labels import imbalance
from scandata.core.context import ScanContext
from scandata.core.finding import Severity
from scandata.core.registry import Check, register


@register
class Majority(Check):
    id = "base.majority"
    section = "baselines"
    title = "Majority-class baseline"

    def run(self, ctx: ScanContext):
        df = ctx.index.df
        train = df[df["split"] == "train"] if "train" in ctx.index.splits else df
        held = held_out_split(ctx)
        evaluate = df[df["split"] == held] if held else df
        majority = train["label"].value_counts().idxmax()
        acc = float((evaluate["label"] == majority).mean())
        k = evaluate["label"].nunique()
        where = f"on {held}" if held else "on all images"
        return [finding(
            self, Severity.INFO,
            f"Always predicting '{majority}' scores {acc:.1%} accuracy {where} "
            f"(balanced accuracy {1 / k:.1%})",
            metric={"majority_class": majority, "accuracy": round(acc, 4),
                    "balanced_accuracy": round(1 / k, 4)},
            fix="This is the floor. A model has to clearly beat it to be worth reporting.",
        )]


@register
class MetricAdvice(Check):
    id = "base.metric_advice"
    section = "baselines"
    title = "Recommended primary metric"

    def run(self, ctx: ScanContext):
        df = ctx.index.df
        ratio, _, _ = imbalance(df)
        k = df["label"].nunique()
        if ratio >= 3:
            metric = "macro-F1" + (" and PR-AUC" if k == 2 else "")
            why = f"accuracy is misleading at {ratio:.1f}:1 imbalance"
        else:
            metric = "accuracy (plus macro-F1)"
            why = f"classes are roughly balanced ({ratio:.1f}:1)"
        return [finding(
            self, Severity.INFO, f"Use {metric} as the primary metric: {why}",
            metric={"recommended": metric, "imbalance_ratio": round(ratio, 2)},
        )]
