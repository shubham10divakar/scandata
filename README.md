# ScanData

**Audit your dataset before you train on it.** ScanData points at a folder, works out the layout, splits and classes, and writes a Markdown report on what will break your training: leakage, label problems, shortcuts and quality issues.

> Status: early development (Phase 0: CLI shell). The scan engine lands in v0.1.

## Install

```bash
pip install scandata            # once released
pip install -e ".[dev]"         # from a local checkout
```

## Use

```bash
scandata                                     # interactive menu
scandata scan ./data --type image-cls        # direct mode (scripts, CI)
scandata list-checks --type image-cls
scandata explain leak.near_dup
scandata --version
```

In the interactive menu, use the arrow keys and Enter. **Esc** or **Ctrl+C** goes back one screen; every screen has **← Back** and **⌂ Main menu**.

## Python

```python
import scandata as sd

report = sd.scan("./data", type="image-cls")   # available from v0.1
```

See [`plan.md`](plan.md) for the build plan and [`preflight_design.md`](preflight_design.md) for the full design.

## License

MIT. Built with ❤ by Subham Divakar.
