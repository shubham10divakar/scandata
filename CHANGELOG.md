# Changelog

## 0.1.0 (unreleased)

Dataset scanning for image classification (fast mode).

- Reads class-folder, split-folder and CSV-manifest datasets; nested folders become domains; `--group-regex` extracts source IDs.
- 30 checks across integrity, leakage, labels, quality, shortcuts and baselines, each with a severity, evidence and a fix.
- Near-duplicate detection across splits (perceptual hashes), label conflicts, source-group leakage and train/test distribution shift.
- Shortcut probes: can metadata, filenames, global color or the background alone predict the label?
- Markdown report with verdict, scorecard, fix-first list, thumbnail grids, dataset card and reproducibility details; `findings.json`; per-image `index.csv`; duplicate-cluster review CSV.
- `suggested_splits.csv`: group-aware, stratified, duplicate-safe train/val/test split.
- Feature cache so re-scans only process new or changed files; parallel image reading.
- Interactive menu runs scans with a progress bar and lets you browse results, the fix-first list and findings by section, and reopen recent reports.
- `--fail-on blocker|warn` for CI; `--config` YAML threshold overrides; `--workers`, `--no-cache`.

## 0.0.1 (2026-10-02)

First public preview.

- Interactive CLI: run `scandata` for a welcome screen and a menu with Back / Main menu on every screen. Esc or Ctrl+C goes back.
- Scan wizard with all scan options, a review screen and the equivalent one-line command.
- Browse the full check catalog for image classification (integrity, leakage, labels, quality, shortcuts, baselines).
- Settings saved between sessions.
- Direct commands: `scandata scan`, `scandata list-checks`, `scandata explain`, `scandata --version`.
- Dataset scanning is not included yet; `scandata scan` validates the options and exits with code 2.
