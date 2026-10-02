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

> **Early preview.** This release ships the interactive CLI and the full check catalog. Dataset scanning is coming in the next release.

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
scandata list-checks                           # every check, in a table
scandata list-checks --section leakage         # one section only
scandata explain leak.near_dup                 # what a check does and why it matters
scandata --version
scandata --help
```

## What it checks

Checks for image classification datasets, grouped by what they protect you from:

| Section | Catches |
|---|---|
| **Integrity** | Corrupt or unreadable files, wrong extensions, mixed color modes, EXIF rotation, blank and tiny images, empty classes |
| **Leakage** | Exact and near-duplicate images across train/val/test, the same image under different labels, source groups split across sets, train/test distribution shift |
| **Labels** | Class imbalance, too few test examples per class, uneven stratification, suspected mislabels, overlapping classes |
| **Quality** | Resolution and aspect-ratio spread, detail lost at training size, blur, exposure, normalisation stats |
| **Shortcuts** | Labels predictable from metadata, filenames, global color or the background alone |
| **Baselines** | Majority-class and linear-probe baselines, learning curve, recommended metric |

Run `scandata list-checks` for the full list, or `scandata explain <check-id>` for details on any one.

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
| `--mode` | `fast` | `fast` runs on a CPU in minutes; `deep` adds embedding-based checks |
| `--splits` | `auto` | `auto`, `none`, or a manifest CSV |
| `--group-regex` | none | Regex with a named group `group` that pulls the source ID (patient, plant, slab) from filenames |
| `--target-size` | none | Training resolution, used to flag detail lost when resizing |
| `--sample` | all | Audit only N images per class |
| `--config` | none | YAML file that overrides thresholds |
| `--out` | `scandata_report.md` | Markdown report path |
| `--json` | none | Machine-readable findings |
| `--fail-on` | none | `blocker` or `warn`: exit with code 1 if findings reach that level |
| `--seed` | `42` | Seed for sampling |

Exit codes: `0` OK, `1` the `--fail-on` threshold was hit, `2` error.

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
