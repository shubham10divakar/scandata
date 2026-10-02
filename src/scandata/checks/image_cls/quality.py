"""Section D: Quality and distribution."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scandata.analysis.grids import save_grid
from scandata.checks.image_cls._util import examples, finding, md_table, passed, pct, skipped
from scandata.core.context import ScanContext
from scandata.core.finding import Severity
from scandata.core.registry import Check, register


def _grid(ctx, df, name, n=16) -> list[str]:
    out = ctx.asset_path(name)
    if out is None or df.empty:
        return []
    written = save_grid([(r.path, r.label) for r in df.head(n).itertuples()], out)
    return [written] if written else []


@register
class Resolution(Check):
    id = "qual.resolution"
    section = "quality"
    title = "Resolution and aspect ratio"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        aspect = df["width"] / df["height"]
        ref = float(aspect.median())
        distorted = (np.abs(np.log(aspect / ref)) > np.log(1.25)).mean()
        rows = []
        for label, g in df.groupby("label"):
            rows.append([label, f"{int(g.width.median())}x{int(g.height.median())}",
                         f"{int(g.width.min())}x{int(g.height.min())}",
                         f"{int(g.width.max())}x{int(g.height.max())}",
                         f"{(g.width / g.height).median():.2f}"])
        details = md_table(["class", "median", "min", "max", "median aspect"], rows)
        sizes = (df["width"].astype(int).astype(str) + "x"
                 + df["height"].astype(int).astype(str)).value_counts()
        metric = {"distinct_sizes": int(sizes.size), "median_aspect": round(ref, 3),
                  "pct_distorted": round(100 * float(distorted), 2)}
        if distorted > ctx.t["aspect_distort_frac"]:
            return [finding(
                self, Severity.WARN,
                f"{100 * distorted:.1f}% of images differ >25% from the median aspect ratio",
                metric=metric, details=details,
                fix="A fixed-size resize will stretch these. Use padding (letterbox) or "
                "random-resized crops instead of a plain resize.",
            )]
        top = ", ".join(f"{s} ({n:,})" for s, n in sizes.head(3).items())
        return [finding(self, Severity.INFO,
                        f"{sizes.size:,} distinct image size(s); most common: {top}",
                        metric=metric, details=details)]


@register
class ResizeRisk(Check):
    id = "qual.resize_risk"
    section = "quality"
    title = "Fine detail lost at training resolution"

    def run(self, ctx: ScanContext):
        size = ctx.options.target_size
        if not size:
            return skipped(self, "pass --target-size to check this")
        df = ctx.index.readable
        usable = df[(df["edge_density"] > 0.005) & df["edge_density_target"].notna()]
        if usable.empty:
            return skipped(self, "images have too few edges to measure")
        loss = 1 - usable["edge_density_target"].astype(float) / usable["edge_density"]
        # assign before filtering: .assign(Series) on an empty frame would adopt the
        # Series' whole index and resurrect every row with blank columns
        flagged = usable.assign(loss=loss)[loss > ctx.t["resize_edge_loss"]]
        frac = len(flagged) / len(usable)
        by_class = (loss > ctx.t["resize_edge_loss"]).groupby(usable["label"]).mean() * 100
        details = md_table(["class", "% losing >50% of edges"],
                           [[c, f"{v:.1f}%"] for c, v in by_class.items()])
        metric = {"target_size": size, "pct_flagged": round(100 * frac, 2),
                  "median_edge_loss": round(float(loss.median()), 3)}
        if frac > ctx.t["resize_flag_frac"]:
            flagged = flagged.sort_values("loss", ascending=False)
            return [finding(
                self, Severity.WARN,
                f"{100 * frac:.1f}% of images lose over half their edges at {size}x{size}",
                metric=metric, details=details,
                evidence=examples(flagged.assign(loss=flagged["loss"].round(2)), ctx, note="loss"),
                assets=_grid(ctx, flagged, "qual_resize_risk.png"),
                fix="Thin structures (cracks, lesions) vanish at this size. Train at a higher "
                "resolution or on tiles/crops instead of the downscaled whole image.",
            )]
        return passed(self, f"Detail survives resizing to {size}x{size} "
                            f"({100 * frac:.1f}% of images flagged)", metric=metric,
                      details=details)


@register
class Blur(Check):
    id = "qual.blur"
    section = "quality"
    title = "Blurry images"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        log_sharp = np.log1p(df["sharpness"].astype(float))
        z = pd.Series(index=df.index, dtype=float)
        for _, g in log_sharp.groupby(df["label"]):
            mad = (g - g.median()).abs().median() * 1.4826
            z[g.index] = (g - g.median()) / mad if mad > 0 else 0.0
        blurry = df[z < ctx.t["blur_z"]].assign(sharpness=lambda d: d["sharpness"].round(1))
        rate = (z < ctx.t["blur_z"]).groupby(df["label"]).mean() * 100
        details = md_table(["class", "median sharpness", "% flagged blurry"],
                           [[c, float(df.loc[df.label == c, "sharpness"].median()), f"{r:.1f}%"]
                            for c, r in rate.items()])
        if blurry.empty:
            return passed(self, "No unusually blurry images", details=details)
        spread = float(rate.max() - rate.min())
        uneven = spread > 5 and rate.min() * 2 < rate.max()
        return [finding(
            self, Severity.WARN if uneven else Severity.INFO,
            f"{len(blurry):,} unusually blurry image(s)"
            + (f"; blur rate differs by class ({rate.idxmax()} {rate.max():.1f}%)" if uneven else ""),
            metric={"files": len(blurry), "pct": pct(len(blurry), len(df)),
                    "rate_by_class": rate.round(2).to_dict()},
            evidence=examples(blurry.sort_values("sharpness"), ctx, note="sharpness"),
            details=details, assets=_grid(ctx, blurry.sort_values("sharpness"), "qual_blur.png"),
            fix="Review and drop unusable frames." + (
                " Blur that depends on class is a shortcut the model can learn." if uneven else ""),
        )]


@register
class Exposure(Check):
    id = "qual.exposure"
    section = "quality"
    title = "Over- or under-exposed images"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        bad = df[df["clipped_frac"] > ctx.t["exposure_clipped_frac"]]
        if bad.empty:
            return passed(self, "No badly exposed images")
        bad = bad.assign(clipped=lambda d: (d["clipped_frac"] * 100).round(0).astype(int).astype(str) + "%")
        return [finding(
            self, Severity.INFO,
            f"{len(bad):,} image(s) have over {ctx.t['exposure_clipped_frac'] * 100:.0f}% "
            "clipped (pure black/white) pixels",
            metric={"files": len(bad), "by_class": bad["label"].value_counts().to_dict()},
            evidence=examples(bad.sort_values("clipped_frac", ascending=False), ctx, note="clipped"),
            assets=_grid(ctx, bad, "qual_exposure.png"),
            fix="Check these for over/under-exposure; brightness augmentation can help.",
        )]


@register
class Normalization(Check):
    id = "qual.normalization"
    section = "quality"
    title = "Channel mean and std for normalisation"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        source = "train split"
        if ctx.index.has_splits and "train" in ctx.index.splits:
            df = df[df["split"] == "train"]
        else:
            source = "all images (no train split)"
        means = [float(df[f"mean_{c}"].mean()) for c in "rgb"]
        # pooled std: within-image variance plus variance of the image means
        stds = [float(np.sqrt((df[f"std_{c}"] ** 2).mean() + df[f"mean_{c}"].var(ddof=0)))
                for c in "rgb"]
        m = ", ".join(f"{v:.4f}" for v in means)
        s = ", ".join(f"{v:.4f}" for v in stds)
        snippet = (
            "```python\n"
            f"# computed from the {source}, RGB, scale 0-1\n"
            f"mean = [{m}]\nstd = [{s}]\n\n"
            "# torchvision\ntransforms.Normalize(mean=mean, std=std)\n```"
        )
        return [finding(self, Severity.INFO, f"Dataset mean [{m}], std [{s}]",
                        metric={"mean": means, "std": stds, "source": source}, details=snippet)]


@register
class Slices(Check):
    id = "qual.slices"
    section = "quality"
    title = "Per-domain breakdown"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        if df["domain"].isna().all():
            return skipped(self, "no domains (nested folders) in this dataset")
        domain = df["domain"].fillna("(none)")
        table = pd.crosstab(domain, df["label"])
        share = domain.value_counts(normalize=True)
        stats = df.groupby(domain)[["brightness", "sharpness"]].median()
        rows = [[d, int(table.loc[d].sum()), f"{share[d] * 100:.1f}%",
                 float(stats.loc[d, "brightness"]), float(stats.loc[d, "sharpness"])]
                for d in table.index]
        details = md_table(["domain", "images", "share", "median brightness",
                            "median sharpness"], rows)
        details += "\n\n" + md_table(["domain", *table.columns],
                                     [[d, *r] for d, r in zip(table.index, table.to_numpy().tolist(),
                                                              strict=True)])
        small = share[share < ctx.t["slice_min_frac"]]
        if not small.empty:
            return [finding(
                self, Severity.WARN,
                f"{len(small)} domain(s) hold under {ctx.t['slice_min_frac'] * 100:.0f}% of the data: "
                + ", ".join(small.index),
                metric={"domains": share.round(4).to_dict()}, details=details,
                fix="Report metrics per domain; overall scores will hide how the model does "
                "on these.",
            )]
        return [finding(self, Severity.INFO, f"{len(share)} domains", details=details,
                        metric={"domains": share.round(4).to_dict()})]
