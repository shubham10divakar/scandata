"""Screen stack: Push goes forward, Pop goes back, Home returns to the main menu."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from scandata.cli.context import App


class Screen(Protocol):
    title: str

    def show(self, app: App) -> NavAction: ...


class NavAction:
    pass


@dataclass(frozen=True)
class Push(NavAction):
    screen: Screen


@dataclass(frozen=True)
class Replace(NavAction):
    screen: Screen


@dataclass(frozen=True)
class Pop(NavAction):
    pass


@dataclass(frozen=True)
class Home(NavAction):
    pass


@dataclass(frozen=True)
class Exit(NavAction):
    pass


@dataclass(frozen=True)
class Stay(NavAction):
    """Re-render the current screen (e.g. after editing a field)."""


class Navigator:
    def __init__(self, root: Screen) -> None:
        self.stack: list[Screen] = [root]

    @property
    def running(self) -> bool:
        return bool(self.stack)

    @property
    def current(self) -> Screen:
        return self.stack[-1]

    @property
    def depth(self) -> int:
        return len(self.stack)

    @property
    def breadcrumb(self) -> str:
        return " › ".join(s.title for s in self.stack)

    def apply(self, action: NavAction) -> None:
        if isinstance(action, Push):
            self.stack.append(action.screen)
        elif isinstance(action, Replace):
            self.stack[-1] = action.screen
        elif isinstance(action, Pop):
            if len(self.stack) > 1:
                self.stack.pop()
        elif isinstance(action, Home):
            del self.stack[1:]
        elif isinstance(action, Exit):
            self.stack.clear()
        elif isinstance(action, Stay):
            pass
        else:
            raise TypeError(f"Unknown navigation action: {action!r}")
