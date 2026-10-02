"""Section B: Leakage (the results killers)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import chi2_contingency

from scandata.analysis.duplicates import DupResult, find_duplicates, pixel_verifier
from scandata.analysis.grids import save_pairs
from scandata.analysis.probes import probe, single_feature_auc
from scandata.checks.image_cls._util import (
    finding,
    held_out_split,
    md_table,
    passed,
    pct,
    skipped,
)
from scandata.core.context import ScanContext
from scandata.core.finding import Severity
from scandata.core.registry import Check, register

NUMERIC_FEATURES = [
    "width", "height", "bytes", "brightness", "contrast", "saturation", "sharpness",
    "entropy", "clipped_frac", "edge_density", "mean_r", "mean_g", "mean_b",
    "std_r", "std_g", "std_b", "jpeg_quality",
]


def duplicates(ctx: ScanContext) -> tuple[pd.DataFrame, DupResult]:
    def compute():
        df = ctx.index.readable
        blank = (df["contrast"] < ctx.t["blank_std"]) | (df["entropy"] < ctx.t["blank_entropy"])
        return df, find_duplicates(
            df, int(ctx.t["near_dup_hamming"]), exclude=blank,
            dhash_threshold=int(ctx.t["near_dup_dhash"]),
            verify=pixel_verifier(df["path"].tolist(), float(ctx.t["near_dup_edge_corr"])),
        )

    return ctx.memo("duplicates", compute)


def _cross_split_pairs(df: pd.DataFrame, pairs: np.ndarray) -> np.ndarray:
    if len(pairs) == 0:
        return pairs
    split = df["split"].to_numpy()
    a, b = pairs[:, 0], pairs[:, 1]
    keep = pd.notna(split[a]) & pd.notna(split[b]) & (split[a] != split[b])
    return pairs[keep]


def _pair_grid(ctx, df, pairs, name) -> list[str]:
    out = ctx.asset_path(name)
    if out is None or len(pairs) == 0:
        return []
    items = []
    for a, b, _d in pairs[:8]:
        ra, rb = df.iloc[a], df.iloc[b]
        items.append((ra.path, f"{ra.split or ''} {ra.label}", rb.path, f"{rb.split or ''} {rb.label}"))
    written = save_pairs(items, out)
    return [written] if written else []


def _pair_lines(df, pairs, limit) -> list[str]:
    rel = df["relpath"].to_numpy()
    return [f"{rel[a]}  <->  {rel[b]}  (distance {d})" for a, b, d in pairs[:limit]]


@register
class ExactDup(Check):
    id = "leak.exact_dup"
    section = "leakage"
    title = "Byte-identical files"

    def run(self, ctx: ScanContext):
        df, dups = duplicates(ctx)
        if not dups.exact_groups:
            return passed(self, "No byte-identical files")
        split = df["split"].to_numpy()
        spans = [len({s for s in split[g] if pd.notna(s)}) > 1 for g in dups.exact_groups]
        cross = [g for g, x in zip(dups.exact_groups, spans, strict=True) if x]
        within = [g for g, x in zip(dups.exact_groups, spans, strict=True) if not x]
        rel = df["relpath"].to_numpy()
        out = []
        if cross:
            files = sum(len(g) for g in cross)
            out.append(finding(
                self, Severity.BLOCKER,
                f"{len(cross):,} identical file group(s) span splits ({files:,} files)",
                metric={"groups": len(cross), "files": files},
                evidence=[" = ".join(rel[g][:4]) for g in cross[: ctx.max_examples]],
                fix="The same file is in train and evaluation, so test scores are inflated. "
                "Keep one copy, or use suggested_splits.csv.",
            ))
        if within:
            extra = sum(len(g) - 1 for g in within)
            out.append(finding(
                self, Severity.WARN,
                f"{len(within):,} identical file group(s) inside a split ({extra:,} redundant copies)",
                metric={"groups": len(within), "redundant": extra},
                evidence=[" = ".join(rel[g][:4]) for g in within[: ctx.max_examples]],
                fix="Duplicates over-weight those images during training. Keep one copy of each.",
            ))
        return out


@register
class NearDup(Check):
    id = "leak.near_dup"
    section = "leakage"
    title = "Near-duplicate images across splits"

    def run(self, ctx: ScanContext):
        df, dups = duplicates(ctx)
        thr = int(ctx.t["near_dup_hamming"])
        near = dups.near_pairs[dups.near_pairs[:, 2] > 0] if len(dups.near_pairs) else dups.near_pairs
        if not ctx.index.has_splits:
            if len(near) == 0:
                return passed(self, f"No near-duplicates (pHash distance <= {thr})")
            members = int((dups.component >= 0).sum())
            return [finding(
                self, Severity.INFO,
                f"{len(near):,} near-duplicate pair(s) in {dups.n_components:,} cluster(s); "
                "no splits yet",
                metric={"pairs": len(near), "clusters": dups.n_components, "images": members},
                evidence=_pair_lines(df, near, ctx.max_examples),
                assets=_pair_grid(ctx, df, near, "leak_near_dup.png"),
                fix="When you split, keep each cluster in one split. suggested_splits.csv "
                "does this for you.",
            )]

        cross = _cross_split_pairs(df, dups.near_pairs)
        if len(cross) == 0:
            return passed(self, f"No near-duplicates across splits (pHash distance <= {thr})")
        held = held_out_split(ctx)
        split = df["split"].to_numpy()
        leaked = set()
        for a, b, _ in cross:
            for x, y in ((a, b), (b, a)):
                if split[x] == held and split[y] == "train":
                    leaked.add(int(x))
        n_held = int((split == held).sum())
        pct_held = pct(len(leaked), n_held)
        severity = Severity.BLOCKER if pct_held > ctx.t["near_dup_pct_test_block"] else Severity.WARN
        return [finding(
            self, severity,
            f"{len(cross):,} near-duplicate pair(s) cross splits; {len(leaked):,} {held} images "
            f"({pct_held}%) have a near-copy in train",
            metric={"pairs": len(cross), f"{held}_leaked": len(leaked), f"pct_{held}": pct_held},
            evidence=_pair_lines(df, cross, ctx.max_examples),
            assets=_pair_grid(ctx, df, cross, "leak_near_dup.png"),
            fix="Resized or recompressed copies across splits inflate scores. Re-split keeping "
            "near-duplicate clusters together: use suggested_splits.csv.",
        )]


@register
class LabelConflict(Check):
    id = "leak.label_conflict"
    section = "leakage"
    title = "The same image under different labels"

    def run(self, ctx: ScanContext):
        df, dups = duplicates(ctx)
        if not len(dups.near_pairs):
            return passed(self, "No duplicate images with conflicting labels")
        labels = df["label"].to_numpy()
        pairs = dups.near_pairs[labels[dups.near_pairs[:, 0]] != labels[dups.near_pairs[:, 1]]]
        if len(pairs) == 0:
            return passed(self, "Duplicates always share a label")
        rel = df["relpath"].to_numpy()
        involved = len(set(pairs[:, 0]) | set(pairs[:, 1]))
        return [finding(
            self, Severity.BLOCKER,
            f"{len(pairs):,} duplicate pair(s) carry different labels ({involved:,} images)",
            metric={"pairs": len(pairs), "images": involved},
            evidence=[f"{rel[a]} [{labels[a]}]  <->  {rel[b]} [{labels[b]}]"
                      for a, b, _ in pairs[: ctx.max_examples]],
            assets=_pair_grid(ctx, df, pairs, "leak_label_conflict.png"),
            fix="The same picture can't be both classes. Decide the right label for each pair "
            "and remove the other copy.",
        )]


GROUP_CANDIDATES = [
    r"^(?P<group>[A-Za-z]*\d+)[_\-\s]",          # 7001_12.jpg, IMG123-4.png
    r"^(?P<group>[A-Za-z0-9]+)[_\-\s]",           # anything before the first separator
    r"^(?P<group>.+)[_\-]\d+\.[A-Za-z]+$",        # source_name_003.jpg
]


def infer_groups(df: pd.DataFrame) -> tuple[str, pd.Series] | None:
    names = df["path"].map(lambda p: Path(p).name)
    n_labels = df["label"].nunique()
    for pattern in GROUP_CANDIDATES:
        rx = re.compile(pattern)
        groups = names.map(lambda s, rx=rx: (m.group("group") if (m := rx.search(s)) else None))
        coverage = groups.notna().mean()
        n_groups = groups.nunique()
        if coverage < 0.9 or n_groups < max(3, 2 * n_labels) or n_groups > 0.5 * len(df):
            continue
        return pattern, groups
    return None


@register
class GroupLeak(Check):
    id = "leak.group"
    section = "leakage"
    title = "Source groups shared across splits"

    def run(self, ctx: ScanContext):
        index = ctx.index
        if not index.has_splits:
            return skipped(self, "no train/val/test splits")
        df = index.df
        declared = index.groups_declared and df["group"].notna().any()
        if declared:
            groups, source, pattern = df["group"], "declared", ctx.options.group_regex
        else:
            inferred = infer_groups(df)
            if inferred is None:
                return skipped(self, "no --group-regex given and no filename grouping detected")
            pattern, groups = inferred
            source = "inferred"
        frame = pd.DataFrame({"group": groups, "split": df["split"], "rel": df["relpath"]}).dropna()
        spread = frame.groupby("group")["split"].nunique()
        shared = spread[spread > 1]
        if shared.empty:
            return passed(self, f"No {source} group appears in more than one split "
                                f"({spread.size:,} groups)")
        severity = Severity.BLOCKER if declared else Severity.WARN
        examples = [
            f"{g}: " + ", ".join(sorted(frame.loc[frame.group == g, "split"].unique()))
            for g in shared.index[: ctx.max_examples]
        ]
        return [finding(
            self, severity,
            f"{len(shared):,} of {spread.size:,} {source} source groups span multiple splits",
            metric={"groups_shared": len(shared), "groups": int(spread.size), "source": source,
                    "pattern": pattern},
            evidence=examples,
            fix=(
                "Images from one source (patient, plant, slab, source photo) must stay in one "
                "split. Re-split by group: use suggested_splits.csv."
                if declared else
                f"Filenames suggest a source ID (pattern `{pattern}`). If that's right, rerun "
                f"with `--group-regex \"{pattern}\"` to confirm, and re-split by group."
            ),
        )]


@register
class NoTestSplit(Check):
    id = "leak.no_test_split"
    section = "leakage"
    title = "No held-out split"

    def run(self, ctx: ScanContext):
        if ctx.index.has_splits:
            missing = [s for s in ("val", "test") if s not in ctx.index.splits]
            if "test" in missing:
                return [finding(
                    self, Severity.INFO, "No test split (only " + ", ".join(ctx.index.splits) + ")",
                    fix="Keep a final test set you never tune on. suggested_splits.csv adds one.",
                )]
            return passed(self, "Splits found: " + ", ".join(ctx.index.splits))
        return [finding(
            self, Severity.INFO, "No train/val/test split exists yet",
            fix="suggested_splits.csv has a group-aware, stratified, duplicate-safe split "
            "(about 70/15/15) ready to use.",
        )]


@register
class SplitStats(Check):
    id = "leak.split_stats"
    section = "leakage"
    title = "Splits drawn from different distributions"

    def run(self, ctx: ScanContext):
        index = ctx.index
        if not index.has_splits or "train" not in index.splits:
            return skipped(self, "needs a train split and at least one other split")
        df = index.readable
        out = []
        table = pd.crosstab(df["label"], df["split"])
        _, p, _, _ = chi2_contingency(table) if table.shape[0] > 1 else (0, 1.0, 0, 0)
        rows, worst = [], (None, 0.0, 0.5, [])
        min_n = int(ctx.t["adv_val_min_images"])
        for split in index.held_out:
            sub = df[df["split"].isin(["train", split])]
            y = (sub["split"] == split).to_numpy()
            if y.sum() < min_n or (~y).sum() < min_n:
                rows.append([f"train vs {split}", "-", "-", f"under {min_n} images, not tested"])
                continue
            js = float(jensenshannon(table["train"] / table["train"].sum(),
                                     table[split] / table[split].sum(), base=2))
            features = [c for c in NUMERIC_FEATURES if c in sub]
            X = sub[features].astype(float).to_numpy()
            res = probe(X, y, seed=ctx.options.seed, max_per_class=int(ctx.t["max_probe_per_class"]))
            auc = res.auc if res else float("nan")
            singles = sorted(
                ((f, single_feature_auc(sub[f].astype(float).to_numpy(), y)) for f in features),
                key=lambda kv: -kv[1],
            )[:3]
            rows.append([f"train vs {split}", round(js, 3), round(auc, 3),
                         ", ".join(f"{f} ({a:.2f})" for f, a in singles)])
            if res and auc > worst[2]:
                worst = (split, js, auc, singles)
        details = md_table(["comparison", "label JS divergence", "adversarial AUC",
                            "most different features (AUC)"], rows)
        details += f"\n\nLabel distribution chi-squared p = {p:.3g}."
        split, js, auc, singles = worst
        metric = {"adversarial_auc": round(auc, 3), "label_chi2_p": float(p)}
        if split and auc > ctx.t["adv_val_auc_block"]:
            sev = Severity.BLOCKER
        elif split and auc > ctx.t["adv_val_auc_warn"]:
            sev = Severity.WARN
        else:
            sev = Severity.PASS
        if split is None:
            return [finding(self, Severity.PASS,
                            f"Skipped: splits too small to compare (need {min_n}+ images each)",
                            metric={"skipped": "splits too small"}, details=details)]
        if sev is Severity.PASS:
            out.append(finding(self, sev, "Train and evaluation splits look alike "
                                         f"(adversarial AUC <= {max(auc, 0.5):.2f})",
                               metric=metric, details=details))
        else:
            top = ", ".join(f for f, _ in singles)
            out.append(finding(
                self, sev,
                f"A classifier can tell train from {split} (AUC {auc:.2f}); top cues: {top}",
                metric=metric, details=details,
                fix="Your evaluation split comes from a different distribution (capture "
                "setup, source, preprocessing). Scores won't reflect training conditions. "
                "Re-split randomly within sources, or report it as an out-of-distribution test.",
            ))
        return out  # class-proportion differences are reported by lab.stratification
