"""Tests for mgear.core.pyqt.rich_tooltip."""

import pytest


@pytest.fixture
def pyqt(setup_path):
    from mgear.core import pyqt

    return pyqt


def test_title_text_bullets(pyqt):
    html = pyqt.rich_tooltip(
        "Nudge Keys",
        "Move your selected keys in time.",
        ["Left arrow nudges keys backward.", "Right arrow nudges keys forward."],
        color="#4a90d9",
    )
    for part in (
        "Nudge Keys",
        "#4a90d9",
        "Move your selected keys in time.",
        "Left arrow nudges keys backward.",
        "Right arrow nudges keys forward.",
    ):
        assert html.count(part) == 1
    assert html.count("&bull;") == 2


def test_escaping(pyqt):
    html = pyqt.rich_tooltip("A & B", "Use <b> & co")
    assert "A &amp; B" in html
    assert "Use &lt;b&gt; &amp; co" in html
    assert "<b>" not in html


def test_no_bullets(pyqt):
    html = pyqt.rich_tooltip("Title", "Text")
    assert "&bull;" not in html


def test_default_color(pyqt):
    assert pyqt.TOOLTIP_COLOR in pyqt.rich_tooltip("Title", "Text")
