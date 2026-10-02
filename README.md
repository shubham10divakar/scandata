# ScanData

[![PyPI version](https://img.shields.io/pypi/v/scandata?color=0aa3c2)](https://pypi.org/project/scandata/)
[![Python versions](https://img.shields.io/pypi/pyversions/scandata)](https://pypi.org/project/scandata/)
[![Downloads](https://static.pepy.tech/badge/scandata)](https://pepy.tech/project/scandata)
[![Monthly downloads](https://img.shields.io/pypi/dm/scandata)](https://pypistats.org/packages/scandata)
[![Tests](https://github.com/shubham10divakar/scandata/actions/workflows/tests.yml/badge.svg)](https://github.com/shubham10divakar/scandata/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/shubham10divakar/scandata/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![GitHub stars](https://img.shields.io/github/stars/shubham10divakar/scandata?style=social)](https://github.com/shubham10divakar/scandata)

**Audit your ML dataset before you train on it.**

Point ScanData at a dataset folder and it tells you what will break your training: leakage between splits, label problems, shortcuts the model can cheat with, and image quality issues. Every finding comes with a severity, evidence and a concrete fix.

## Install

```bash
pip install scandata
```

Requires Python 3.10 or newer. Works on Windows, macOS and Linux.

## Quick start

Run it with no arguments to open the interactive menu:

```bash
scandata
```

```
   ____                  ____        _
  / ___|  ___ __ _ _ __ |  _ \  __ _| |_ __ _
  \___ \ / __/ _` | '_ \| | | |/ _` | __/ _` |
   ___) | (_| (_| | | | | |_| | (_| | || (_| |
  |____/ \___\__,_|_| |_|____/ \__,_|\__\__,_|

  ScanData · audit your dataset before you train on it
  Built with ❤ by Subham Divakar

› What would you like to do?
  » 1. Scan a dataset
    2. Results (last scan)
    3. Browse checks
    4. Recent scans
    5. Settings
    6. Help & about
    0. Exit
```

| Key | Action |
|---|---|
| ↑ / ↓ | Move |
| Enter | Select |
| Esc or Ctrl+C | Back one screen |
| ← Back / ⌂ Main menu | At the bottom of every screen |

Or skip the menu and run commands directly, which is handy in scripts and CI:

```bash
scandata scan ./data --type image-cls          # scan a dataset folder
scandata scan ./data --type image-cls --target-size 224 --fail-on blocker
scandata list-checks                           # every check, in a table
scandata list-checks --section leakage         # one section only
scandata explain leak.near_dup                 # what a check does and why it matters
scandata --version
scandata --help
```

## What you get

```
╭──────────────── Verdict ────────────────╮
│ NOT READY                               │
│ 4 blocker(s) · 7 warning(s) · 9 info    │
╰─────────────────────────────────────────╯
 Section     Status    Blockers  Warnings
 Integrity   BLOCKER          1         4
 Leakage     BLOCKER          3         1
 Labels      WARN             0         2
 ...

Fix these first
1. BLOCKER 2 image(s) can't be decoded (2.25%)
2. BLOCKER 1 identical file group(s) span splits (2 files)
3. BLOCKER 2 near-duplicate pair(s) cross splits; 2 test images (14.29%) have a near-copy in train
```

Every scan writes:

| File | What's in it |
|---|---|
| `scandata_report.md` | Verdict (🔴 not ready, 🟡 ready with caveats, 🟢 ready), scorecard, a "fix these first" list, every finding with numbers, example files, thumbnail grids and a concrete fix, a dataset card and reproducibility details |
| `scandata_report_assets/` | Thumbnail grids, `index.csv` (one row per image with every extracted feature) and `review/duplicate_clusters.csv` |
| `suggested_splits.csv` | A train/val/test split that keeps duplicates and source groups together and stratifies by class. Written when there's no split yet or when leakage is found |
| `findings.json` | Every finding, machine-readable (with `--json`) |

ScanData never modifies your dataset. Extracted features are cached in `~/.scandata/cache`, so re-scans only process new or changed files.

## What it checks

Checks for image classification datasets, grouped by what they protect you from:

| Section | Catches |
|---|---|
| **Integrity** | Corrupt or unreadable files, wrong extensions, mixed color modes, EXIF rotation, blank and tiny images, empty classes, stray files |
| **Leakage** | Exact and near-duplicate images across train/val/test, the same image under different labels, source groups split across sets, train/test distribution shift |
| **Labels** | Class imbalance, too few evaluation examples per class, uneven stratification |
| **Quality** | Resolution and aspect-ratio spread, detail lost at training size, blur, exposure, normalisation stats, per-domain breakdown |
| **Shortcuts** | Labels predictable from file metadata, filenames, global color or the background alone |
| **Baselines** | Majority-class baseline and the recommended metric |

Run `scandata list-checks` for the full list, or `scandata explain <check-id>` for details on any one. Deep-mode checks (semantic duplicates, suspected mislabels, class overlap, linear-probe baselines) are on the way.

## Python

```python
import scandata as sd

report = sd.scan("./data", target_size=224)
report.summary()                       # verdict, scorecard, top fixes
report.findings(severity="blocker")    # list of findings
report.index                           # pandas DataFrame, one row per image
report.to_markdown("report.md")
report.to_json("findings.json")
```

## Supported dataset layouts

```
class folders               split / class folders        manifest
data/                       data/                        data/
  cracked/   *.jpg            train/cracked/ ...           images/...
  uncracked/ *.jpg            val/...                      labels.csv
                              test/...                     (path,label[,split][,group])
```

ScanData works out the layout automatically.

## Scan options

| Flag | Default | Meaning |
|---|---|---|
| `--type` | required | Data type: `image-cls` |
| `--mode` | `fast` | `fast` runs on a CPU in minutes. `deep` (embedding-based checks) is coming soon |
| `--splits` | `auto` | `auto`, `none`, or a manifest CSV |
| `--group-regex` | none | Regex with a named group `group` that pulls the source ID (patient, plant, slab) from filenames |
| `--target-size` | none | Training resolution, used to flag detail lost when resizing |
| `--sample` | all | Audit only N random images per class |
| `--config` | none | YAML file that overrides thresholds |
| `--out` | `scandata_report.md` | Markdown report path |
| `--json` | none | Machine-readable findings |
| `--fail-on` | none | `blocker` or `warn`: exit with code 1 if findings reach that level |
| `--seed` | `42` | Seed for sampling, probes and suggested splits |
| `--workers` | up to 8 | Worker processes for reading images |
| `--no-cache` | off | Recompute every image's features |

Exit codes: `0` OK, `1` the `--fail-on` threshold was hit, `2` error.

Thresholds can be overridden with `--config`:

```yaml
thresholds:
  near_dup_hamming: 6        # pHash bits that may differ for a near-duplicate
  imbalance_warn: 10
  shortcut_auc_warn: 0.70
checks:
  disable: [qual.exposure]
report:
  max_examples: 20
  thumbnails: true
```

Every report lists the thresholds it actually used.

## Contributing

Contributions are welcome, whether it's a bug report, a new check idea, docs or code. Feel free to reach out: open an [issue](https://github.com/shubham10divakar/scandata/issues) or contact me through [GitHub](https://github.com/shubham10divakar).

**To contribute code:**

1. Fork the repo and clone your fork:
   ```bash
   git clone https://github.com/<your-username>/scandata.git
   cd scandata
   ```
2. Create a virtual environment and install in editable mode with the dev tools:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
3. Create a branch for your change:
   ```bash
   git checkout -b my-change
   ```
4. Make your change, then run the tests and the linter:
   ```bash
   pytest
   ruff check src tests
   ```
5. Push your branch and open a pull request describing what you changed and why.

For larger changes, such as a new check or data type, please open an issue first so we can agree on the approach.

## License

[MIT](https://github.com/shubham10divakar/scandata/blob/main/LICENSE)

Built with ❤ by **Subham Divakar**.
