# Changelog

## 0.0.1 (2026-10-02)

First public preview.

- Interactive CLI: run `scandata` for a welcome screen and a menu with Back / Main menu on every screen. Esc or Ctrl+C goes back.
- Scan wizard with all scan options, a review screen and the equivalent one-line command.
- Browse the full check catalog for image classification (integrity, leakage, labels, quality, shortcuts, baselines).
- Settings saved between sessions.
- Direct commands: `scandata scan`, `scandata list-checks`, `scandata explain`, `scandata --version`.
- Dataset scanning is not included yet; `scandata scan` validates the options and exits with code 2.
