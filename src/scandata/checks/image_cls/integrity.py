"""Section A: Integrity (garbage in)."""

from __future__ import annotations

import pandas as pd

from scandata.analysis.grids import save_grid
from scandata.checks.image_cls._util import examples, finding, md_table, passed, pct
from scandata.core.context import ScanContext
from scandata.core.finding import Severity
from scandata.core.registry import Check, register


@register
class Unreadable(Check):
    id = "int.unreadable"
    section = "integrity"
    title = "Corrupt, truncated or zero-byte files"

    def run(self, ctx: ScanContext):
        df = ctx.index.df
        bad = df[~df["readable"]]
        if bad.empty:
            return passed(self, f"All {len(df):,} images decode cleanly")
        reasons = bad["error"].fillna("unknown").str.split(":").str[0].value_counts()
        return [finding(
            self, Severity.BLOCKER,
            f"{len(bad):,} image(s) can't be decoded ({pct(len(bad), len(df))}%)",
            metric={"unreadable": len(bad), "pct": pct(len(bad), len(df))},
            evidence=examples(bad, ctx, note="error"),
            details=md_table(["reason", "files"], reasons.items()),
            fix="Remove or re-export these files. Most data loaders crash or silently skip "
            "them mid-epoch.",
        )]


@register
class FormatMismatch(Check):
    id = "int.format_mismatch"
    section = "integrity"
    title = "Extension doesn't match the actual format"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        wrong = df[df["magic_format"].notna() & (df["magic_format"] != df["ext_format"])]
        if wrong.empty:
            return passed(self, "File extensions match the real formats")
        kinds = (wrong["ext"] + " is really " + wrong["magic_format"]).value_counts()
        return [finding(
            self, Severity.WARN,
            f"{len(wrong):,} file(s) have an extension that doesn't match their format",
            metric={"files": len(wrong)},
            evidence=examples(wrong, ctx),
            details=md_table(["mismatch", "files"], kinds.items()),
            fix="Rename or re-encode them. Some loaders pick the decoder from the extension.",
        )]


@register
class ModeMix(Check):
    id = "int.mode_mix"
    section = "integrity"
    title = "Mixed color modes"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        modes = df["mode"].value_counts()
        if len(modes) <= 1:
            return passed(self, f"All images share one color mode ({modes.index[0]})")
        by_class = pd.crosstab(df["label"], df["mode"])
        # classes whose dominant mode differs from the overall dominant mode
        dominant = modes.index[0]
        odd = [c for c in by_class.index if by_class.loc[c].idxmax() != dominant]
        note = (
            f" Mode depends on class ({', '.join(odd)}): see the metadata shortcut check."
            if odd else ""
        )
        return [finding(
            self, Severity.WARN,
            f"{len(modes)} color modes mixed: " + ", ".join(f"{m} ({n:,})" for m, n in modes.items()),
            metric={"modes": modes.to_dict(), "class_dependent": bool(odd)},
            evidence=examples(df[df["mode"] != dominant], ctx, note="mode"),
            details=md_table(["class", *by_class.columns],
                             [[c, *r] for c, r in zip(by_class.index, by_class.to_numpy().tolist(),
                                                      strict=True)]),
            fix=f"Convert everything to one mode (usually RGB) in preprocessing.{note}",
        )]


@register
class ExifRotation(Check):
    id = "int.exif_rotation"
    section = "integrity"
    title = "EXIF orientation is not 1"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        rotated = df[df["exif_orientation"].notna() & (df["exif_orientation"] != 1)]
        rotated = rotated.assign(exif_orientation=rotated["exif_orientation"].astype(int))
        if rotated.empty:
            return passed(self, "No EXIF rotation flags")
        return [finding(
            self, Severity.WARN,
            f"{len(rotated):,} image(s) carry an EXIF rotation flag",
            metric={"files": len(rotated)},
            evidence=examples(rotated, ctx, note="exif_orientation"),
            fix="These display rotated in viewers but most training pipelines load them "
            "unrotated. Apply `ImageOps.exif_transpose` once and re-save, or do it in the loader.",
        )]


@register
class Blank(Check):
    id = "int.blank"
    section = "integrity"
    title = "Near-constant images"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        blank = df[(df["contrast"] < ctx.t["blank_std"]) | (df["entropy"] < ctx.t["blank_entropy"])]
        if blank.empty:
            return passed(self, "No blank or single-color images")
        assets = []
        out = ctx.asset_path("int_blank.png")
        if out:
            name = save_grid([(r.path, r.label) for r in blank.head(16).itertuples()], out)
            assets = [name] if name else []
        return [finding(
            self, Severity.WARN,
            f"{len(blank):,} near-constant image(s) (all black, white or one color)",
            metric={"files": len(blank), "by_class": blank["label"].value_counts().to_dict()},
            evidence=examples(blank, ctx), assets=assets,
            fix="Check the capture/export step and drop them; they carry no signal.",
        )]


@register
class Tiny(Check):
    id = "int.tiny"
    section = "integrity"
    title = "Images below a minimum size"

    def run(self, ctx: ScanContext):
        df = ctx.index.readable
        limit = ctx.t["tiny_min_side"]
        if ctx.options.target_size:
            limit = max(limit, 0.25 * ctx.options.target_size)
        side = df[["width", "height"]].min(axis=1)
        tiny = df[side < limit].assign(
            size=lambda d: d["width"].astype(int).astype(str) + "x" + d["height"].astype(int).astype(str)
        )
        if tiny.empty:
            return passed(self, f"Every image is at least {limit:g} px on its shorter side")
        return [finding(
            self, Severity.WARN,
            f"{len(tiny):,} image(s) smaller than {limit:g} px on the shorter side",
            metric={"files": len(tiny), "min_side_px": limit},
            evidence=examples(tiny, ctx, note="size"),
            fix="Upscaling these adds blur the model may learn as a class cue. Drop or re-collect.",
        )]


@register
class NonImage(Check):
    id = "int.non_image"
    section = "integrity"
    title = "Stray files"

    def run(self, ctx: ScanContext):
        stray = ctx.index.stray
        if not stray:
            return passed(self, "No stray files in the dataset folders")
        reasons = pd.Series([r for _, r in stray]).value_counts()
        return [finding(
            self, Severity.INFO,
            f"{len(stray):,} file(s) ignored (not images, or outside class folders)",
            metric={"files": len(stray)},
            evidence=[f"{p}  ({r})" for p, r in stray[: ctx.max_examples]],
            details=md_table(["reason", "files"], reasons.items()),
            fix="Remove them, or make sure your loader filters by extension.",
        )]


@register
class EmptyClass(Check):
    id = "int.empty_class"
    section = "integrity"
    title = "Empty or tiny classes"

    def run(self, ctx: ScanContext):
        counts = ctx.index.class_counts or ctx.index.df["label"].value_counts().to_dict()
        empty = sorted(c for c, n in counts.items() if n == 0)
        small = sorted((c, n) for c, n in counts.items() if 0 < n < ctx.t["empty_class_warn"])
        labelled = [c for c, n in counts.items() if n > 0]
        out = []
        if len(labelled) < 2:
            out.append(finding(
                self, Severity.BLOCKER, f"Only {len(labelled)} class(es) with images found",
                metric={"classes": len(labelled)},
                fix="Classification needs at least two classes. Check the folder layout: "
                "images should sit in one folder per class.",
            ))
        if empty:
            out.append(finding(
                self, Severity.BLOCKER, f"{len(empty)} class folder(s) contain no images",
                metric={"empty": empty}, evidence=empty,
                fix="Remove the empty folders or add images; frameworks still create a "
                "class index for them.",
            ))
        if small:
            out.append(finding(
                self, Severity.WARN,
                f"{len(small)} class(es) have fewer than {ctx.t['empty_class_warn']:g} images",
                metric={"small": dict(small)}, evidence=[f"{c}  ({n})" for c, n in small],
                fix="Collect more examples or merge these classes; results on them won't be "
                "reliable.",
            ))
        return out or passed(self, f"All {len(counts)} classes have images")
