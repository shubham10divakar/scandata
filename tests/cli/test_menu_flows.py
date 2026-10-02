"""Drive the interactive menu with scripted answers."""

import json

from scandata.cli.context import BACK, HOME
from scandata.cli.screens import MainMenu
from scandata.core.config import home_dir


def test_exit_from_main_menu(make_app):
    app, _, out = make_app(["exit"])
    app.run(MainMenu())
    text = out.getvalue()
    assert "Built with" in text and "Subham Divakar" in text
    assert "Thanks for using ScanData" in text


def test_esc_on_main_menu_asks_before_exiting(make_app):
    app, prompter, _ = make_app([None, False, None, True])
    app.run(MainMenu())
    assert [m for m, _ in prompter.seen].count("Exit ScanData?") == 2


def test_browse_checks_forward_and_back(make_app):
    app, prompter, out = make_app([
        "label:3. Browse checks",
        "label:B. Leakage",
        "label:leak.near_dup",
        "label:Next: leak.semantic_dup",
        "label:◂ Previous: leak.near_dup",
        BACK,               # detail -> section
        BACK,               # section -> sections
        BACK,               # sections -> main
        "exit",
    ])
    app.run(MainMenu())
    text = out.getvalue()
    assert "pHash Hamming" in text
    assert "Embedding cosine" in text
    assert "ScanData › Browse checks › B. Leakage › leak.near_dup" in text


def test_main_menu_shortcut_from_deep_screen(make_app):
    app, prompter, _ = make_app([
        "label:3. Browse checks", "label:A. Integrity", HOME, "exit",
    ])
    app.run(MainMenu())
    assert prompter.seen[-1][0] == "What would you like to do?"


def test_scan_wizard_keeps_values_when_going_back(make_app, tmp_path):
    app, prompter, out = make_app([
        "label:1. Scan a dataset",
        "label:Dataset folder", str(tmp_path),
        "label:Advanced options", "label:Target size", "224", BACK,
        "label:Review & run",
        "label:▶ Run scan",
        "label:✎ Edit options",
        BACK,               # wizard -> main
        "label:1. Scan a dataset",
        BACK,
        "exit",
    ])
    app.run(MainMenu())
    assert app.options.path == tmp_path
    assert app.options.target_size == 224
    text = out.getvalue()
    assert "Not built yet" in text
    assert "--target-size 224" in text


def test_review_is_disabled_until_folder_chosen(make_app):
    # The fake prompter refuses disabled options; the app shows the error and pops back.
    app, _, out = make_app(["label:1. Scan a dataset", "label:Review & run", "exit"])
    app.run(MainMenu())
    assert "choose a dataset folder first" in out.getvalue()


def test_settings_persist(make_app):
    app, _, _ = make_app([
        "label:5. Settings", "label:Color", "label:View effective thresholds", BACK, BACK, "exit",
    ])
    app.run(MainMenu())
    saved = json.loads((home_dir() / "settings.json").read_text(encoding="utf-8"))
    assert saved["color"] is False


def test_every_main_menu_item_opens_and_returns(make_app):
    items = ["2. Results", "3. Browse checks", "4. Recent scans", "5. Settings", "6. Help"]
    answers = []
    for item in items:
        answers += [f"label:{item}", BACK]
    app, prompter, _ = make_app(answers + ["exit"])
    app.run(MainMenu())
    assert not prompter.answers


def test_screen_error_is_shown_and_menu_survives(make_app, monkeypatch):
    from scandata.cli.screens import help as help_screen

    def boom(self, app):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(help_screen.HelpScreen, "show", boom)
    app, _, out = make_app(["label:6. Help", "exit"])
    app.run(MainMenu())
    assert "kaboom" in out.getvalue()
