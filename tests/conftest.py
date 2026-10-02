from __future__ import annotations

import io
from collections import deque
from typing import Any

import pytest
from rich.console import Console

from scandata.cli.context import App
from scandata.cli.prompter import Option
from scandata.core.config import Settings


class FakePrompter:
    """Plays back scripted answers. A callable answer receives the options list."""

    def __init__(self, answers: list[Any]) -> None:
        self.answers = deque(answers)
        self.seen: list[tuple[str, list[str]]] = []

    def _next(self, message: str, labels: list[str] | None = None) -> Any:
        self.seen.append((message, labels or []))
        if not self.answers:
            raise AssertionError(f"No scripted answer left for prompt: {message!r}")
        return self.answers.popleft()

    def select(self, message: str, options: list[Option], default: Any = None) -> Any:
        labels = [o.label for o in options if not o.separator]
        answer = self._next(message, labels)
        if answer is None:
            return None
        if isinstance(answer, str) and answer.startswith("label:"):
            wanted = answer[len("label:"):]
            match = [o for o in options if not o.separator and o.label.startswith(wanted)]
            assert match, f"No option starting with {wanted!r} in {labels}"
            assert match[0].disabled is None, f"{wanted!r} is disabled: {match[0].disabled}"
            return match[0].value
        return answer

    def text(self, message, default="", validate=None):
        answer = self._next(message)
        if answer is not None and validate is not None:
            assert validate(answer) is True, validate(answer)
        return answer

    def path(self, message, default="", only_directories=False, validate=None):
        return self.text(message, default, validate)

    def confirm(self, message, default=False):
        return self._next(message)

    def pause(self) -> None:
        pass


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANDATA_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("NO_COLOR", raising=False)


@pytest.fixture
def make_app():
    def _make(answers: list[Any]) -> tuple[App, FakePrompter, io.StringIO]:
        out = io.StringIO()
        console = Console(file=out, width=100, color_system=None, legacy_windows=False)
        prompter = FakePrompter(answers)
        return App(prompter, console=console, settings=Settings(), clear=False), prompter, out

    return _make
