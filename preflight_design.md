# Preflight: design document

**A pre-training dataset auditor. Point it at a folder, say what kind of data it is, and get a Markdown report on what will break your training.**

| | |
|---|---|
| Status | Design v0.1 (draft) |
| Author | Subham Divakar |
| Date | 2026-10-02 |
| v1 scope | Image classification |
| Output | Markdown report (plus JSON for CI) |

---

## 1. Name

**Preflight**. Pilots run a preflight checklist before every takeoff, and you run `preflight` before every training run. The name is short, is a real word, and says what the tool does.

```bash
preflight scan ./SDNET2018 --type image-cls
```

PyPI name: `preflight` is probably taken, so ship the package as **`preflight-ml`** and keep the CLI command as `preflight`.

Backup names: **DataLint** (sounds like "a linter for datasets") or **Vetted**.

---

## 2. Goals and non-goals

### Goals
1. **One command, zero config.** It infers the layout, the splits and the classes.
2. **Catch the mistakes that invalidate results:** leakage, shortcuts and label problems. Cosmetic stats come second.
3. **Every finding is actionable.** Each one comes with evidence (counts and example file paths), a severity, and a concrete fix.
4. **Fast by default, deep when asked.** Fast mode runs on a CPU laptop in minutes. Deep mode uses embeddings on a GPU.
5. **Reproducible and citable.** The report records the dataset fingerprint, the tool version, the seed and the thresholds, so it can go into a paper appendix.
6. **CI-friendly.** Exit codes and a JSON output let it gate a training pipeline.

### Non-goals (v1)
- Cleaning or modifying the dataset in place. Preflight never touches source files. Fixes are exported as a *new* manifest (see v0.3).
- Training production models. The baselines exist only for diagnosis.
- Being a general-purpose plotting or EDA notebook replacement.

---

## 3. How people use it

### 3.1 CLI

```bash
# minimal
preflight scan ./data --type image-cls

# typical research usage
preflight scan ./SDNET2018 --type image-cls \
    --mode deep \
    --group-regex "^(?P<group>[A-Z]+_\d+)_" \
    --target-size 224 \
    --out reports/sdnet_preflight.md

# CI gate: non-zero exit if any BLOCKER
preflight scan ./data --type image-cls --fail-on blocker --json out.json
```

| Flag | Default | Meaning |
|---|---|---|
| `--type` | required | Data category. v1: `image-cls` |
| `--mode` | `fast` | `fast` = hashes and pixel stats only; `deep` = adds embeddings, mislabel detection, linear probe |
| `--splits` | `auto` | `auto`, `none`, or a manifest CSV |
| `--group-regex` | none | Regex with a named group `group` that extracts the source ID from the filename (patients, plants, slabs, source images) |
| `--target-size` | none | Training input resolution, used for the resize-risk check |
| `--sample` | none | Audit only N images per class (for very large datasets) |
| `--config` | none | YAML file that overrides thresholds and enables or disables checks |
| `--out` | `./preflight_report.md` | Path to the Markdown report |
| `--json` | none | Machine-readable findings |
| `--fail-on` | none | `blocker` or `warn`: exit with code 1 if findings at that level or above exist |
| `--seed` | `42` | Seed for all sampling and probes |
| `--device` | `auto` | `cpu`, `cuda` or `mps` for deep mode |

### 3.2 Python API (for notebooks)

```python
import preflight as pf

report = pf.scan("./SDNET2018", type="image-cls", mode="deep",
                 group_regex=r"^(?P<group>[A-Z]+_\d+)_")
report.summary()                 # verdict + scorecard
report.findings(severity="blocker")
report.to_markdown("report.md")
df = report.index                # per-image dataframe: path, label, split, group, stats, hashes
```

### 3.3 Supported folder layouts (auto-detected)

```
A) class folders, no splits      B) split/class folders          C) manifest
data/                            data/                           data/
  cracked/  *.jpg                  train/cracked/ ...              images/...
  uncracked/ *.jpg                 train/uncracked/ ...            labels.csv
                                   val/...                          (path,label[,split][,group])
                                   test/...
```

Detection rules:
- If the top-level folders match `{train, val, valid, validation, test, dev}` (case-insensitive), it's layout B.
- Otherwise, if there's a CSV with a `path` column, it's layout C.
- Otherwise it's layout A.

Nested class hierarchies, such as SDNET2018's `D/CD`, `D/UD`, `P/CP`..., are flattened to leaf folder names. The parent folder is kept as a **`domain`** attribute, which feeds the slice analysis.

---

## 4. Architecture

```
          ┌───────────────┐
 folder ─►│ Loader         │  layout detection → DatasetIndex (one row per file)
          └──────┬────────┘
                 ▼
          ┌───────────────┐   cached in .preflight/cache/ keyed by (sha256, extractor version)
          │ Extractors     │   file meta │ decode + pixel stats │ hashes │ embeddings (deep)
          └──────┬────────┘
                 ▼
          ┌───────────────┐
          │ Check registry │   each Check: requires=[extractors], run(index) → [Finding]
          └──────┬────────┘
                 ▼
          ┌───────────────┐
          │ Scorer         │   severities → per-section status + overall verdict
          └──────┬────────┘
                 ▼
          ┌───────────────┐
          │ Reporters      │   Markdown (+ PNG assets), JSON
          └───────────────┘
```

### 4.1 Core data model

```python
class DatasetIndex:      # wraps a pandas DataFrame
    # columns: path, label, split, group, domain, sha256, bytes, format,
    #          width, height, mode, readable, exif_orientation, ... (extractor outputs)

@dataclass
class Finding:
    check_id: str          # e.g. "leak.near_dup_cross_split"
    severity: Severity     # BLOCKER | WARN | INFO | PASS
    title: str             # one line, human readable
    metric: dict           # numbers that triggered it, e.g. {"pairs": 312, "pct_test": 4.1}
    evidence: list[str]    # example paths or pairs (capped, e.g. 20)
    assets: list[str]      # generated PNGs (thumbnail grids, histograms)
    fix: str               # concrete recommendation

class Check(Protocol):
    id: str
    section: str           # integrity | leakage | labels | quality | shortcuts | baselines
    requires: list[str]    # extractor names
    modes: set[str]        # {"fast","deep"}
    def run(self, idx: DatasetIndex, cfg: Config) -> list[Finding]: ...
```

Checks are registered through a decorator and Python entry points, so third-party plugins can add checks without forking the tool.

### 4.2 Extractors (computed once, cached)

| Extractor | Output | Cost |
|---|---|---|
| `file_meta` | size, extension, magic-byte format, sha256, mtime | very cheap |
| `decode` | readable?, width, height, mode, EXIF (orientation, camera model), JPEG quality estimate | cheap |
| `pixel_stats` | per-channel mean/std, brightness, contrast (RMS), saturation, sharpness (variance of Laplacian), entropy, fraction of clipped pixels, edge density at native and target size | cheap |
| `hashes` | pHash, dHash (64-bit) | cheap |
| `thumb` | 8×8 and 32×32 downsampled vectors | cheap |
| `border` | stats of the outer 10% frame vs the center | cheap |
| `embed` (deep) | DINOv2-S/14 or CLIP ViT-B/32 embeddings, L2-normalised | GPU-friendly |

The image is decoded **once**. All cheap extractors run in the same pass, spread across worker processes.

---

## 5. Severity model and verdict

| Level | Meaning | Example |
|---|---|---|
| **BLOCKER** | Results will be invalid or misleading if you train as-is | Test images duplicated in train; metadata alone predicts the label |
| **WARN** | Likely to hurt performance or the credibility of the evaluation | Imbalance 15:1 with accuracy as the metric; 3% suspected mislabels |
| **INFO** | Worth knowing; affects design choices | Normalisation stats; resolution spread |
| **PASS** | Check ran and found nothing | |

**Verdict** at the top of the report:
- 🔴 **NOT READY** if there's at least one BLOCKER
- 🟡 **READY WITH CAVEATS** if there are WARNs only
- 🟢 **READY** otherwise

Exit codes: `0` ok, `1` the `--fail-on` threshold was hit, `2` tool error.

Every threshold below is a default that can be overridden in YAML. The report prints the thresholds it actually used.

---

## 6. Core check catalog (image classification)

Checks are grouped into six sections, in report order. ⚡ = fast mode; 🧠 = deep mode only.

### Section A: Integrity (garbage in)

| ID | Check | Method | Default severity |
|---|---|---|---|
| `int.unreadable` ⚡ | Corrupt, truncated or zero-byte files | Pillow `verify()` + full decode; zero-byte check | BLOCKER if > 0 |
| `int.format_mismatch` ⚡ | Extension doesn't match the actual format (e.g. `.jpg` that's really a PNG) | magic bytes vs extension | WARN |
| `int.mode_mix` ⚡ | Mixed color modes (L, RGB, RGBA, CMYK, P) | `img.mode` counts | WARN if more than 1 mode; flag if **mode correlates with class** (escalated to Shortcuts) |
| `int.exif_rotation` ⚡ | EXIF orientation ≠ 1 (displays differently from how it trains) | EXIF tag 274 | WARN |
| `int.blank` ⚡ | Near-constant images (all black, white or one color) | std < 2 or entropy < 0.5 | WARN |
| `int.tiny` ⚡ | Images below a minimum size | min side < 32 px or < 0.25 × `--target-size` | WARN |
| `int.non_image` ⚡ | Stray files (`.DS_Store`, `Thumbs.db`, `.txt`) inside class folders | extension allow-list | INFO |
| `int.empty_class` ⚡ | A class folder with 0 or 1 images | counts | BLOCKER (0), WARN (< 10) |

### Section B: Leakage (the results killers)

| ID | Check | Method | Default severity |
|---|---|---|---|
| `leak.exact_dup` ⚡ | Byte-identical files | sha256 groups; reported within-split and **cross-split** separately | Cross-split: BLOCKER. Within: WARN |
| `leak.near_dup` ⚡ | Resized, recompressed or slightly cropped copies | pHash Hamming ≤ 6/64 (configurable); BK-tree or multi-index hashing for O(n log n) | Cross-split: BLOCKER if > 0.5% of test, else WARN |
| `leak.semantic_dup` 🧠 | Same scene or object from a different shot or augmentation | embedding cosine ≥ 0.95; FAISS k-NN (k=5) | Cross-split: WARN (BLOCKER if > 2% of test) |
| `leak.label_conflict` ⚡ | The same image (exact or near dup) appears under **different labels** | cross-reference dup groups with labels | BLOCKER |
| `leak.group` ⚡ | The same source group appears in more than one split | `--group-regex`; if not given, *auto-suggest* groups from filename prefix clustering and near-dup connected components | BLOCKER if groups are declared and overlap; WARN if inferred |
| `leak.no_test_split` ⚡ | No held-out split exists | layout | INFO + recommends a group-aware stratified split (written to `suggested_splits.csv`) |
| `leak.split_stats` ⚡ | Train, val and test drawn from different distributions | label distribution χ² test and Jensen–Shannon divergence; adversarial validation (gradient-boosted classifier on cheap features, plus embeddings in deep mode, separating train from test; 5-fold AUC) | AUC > 0.60 WARN, > 0.75 BLOCKER |

> **Why this section comes first:** near-duplicate leakage across splits is the most common reason published accuracies don't reproduce. Patch datasets such as SDNET2018 are especially exposed, because neighboring patches from one source image are highly correlated. So `leak.group` and `leak.near_dup` treat **connected components of near-duplicates as implicit groups**, and the suggested splits keep whole components together.

### Section C: Labels

| ID | Check | Method | Default severity |
|---|---|---|---|
| `lab.distribution` ⚡ | Class counts and imbalance ratio (max/min) | counts, overall and per split | INFO always; WARN if ratio > 10; recommends metric and weighting |
| `lab.split_coverage` ⚡ | Smallest class has too few examples in val or test to evaluate | per-split counts; reports the 95% CI width of per-class recall given n | WARN if n_test(class) < 30 |
| `lab.stratification` ⚡ | Class proportions differ across splits | max abs difference in proportion | WARN if > 5 percentage points |
| `lab.suspected_mislabel` 🧠 | Likely wrong labels | 5-fold out-of-fold logistic regression on embeddings → confident learning (cleanlab-style `find_label_issues`); ranks images by self-confidence | WARN if > 2%; saves a thumbnail grid of the top 50 per class for manual review |
| `lab.class_overlap` 🧠 | Classes that are hard to separate (possibly ill-defined) | confusion matrix of the linear probe; centroid cosine distance; silhouette per class | INFO; WARN if a class pair is confused more than 30% of the time |
| `lab.outliers` 🧠 | Images far from their own class (wrong domain, junk) | distance to class centroid; isolation forest on embeddings; top-k list | INFO with a grid |

### Section D: Quality and distribution

| ID | Check | Method | Default severity |
|---|---|---|---|
| `qual.resolution` ⚡ | Width, height and aspect-ratio distribution | histograms overall and per class | INFO; WARN if aspect ratio varies so much that a fixed resize distorts > 10% of images |
| `qual.resize_risk` ⚡ | Fine structures lost at the training resolution (thin cracks, small lesions) | ratio of edge density at `--target-size` vs native; flag images losing > 50% of edges | WARN with a before/after grid. Needs `--target-size` |
| `qual.blur` ⚡ | Blurry images | variance of Laplacian; flags the bottom 1% per class, or a robust z-score below −3 | INFO / WARN if the rate differs by class |
| `qual.exposure` ⚡ | Over- or under-exposed images | fraction of clipped pixels > 20% | INFO |
| `qual.normalization` ⚡ | Dataset channel mean and std to use for normalisation | computed from the train split only | INFO, printed as a code snippet ready to paste |
| `qual.slices` ⚡ | Per-domain and per-split breakdown of all the above | groups by `domain` (e.g. Deck / Pavement / Wall) | INFO table; WARN if one slice has < 5% of the data |

### Section E: Shortcuts (can the label be predicted from things that shouldn't predict it?)

Each shortcut check trains a **deliberately handicapped** classifier: gradient boosting or logistic regression, 5-fold CV, reporting balanced accuracy and macro AUC. If a model that can't see the actual content still predicts the label, the real model will learn that shortcut too.

| ID | "Cheater" feature set | Default severity |
|---|---|---|
| `short.metadata` ⚡ | width, height, aspect, file size, format, JPEG quality, color mode, EXIF camera model | AUC > 0.70 WARN, > 0.85 BLOCKER |
| `short.filename` ⚡ | filename tokens and patterns (character n-grams of the basename, folder depth), excluding the class folder name | same thresholds |
| `short.thumbnail` ⚡ | 8×8 color thumbnail (global color and brightness only) | AUC > 0.80 WARN (INFO for classes that really are defined by color) |
| `short.border` ⚡ | border-frame pixels only, center masked out (background bias) | AUC > 0.75 WARN, > 0.90 BLOCKER |
| `short.stat_by_class` ⚡ | single-feature tests: each pixel or meta stat vs label (Kruskal–Wallis + effect size), ranked | INFO: top 5 most label-correlated low-level features |

The report shows feature importances for any shortcut it flags (e.g. *"file size alone gives AUC 0.91: cracked images were saved at higher JPEG quality"*).

### Section F: Baselines and data sufficiency

| ID | Check | Method | Default severity |
|---|---|---|---|
| `base.majority` ⚡ | Accuracy and balanced accuracy of always predicting the majority class | counts | INFO: this is the floor |
| `base.linear_probe` 🧠 | Frozen-embedding logistic regression on train → val/test | macro F1, balanced accuracy, per-class recall | INFO: a realistic "free" baseline. A custom model has to clearly beat it to be worth reporting |
| `base.learning_curve` 🧠 | Linear probe trained on 10/25/50/100% of train | slope of the last segment | INFO: "more data would help" vs "you've plateaued" |
| `base.metric_advice` ⚡ | Recommended primary metric | rule-based on imbalance and task | INFO: e.g. "Use macro-F1 / PR-AUC; accuracy is misleading at 7.3:1" |

---

## 7. Report design (Markdown)

Output: `preflight_report.md` plus `preflight_report_assets/` (PNG thumbnail grids and histograms, referenced with relative links so the report renders on GitHub, VS Code and Obsidian).

### 7.1 Structure

```markdown
# Preflight report: SDNET2018
🔴 **NOT READY**: 2 blockers, 5 warnings, 11 info
Scanned 56,092 images · 6 classes · 3 domains · mode=deep · preflight 0.1.0 · seed 42
Dataset fingerprint: 3f9a…c21 (sha256 of sorted file hashes)

## Scorecard
| Section     | Status | Blockers | Warnings |
|-------------|--------|----------|----------|
| Integrity   | 🟢     | 0        | 0        |
| Leakage     | 🔴     | 1        | 1        |
| Labels      | 🟡     | 0        | 2        |
| Quality     | 🟡     | 0        | 1        |
| Shortcuts   | 🔴     | 1        | 0        |
| Baselines   | ℹ️      | –        | –        |

## Fix these first
1. **[BLOCKER] 1,204 near-duplicate pairs cross train/test (4.3% of test)** → use `suggested_splits.csv` (group-aware, stratified)
2. **[BLOCKER] Border pixels alone predict label (AUC 0.92)** → background differs by class; ...

## A. Integrity
...each finding: metric table, up to 20 example paths, thumbnail grid, fix...

## Dataset card (auto-generated)
Counts per class × split, resolution summary, normalisation stats, split method, known caveats.
Ready to paste into a paper appendix or README.

## Reproducibility
Command line, config with effective thresholds, tool + dependency versions, embedding model, runtime.
```

### 7.2 Side outputs
- `findings.json`: every finding, machine-readable, for CI.
- `index.parquet`: the per-image table with all extracted features, for your own analysis.
- `suggested_splits.csv`: a group-aware, stratified, dedup-safe split (written only when leakage is found or no split exists).
- `review/`: CSVs listing suspected mislabels, outliers and duplicate clusters, for manual review.

---

## 8. Performance and scale

| Concern | Approach |
|---|---|
| Single pass | Decode each image once; all cheap extractors share that decode |
| Parallelism | `ProcessPoolExecutor` with chunked file lists; embeddings run in batches on GPU |
| Caching | `.preflight/cache/` (SQLite or Parquet) keyed by `sha256 + extractor_version`. Re-runs after adding 100 images only process those 100 |
| Near-dup search | BK-tree for Hamming distance (fast); FAISS `IndexFlatIP` / HNSW for embeddings once n > 50k |
| Large datasets | `--sample N` per class for stats checks. Leakage checks always run on the **full** set, because hashes are cheap |
| Budget | Target: 50k images in fast mode in under 5 min on an 8-core CPU; deep mode in under 10 min on a single consumer GPU |

---

## 9. Configuration (YAML)

```yaml
type: image-cls
mode: deep
target_size: 224
group_regex: "^(?P<group>\\d+)_"
embedding_model: dinov2_vits14     # or clip_vitb32
thresholds:
  near_dup_hamming: 6
  semantic_dup_cosine: 0.95
  imbalance_warn: 10
  shortcut_auc_warn: 0.70
  shortcut_auc_block: 0.85
  adv_val_auc_warn: 0.60
checks:
  disable: [qual.exposure]
report:
  max_examples: 20
  thumbnails: true
```

---

## 10. Tech stack and package layout

**Core dependencies:** Python ≥ 3.10, Pillow, numpy, pandas, pyarrow, opencv-python-headless, imagehash, scikit-learn, typer (CLI), jinja2 (Markdown templates), matplotlib.
**Optional extras:** `preflight-ml[deep]` adds torch, timm or open_clip, faiss-cpu/gpu, and cleanlab.

```
preflight/
  cli.py                 # typer app: scan, explain <check_id>, list-checks
  api.py                 # scan() entry point
  core/
    index.py             # DatasetIndex
    finding.py           # Finding, Severity
    registry.py          # @register_check, entry-point discovery
    config.py
    cache.py
  loaders/
    image_folder.py      # layout A/B detection
    manifest.py          # layout C
  extractors/
    file_meta.py  decode.py  pixel_stats.py  hashes.py  border.py  embed.py
  checks/
    image_cls/
      integrity.py  leakage.py  labels.py  quality.py  shortcuts.py  baselines.py
  splitting/
    group_stratified.py  # suggested_splits generator
  report/
    markdown.py  json.py  plots.py  templates/report.md.j2
tests/
  synthetic/             # corruption-injection benchmark (see §12)
```

Extra CLI commands:
- `preflight explain leak.near_dup` prints what a check does, why it matters, and the thresholds it uses.
- `preflight list-checks --type image-cls`

---

## 11. Roadmap

| Version | Scope |
|---|---|
| **v0.1: Core (fast)** | Loaders A/B/C; Integrity; Leakage (exact, near-dup, label conflict, group, split stats); Labels (distribution, coverage, stratification); Quality; Shortcuts (metadata, filename, thumbnail, border); majority baseline; Markdown + JSON report; caching |
| **v0.2: Deep** | Embeddings; semantic dups; suspected mislabels; class overlap and outliers; linear probe; learning curve; adversarial validation on embeddings |
| **v0.3: Fix exports** | `suggested_splits.csv` (group-aware, dedup-safe, stratified); `preflight fix --dedup --drop-corrupt` writes a **clean manifest** (never edits source files); dataset card export |
| **v0.4: Compare** | `preflight compare A B`: cross-dataset shift (e.g. SDNET2018 vs another crack dataset), overlap and dups between datasets, and a diff between versions of the same dataset |
| **v0.5: More image tasks** | Detection (COCO/YOLO): box sanity, tiny/huge boxes, missing labels, class co-occurrence. Segmentation: mask validity, empty masks, label-ID consistency |
| **v0.6: Tabular** | Missingness patterns, target leakage (single-feature AUC), cardinality, unseen categories, unit inconsistency, adversarial validation |
| **v0.7: Time series and text** | Temporal leakage, gaps, stationarity; text dups, boilerplate leakage, length and language stats, contamination checks |
| **v0.8: Domain packs** | Medical (patient-level splitting, site and scanner effects, prevalence), remote sensing, agriculture |
| **v1.0** | Stable plugin API, GitHub Action, optional HTML report, docs site, benchmark paper |

---

## 12. How we know Preflight works (validating the tool)

A dataset auditor has to be audited too. Build a **corruption-injection benchmark**:

1. Take clean, well-curated datasets (e.g. a deduplicated subset of PlantVillage, CIFAR-10 test, or Imagenette).
2. Inject known defects at controlled rates: cross-split duplicates (exact, resized, JPEG-recompressed, cropped), label flips (symmetric and class-conditional), metadata shortcuts (one class saved at a different JPEG quality or size), background shortcuts (pasting class-specific borders), corrupt files, and group leakage.
3. Measure **precision and recall per check** at each injection rate. Report the minimum detectable rate.
4. Run regression tests on known real-world issues, such as near-duplicates in public benchmarks and background bias in PlantVillage.

This benchmark doubles as material for a short **tool/benchmark paper** (e.g. a JOSS submission, or a NeurIPS Datasets & Benchmarks–style workshop paper).

---

## 13. Open questions

1. Default embedding model: DINOv2-S (better for near-dups and fine texture) or CLIP B/32 (more semantic, more familiar)? Leaning DINOv2.
2. Should `--group-regex` inference be on by default, or always ask? Auto-inferred groups could produce false-positive BLOCKERs, so they're currently WARN only.
3. When images are legitimately defined by color, `short.thumbnail` will always fire. Should there be a per-dataset "expected signals" allow-list?
4. Licensing: MIT or Apache-2.0?

---

## 14. First milestone (v0.1 build order)

1. `DatasetIndex` + image-folder loader + `file_meta`/`decode` extractors + cache
2. Integrity checks + Markdown reporter skeleton (verdict, scorecard, findings)
3. Hashes + exact and near-dup + label conflict + cross-split logic
4. Label distribution, coverage and stratification checks
5. Pixel stats + quality checks + normalisation snippet
6. Shortcut probes (metadata, filename, thumbnail, border)
7. Group leakage + `suggested_splits.csv`
8. Synthetic benchmark for checks 2–7 → tune default thresholds
9. Run it on SDNET2018 as the first real-world report
