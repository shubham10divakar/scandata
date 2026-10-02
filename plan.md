# ScanData (SD): implementation plan

> Pre-training dataset auditor with an interactive CLI.
> Source design: [`preflight_design.md`](preflight_design.md). This plan renames *Preflight* to **ScanData**, adds an interactive menu-driven CLI, and lays out how to ship it as a pip-installable package.

| | |
|---|---|
| Status | Plan v0.1 |
| Author | Subham Divakar |
| Date | 2026-10-02 |
| PyPI name | `scandata` (checked 2026-10-02: available) |
| Import name | `scandata` (`import scandata as sd`) |
| CLI command | `scandata` |
| License | MIT |
| Brand color | cyan |
| Python | ≥ 3.10 |

---

## 1. What changes from the design doc

The design doc stays the source of truth for **what the tool checks** (sections A–F, severity model, report format). This plan covers **how it's packaged and how people interact with it**.

| Design doc (Preflight) | ScanData |
|---|---|
| `preflight` command | `scandata` |
| PyPI `preflight-ml` | PyPI `scandata` |
| `import preflight as pf` | `import scandata as sd` |
| `preflight_report.md` | `scandata_report.md` (+ `scandata_report_assets/`) |
| `.preflight/cache/` | `.scandata/cache/` |
| `preflight-ml[deep]` | `scandata[deep]` |
| Flags-only CLI | **Interactive menu** when run with no arguments, plus the same flag-based subcommands for scripts and CI |

Everything else (checks, IDs like `leak.near_dup`, thresholds, exit codes 0/1/2, roadmap) carries over unchanged.

---

## 2. CLI experience

### 2.1 Two ways in

```bash
scandata                      # interactive mode: banner + menu (needs a TTY)

scandata scan ./data --type image-cls --out report.md   # direct mode, no menu
scandata list-checks --type image-cls
scandata explain leak.near_dup
scandata --version
```

Rules:
- **No arguments + interactive terminal** → banner, then the main menu.
- **No arguments + not a TTY** (piped, CI) → print `--help` and exit 0. Never block waiting for input in CI.
- **Any subcommand** → run it directly, no menu. A short one-line banner is printed unless `--quiet` / `--no-banner`.

### 2.2 Welcome screen

Shown on interactive start:

```
   ____                  ____        _
  / ___|  ___ __ _ _ __ |  _ \  __ _| |_ __ _
  \___ \ / __/ _` | '_ \| | | |/ _` | __/ _` |
   ___) | (_| (_| | | | | |_| | (_| | || (_| |
  |____/ \___\__,_|_| |_|____/ \__,_|\__\__,_|

  ScanData v0.1.0 · audit your dataset before you train on it
  Built with ❤ by Subham Divakar
```

Details:
- ASCII art is a hard-coded string (no `pyfiglet` dependency), rendered in a Rich `Panel` with the brand color.
- The heart is rendered in red with Rich (`[red]❤[/red]`).
- **Windows fallback:** if `sys.stdout.encoding` can't encode `❤` (old `cmd.exe` code pages), print `<3` instead.
- `NO_COLOR` env var and `--no-color` flag are respected.

### 2.3 Menu tree

Arrow keys to move, Enter to select. Every screen below the main menu ends with **← Back** and **⌂ Main menu**.

```
Main menu
├── 1. Scan a dataset
│     ├── Choose folder            (path prompt with tab-completion + validation)
│     ├── Data type                (image-cls; others listed as "coming soon", disabled)
│     ├── Mode                     (fast | deep; deep disabled if extras not installed)
│     ├── Advanced options  ▸      (optional sub-screen)
│     │     ├── Group regex
│     │     ├── Target size
│     │     ├── Sample N per class
│     │     ├── Seed
│     │     ├── Device (auto/cpu/cuda/mps)
│     │     ├── Config YAML
│     │     └── ← Back
│     ├── Output path
│     ├── Review & confirm         (summary table + the equivalent CLI command)
│     └── Run → progress bars → Results screen
│
├── 2. Results (last scan)
│     ├── Verdict + scorecard
│     ├── Browse findings by section  ▸  (A Integrity … F Baselines → finding detail)
│     ├── Fix these first (blockers)
│     ├── Open report file           (opens .md with the OS default app)
│     ├── Export JSON
│     └── ← Back / ⌂ Main menu
│
├── 3. Browse checks
│     ├── Pick section (A–F)
│     ├── Pick check → explain: what it does, why it matters, method, thresholds
│     └── ← Back
│
├── 4. Recent scans               (history from ~/.scandata/history.json; reopen any)
│
├── 5. Settings                   (saved to ~/.scandata/settings.json)
│     ├── Default mode
│     ├── Default output folder
│     ├── View effective thresholds
│     ├── Color on/off
│     └── Reset to defaults
│
├── 6. Help & about               (keyboard shortcuts, docs link, version, credits)
│
└── 0. Exit                       ("Thanks for using ScanData ❤")
```

The **Review & confirm** screen prints the equivalent one-line command (`scandata scan ./data --type image-cls --mode fast ...`). People learn the flags from the menu and can copy the command into scripts later.

### 2.4 Navigation model

Implemented as a **screen stack**, not nested `if/else`:

```python
class Screen(Protocol):
    title: str
    def render(self, ctx: AppContext) -> NavAction: ...

# NavAction = Push(screen) | Pop() | Home() | Exit() | Stay()
```

- `Navigator` holds the stack. `Push` goes forward, `Pop` goes back one screen, `Home` clears to the main menu.
- A breadcrumb is shown at the top of each screen: `ScanData › Scan a dataset › Advanced options`.
- Keys: **Esc** or **Ctrl+C** inside a prompt = Back (one level). Ctrl+C on the main menu asks "Exit ScanData? (y/N)".
- `AppContext` holds shared state across screens: the in-progress scan options, the last `Report`, and settings. Going back never loses what was already typed in the wizard.
- A crash inside a screen is caught, shown as a red panel with the error, and returns to the previous screen. `--debug` shows the full traceback.

### 2.5 Libraries

| Need | Choice | Why |
|---|---|---|
| Subcommands, flags, `--help` | **Typer** | As in the design doc; type-hinted, built on Click |
| Banner, panels, tables, progress bars | **Rich** | Already a Typer dependency; good Windows support |
| Arrow-key menus, prompts, path completion | **questionary** | Works on Windows Terminal, PowerShell and cmd; supports disabled choices and validation |

The menu layer only *collects options* and then calls the same `scandata.api.scan()` that the direct `scan` subcommand calls. No business logic lives in the UI.

---

## 3. Packaging (pip installable)

### 3.1 Repository layout

```
code_repo/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── plan.md
├── preflight_design.md
├── src/
│   └── scandata/
│       ├── __init__.py            # __version__, scan(), Report
│       ├── __main__.py            # `python -m scandata`
│       ├── api.py                 # scan() entry point
│       ├── cli/
│       │   ├── app.py             # Typer app: scan, list-checks, explain, version
│       │   ├── banner.py          # ASCII art, "Built with ❤ by Subham Divakar"
│       │   ├── theme.py           # colors, encoding fallback, NO_COLOR
│       │   ├── navigator.py       # screen stack, NavAction, breadcrumbs
│       │   ├── context.py         # AppContext (wizard state, last report, settings)
│       │   └── screens/
│       │       ├── main_menu.py
│       │       ├── scan_wizard.py
│       │       ├── advanced.py
│       │       ├── results.py
│       │       ├── checks_browser.py
│       │       ├── history.py
│       │       ├── settings.py
│       │       └── help.py
│       ├── core/                  # index.py, finding.py, registry.py, config.py, cache.py
│       ├── loaders/               # image_folder.py, manifest.py
│       ├── extractors/            # file_meta, decode, pixel_stats, hashes, border, embed
│       ├── checks/image_cls/      # integrity, leakage, labels, quality, shortcuts, baselines
│       ├── splitting/             # group_stratified.py
│       └── report/                # markdown.py, json.py, plots.py, templates/report.md.j2
└── tests/
    ├── cli/                       # banner, navigator, direct subcommands
    ├── unit/
    └── synthetic/                 # corruption-injection benchmark (design §12)
```

`src/` layout so tests always run against the installed package, not the working folder.

### 3.2 `pyproject.toml` (sketch)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "scandata"
dynamic = ["version"]
description = "Audit your dataset before you train on it: leakage, label issues, shortcuts and quality, in one report."
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
authors = [{ name = "Subham Divakar" }]
keywords = ["eda", "dataset", "data-quality", "machine-learning", "leakage", "audit"]
dependencies = [
  "typer>=0.12",
  "rich>=13",
  "questionary>=2.0",
  "pillow>=10",
  "numpy>=1.24",
  "pandas>=2.0",
  "pyarrow>=14",
  "opencv-python-headless>=4.8",
  "imagehash>=4.3",
  "scikit-learn>=1.3",
  "jinja2>=3.1",
  "matplotlib>=3.7",
  "pyyaml>=6",
]

[project.optional-dependencies]
deep = ["torch>=2.1", "timm>=0.9", "faiss-cpu>=1.7", "cleanlab>=2.6"]
dev  = ["pytest>=8", "pytest-cov", "ruff", "mypy", "build", "twine"]

[project.scripts]
scandata = "scandata.cli.app:main"

[project.entry-points."scandata.checks"]
# third-party plugins register checks here (design §4.1)

[tool.hatch.version]
path = "src/scandata/__init__.py"
```

Phase 0 ships only the CLI dependencies (`typer`, `rich`, `questionary`). The engine dependencies above (Pillow, numpy, pandas, OpenCV, ...) are added to `pyproject.toml` as the Phase 1 steps that need them land, so the shell installs fast.

Install paths:

```bash
pip install scandata            # fast mode
pip install "scandata[deep]"    # + embeddings, mislabel detection, linear probe
pip install -e ".[dev]"         # local development
```

### 3.3 Release flow

1. Bump `__version__` and `CHANGELOG.md`.
2. `python -m build` → `dist/*.whl` + `*.tar.gz`.
3. `twine check dist/*`, then upload to **TestPyPI** and do a clean install in a fresh venv on Windows and Linux.
4. Upload to PyPI. Later: a GitHub Action publishes on tag `v*` via trusted publishing.

---

## 4. Build phases

### Phase 0: Scaffolding and CLI shell ✅ done (2026-10-02)

Goal: `pip install -e .` works and `scandata` shows the banner and a fully navigable menu, with placeholder screens where the engine isn't built yet.

1. `git init`, `.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`
2. `src/scandata/__init__.py` with `__version__ = "0.1.0.dev0"`
3. `cli/banner.py` + `cli/theme.py` (ASCII art, ❤ with Windows fallback, NO_COLOR)
4. `cli/navigator.py` + `cli/context.py` (screen stack, breadcrumbs, Esc/Ctrl+C = back)
5. All screens from §2.3, with stub actions ("coming in v0.1")
6. Typer subcommands `scan`, `list-checks`, `explain`, `version`, wired to stubs
7. Non-TTY detection (print help instead of the menu)
8. Tests: banner renders, navigator push/pop/home, subcommands exit 0, `scandata` resolves
9. Ruff + pytest config

**Done when:** a fresh venv → `pip install -e .` → `scandata` opens the menu, every menu item is reachable, and Back / Main menu work from every screen.

### Phase 1: v0.1 core engine (design §14 build order) 🚧 steps 1–7 done (2026-10-02)

1. ✅ `DatasetIndex` + image-folder loader (layouts A/B) + manifest loader (C) + `file_meta` / `decode` extractors + cache
2. ✅ Integrity checks + Markdown reporter skeleton (verdict, scorecard, findings)
3. ✅ Hashes + exact and near-dup + label conflict + cross-split logic
4. ✅ Label distribution, coverage and stratification checks
5. ✅ Pixel stats + quality checks + normalisation snippet
6. ✅ Shortcut probes (metadata, filename, thumbnail, border)
7. ✅ Group leakage + `suggested_splits.csv`
8. 🚧 Synthetic benchmark: defect, shortcut and clean datasets exist as tests (every injected defect found; no false alarms on clean data). Still to do: injection at controlled rates, precision/recall per check, threshold tuning.
9. ⏳ First real report on SDNET2018 (needs the dataset on this machine)

The menu screens are live: **Scan wizard** runs the engine with a progress bar, **Results** shows verdict, scorecard, fix-first list and findings by section, **Recent scans** reopens reports.

**Measured:** 10,000 images (128 px, 16-core laptop): about 45 s cold, about 6.5 s warm (cached features). Design target was 50k images in under 5 minutes in fast mode.

#### Implementation decisions (where the build differs from the design doc)

| Design | Built | Why |
|---|---|---|
| OpenCV, `imagehash`, jinja2, matplotlib | numpy implementations of pHash/dHash, Laplacian and Sobel; report built in Python; grids drawn with Pillow | Smaller install, no compiled extras beyond numpy/scipy/sklearn |
| Cache keyed by `sha256 + extractor version` | Keyed by path + size + mtime + extractor version + target size, in `~/.scandata/cache` | A lookup doesn't need to read the file; nothing is written into the dataset folder |
| `short.metadata` includes file size | File size reported as a note, not scored | File size grows with image detail, so it separates classes whenever content differs (e.g. cracks). It caused false BLOCKERs on synthetic crack data |
| `short.filename` on raw basenames | Per-class naming tokens (`cat` in `cat.123.jpg`, `cr` in `cr0001.jpg`) are stripped first and listed in the report | Naming files by class is normal and invisible to the model; without this nearly every dataset got a BLOCKER |
| Thumbnail/border probes with gradient boosting | Scaled logistic regression | About 20x faster, still catches background and color shortcuts |
| (not in design) | BLAS/OpenMP threads capped at 4 while checks run | numpy and scipy each start an OpenBLAS pool; on 16 cores they oversubscribed and a 0.5 s probe took 27 s |
| (not in design) | Adversarial validation skipped when a split has under 50 images | AUCs on a handful of images are noise and produced false WARNs |
| `--sample` limits stats checks only | `--sample` applies to the whole scan | Hashes come from the same decode pass as the stats, so sampling only stats saves nothing |
| `index.parquet` | `index.csv` | Avoids a pyarrow dependency for now |

### Phase 2: CLI polish (mostly built during Phase 1)

- ✅ Progress bar with ETA during extraction and checks
- ✅ Verdict and scorecard at the end of a scan, then the Results screen
- ✅ `Recent scans` history and reopening old reports
- ✅ `--fail-on` and `--json` for CI, exit codes 0/1/2
- ⏳ Export JSON / suggested splits from the Results screen; settings for workers and cache

### Phase 3: First PyPI release (`scandata 0.1.0`)

- README with a GIF of the interactive menu and a sample report
- TestPyPI → PyPI
- Smoke test on Windows (PowerShell, cmd, Windows Terminal), macOS and Linux

### Later

Follow the design doc roadmap (§11): v0.2 deep mode, v0.3 fix exports, v0.4 compare, then detection/segmentation, tabular, time series and text, domain packs. Each new data type shows up in the **Data type** picker of the scan wizard, moving from "coming soon" to enabled.

---

## 5. Testing the CLI

| What | How |
|---|---|
| Direct subcommands | `typer.testing.CliRunner`, assert exit codes and output |
| Banner | Render to a Rich `Console(record=True)`; check the name, version and credit line; check the `<3` fallback with a fake cp1252 stream |
| Navigation | Unit-test `Navigator` with scripted `NavAction`s (no terminal needed) |
| Screens | Inject a fake prompt backend (questionary is wrapped behind a small `Prompter` interface) and feed scripted answers |
| Non-TTY | Run `scandata` with stdin redirected; assert it prints help and exits 0 |
| Packaging | CI job: build the wheel, install it in a clean venv, run `scandata --version` |

---

## 6. Decisions

Resolved on 2026-10-02:
1. **License:** MIT.
2. **Command:** `scandata` only. No `sd` alias (it clashes with the popular `sd` find-and-replace tool). `sd` stays as the import nickname: `import scandata as sd`.
3. **Brand color:** cyan.

Still open (from the design doc): default embedding model (DINOv2-S vs CLIP B/32), group-regex auto-inference, color-defined classes and `short.thumbnail`.
