"""Static catalog of planned checks (design doc §6).

Phase 0 uses this for `list-checks`, `explain` and the Browse checks menu.
From Phase 1 the live check registry replaces it, keeping the same fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckInfo:
    id: str
    section: str
    title: str
    method: str
    severity: str
    deep_only: bool = False

    @property
    def modes(self) -> str:
        return "deep" if self.deep_only else "fast, deep"


SECTIONS: dict[str, str] = {
    "integrity": "A. Integrity",
    "leakage": "B. Leakage",
    "labels": "C. Labels",
    "quality": "D. Quality and distribution",
    "shortcuts": "E. Shortcuts",
    "baselines": "F. Baselines and data sufficiency",
}

SECTION_WHY: dict[str, str] = {
    "integrity": "Garbage in: files that can't be read or don't look like what they claim.",
    "leakage": "The results killers: the same content in train and test inflates every metric.",
    "labels": "Wrong or unbalanced labels decide what the model learns and how you should "
    "measure it.",
    "quality": "Resolution, blur and exposure shape what survives preprocessing.",
    "shortcuts": "If a model that can't see the content still predicts the label, your real "
    "model will learn that shortcut too.",
    "baselines": "The floor a real model has to clearly beat to be worth reporting.",
}

_C = CheckInfo
CHECKS: dict[str, list[CheckInfo]] = {
    "image-cls": [
        # A. Integrity
        _C("int.unreadable", "integrity", "Corrupt, truncated or zero-byte files",
           "Pillow verify() + full decode; zero-byte check", "BLOCKER if > 0"),
        _C("int.format_mismatch", "integrity", "Extension doesn't match the actual format",
           "Magic bytes vs extension", "WARN"),
        _C("int.mode_mix", "integrity", "Mixed color modes (L, RGB, RGBA, CMYK, P)",
           "img.mode counts; escalated to Shortcuts if mode correlates with class",
           "WARN if more than 1 mode"),
        _C("int.exif_rotation", "integrity", "EXIF orientation is not 1",
           "EXIF tag 274", "WARN"),
        _C("int.blank", "integrity", "Near-constant images (all black, white or one color)",
           "std < 2 or entropy < 0.5", "WARN"),
        _C("int.tiny", "integrity", "Images below a minimum size",
           "min side < 32 px or < 0.25 x --target-size", "WARN"),
        _C("int.non_image", "integrity", "Stray files inside class folders",
           "Extension allow-list", "INFO"),
        _C("int.empty_class", "integrity", "A class folder with 0 or very few images",
           "Counts", "BLOCKER (0), WARN (< 10)"),
        # B. Leakage
        _C("leak.exact_dup", "leakage", "Byte-identical files",
           "sha256 groups, reported within-split and cross-split",
           "Cross-split BLOCKER, within WARN"),
        _C("leak.near_dup", "leakage", "Resized, recompressed or slightly cropped copies",
           "pHash Hamming <= 6/64; BK-tree search",
           "Cross-split BLOCKER if > 0.5% of test, else WARN"),
        _C("leak.semantic_dup", "leakage", "Same scene or object from a different shot",
           "Embedding cosine >= 0.95; FAISS k-NN (k=5)",
           "Cross-split WARN (BLOCKER if > 2% of test)", deep_only=True),
        _C("leak.label_conflict", "leakage", "The same image appears under different labels",
           "Cross-reference duplicate groups with labels", "BLOCKER"),
        _C("leak.group", "leakage", "The same source group appears in more than one split",
           "--group-regex, or groups inferred from filename prefixes and near-dup components",
           "BLOCKER if declared, WARN if inferred"),
        _C("leak.no_test_split", "leakage", "No held-out split exists",
           "Layout; writes suggested_splits.csv", "INFO"),
        _C("leak.split_stats", "leakage", "Splits drawn from different distributions",
           "Chi-squared + Jensen-Shannon on labels; adversarial validation (5-fold AUC)",
           "AUC > 0.60 WARN, > 0.75 BLOCKER"),
        # C. Labels
        _C("lab.distribution", "labels", "Class counts and imbalance ratio",
           "Counts overall and per split", "INFO; WARN if ratio > 10"),
        _C("lab.split_coverage", "labels", "Too few examples of a class in val/test",
           "Per-split counts; 95% CI width of per-class recall",
           "WARN if n_test(class) < 30"),
        _C("lab.stratification", "labels", "Class proportions differ across splits",
           "Max absolute difference in proportion", "WARN if > 5 pp"),
        _C("lab.suspected_mislabel", "labels", "Likely wrong labels",
           "Out-of-fold logistic regression on embeddings + confident learning",
           "WARN if > 2%", deep_only=True),
        _C("lab.class_overlap", "labels", "Classes that are hard to separate",
           "Linear-probe confusion matrix; centroid distance; silhouette",
           "INFO; WARN if a pair is confused > 30%", deep_only=True),
        _C("lab.outliers", "labels", "Images far from their own class",
           "Distance to class centroid; isolation forest on embeddings",
           "INFO", deep_only=True),
        # D. Quality
        _C("qual.resolution", "quality", "Width, height and aspect-ratio distribution",
           "Histograms overall and per class",
           "INFO; WARN if a fixed resize distorts > 10% of images"),
        _C("qual.resize_risk", "quality", "Fine structures lost at training resolution",
           "Edge density at --target-size vs native", "WARN (needs --target-size)"),
        _C("qual.blur", "quality", "Blurry images",
           "Variance of Laplacian; bottom 1% per class or robust z < -3",
           "INFO; WARN if rate differs by class"),
        _C("qual.exposure", "quality", "Over- or under-exposed images",
           "Fraction of clipped pixels > 20%", "INFO"),
        _C("qual.normalization", "quality", "Channel mean and std for normalisation",
           "Computed from the train split only", "INFO (code snippet)"),
        _C("qual.slices", "quality", "Per-domain and per-split breakdown",
           "Group stats by domain", "INFO; WARN if a slice has < 5% of data"),
        # E. Shortcuts
        _C("short.metadata", "shortcuts", "Label predictable from file metadata",
           "Classifier on width, height, size, format, JPEG quality, mode, camera",
           "AUC > 0.70 WARN, > 0.85 BLOCKER"),
        _C("short.filename", "shortcuts", "Label predictable from filenames",
           "Character n-grams of the basename, folder depth",
           "AUC > 0.70 WARN, > 0.85 BLOCKER"),
        _C("short.thumbnail", "shortcuts", "Label predictable from global color/brightness",
           "Classifier on an 8x8 thumbnail", "AUC > 0.80 WARN"),
        _C("short.border", "shortcuts", "Label predictable from the background",
           "Border-frame pixels only, center masked", "AUC > 0.75 WARN, > 0.90 BLOCKER"),
        _C("short.stat_by_class", "shortcuts", "Low-level features most tied to the label",
           "Kruskal-Wallis + effect size per feature", "INFO (top 5)"),
        # F. Baselines
        _C("base.majority", "baselines", "Majority-class baseline",
           "Accuracy and balanced accuracy of always predicting the majority", "INFO"),
        _C("base.linear_probe", "baselines", "Frozen-embedding linear probe",
           "Logistic regression on embeddings; macro F1, balanced accuracy",
           "INFO", deep_only=True),
        _C("base.learning_curve", "baselines", "Would more data help?",
           "Linear probe on 10/25/50/100% of train", "INFO", deep_only=True),
        _C("base.metric_advice", "baselines", "Recommended primary metric",
           "Rule-based on imbalance and task", "INFO"),
    ],
}


def list_checks(data_type: str = "image-cls", section: str | None = None) -> list[CheckInfo]:
    checks = CHECKS.get(data_type, [])
    return [c for c in checks if section is None or c.section == section]


def get_check(check_id: str) -> CheckInfo | None:
    for checks in CHECKS.values():
        for check in checks:
            if check.id == check_id:
                return check
    return None
