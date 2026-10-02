from dataclasses import dataclass

import pytest

from scandata.cli.navigator import Exit, Home, Navigator, Pop, Push, Replace, Stay


@dataclass
class S:
    title: str

    def show(self, app):  # pragma: no cover - not called here
        return Stay()


def test_push_pop_home_exit():
    nav = Navigator(S("Root"))
    nav.apply(Push(S("A")))
    nav.apply(Push(S("B")))
    assert nav.breadcrumb == "Root › A › B"

    nav.apply(Pop())
    assert nav.current.title == "A"

    nav.apply(Push(S("C")))
    nav.apply(Replace(S("D")))
    assert nav.breadcrumb == "Root › A › D"

    nav.apply(Home())
    assert nav.depth == 1 and nav.current.title == "Root"

    nav.apply(Pop())  # can't pop the root
    assert nav.running and nav.depth == 1

    nav.apply(Exit())
    assert not nav.running


def test_unknown_action_raises():
    with pytest.raises(TypeError):
        Navigator(S("Root")).apply(object())
