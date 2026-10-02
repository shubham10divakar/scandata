"""Prompt backend. Screens talk to a `Prompter`, so tests can script the answers.

Every prompt returns ``None`` when the user presses Esc or Ctrl+C, which screens treat as Back.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

Validator = Callable[[str], "bool | str"]


@dataclass
class Option:
    label: str
    value: Any = None
    disabled: str | None = None  # reason shown next to a disabled option
    separator: bool = False

    @classmethod
    def sep(cls) -> Option:
        return cls("", separator=True)


class Prompter(Protocol):
    def select(self, message: str, options: list[Option], default: Any = None) -> Any | None: ...
    def text(
        self, message: str, default: str = "", validate: Validator | None = None
    ) -> str | None: ...
    def path(
        self,
        message: str,
        default: str = "",
        only_directories: bool = False,
        validate: Validator | None = None,
    ) -> str | None: ...
    def confirm(self, message: str, default: bool = False) -> bool | None: ...
    def pause(self) -> None: ...


class QuestionaryPrompter:
    """Arrow-key prompts via questionary, with Esc mapped to Back."""

    def __init__(self, color: bool = True) -> None:
        import questionary

        self._q = questionary
        self._style = (
            questionary.Style(
                [
                    ("qmark", "fg:ansicyan bold"),
                    ("question", "bold"),
                    ("pointer", "fg:ansicyan bold"),
                    ("highlighted", "fg:ansicyan bold"),
                    ("selected", "fg:ansicyan"),
                    ("answer", "fg:ansicyan bold"),
                    ("instruction", "fg:ansibrightblack"),
                    ("disabled", "fg:ansibrightblack italic"),
                ]
            )
            if color
            else None
        )

    def _ask(self, question) -> Any | None:
        from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings

        kb = KeyBindings()

        @kb.add("escape", eager=True)
        def _back(event) -> None:
            event.app.exit(result=None)

        app = question.application
        app.key_bindings = merge_key_bindings([app.key_bindings, kb])
        try:
            return question.unsafe_ask()
        except (KeyboardInterrupt, EOFError):
            return None

    def select(self, message: str, options: list[Option], default: Any = None) -> Any | None:
        choices = [
            self._q.Separator() if o.separator
            else self._q.Choice(o.label, value=o.value, disabled=o.disabled)
            for o in options
        ]
        enabled = [o.value for o in options if not o.separator and not o.disabled]
        return self._ask(
            self._q.select(
                message,
                choices=choices,
                default=default if default in enabled else None,
                qmark="›",
                instruction="(↑/↓, Enter · Esc = back)",
                style=self._style,
            )
        )

    def text(self, message: str, default: str = "", validate: Validator | None = None):
        return self._ask(
            self._q.text(
                message, default=default, validate=validate or (lambda _: True),
                qmark="›", style=self._style,
            )
        )

    def path(
        self,
        message: str,
        default: str = "",
        only_directories: bool = False,
        validate: Validator | None = None,
    ):
        return self._ask(
            self._q.path(
                message, default=default, only_directories=only_directories,
                validate=validate or (lambda _: True), qmark="›", style=self._style,
            )
        )

    def confirm(self, message: str, default: bool = False) -> bool | None:
        return self._ask(
            self._q.confirm(message, default=default, qmark="›", style=self._style)
        )

    def pause(self) -> None:
        self._ask(self._q.press_any_key_to_continue("Press any key to continue..."))
