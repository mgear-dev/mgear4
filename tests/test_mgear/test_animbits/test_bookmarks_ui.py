"""Tests for the bookmarks window widgets in mgear.animbits.bookmarks."""

import pytest


def _bookmark(module, items=None):
    return module.create_bookmark(
        "bm", module.BOOKMARK_SELECTION, items or [], (1, 0, 0)
    )


def _show_in_tools_click(chip, monkeypatch):
    """Open the chip menu and click the first "Show In Tools" action."""
    from mgear.vendor.Qt import QtCore
    from mgear.vendor.Qt import QtWidgets

    # A Python subclass: patching exec_ on the PySide2 class has no effect,
    # so the real menu would open (and block when run alone)
    class FakeMenu(QtWidgets.QMenu):
        def exec_(self, *args):
            for action in self.actions():
                if action.menu() and action.text() == "Show In Tools":
                    action.menu().actions()[0].trigger()
            return None

    class ContextEvent(object):
        def globalPos(self):
            return QtCore.QPoint(0, 0)

    monkeypatch.setattr(QtWidgets, "QMenu", FakeMenu)
    chip.contextMenuEvent(ContextEvent())


def test_show_in_tools_checks_tool(selection_bookmarks, monkeypatch):
    """Checking an unchecked tool emits True (regression)."""
    from mgear.animbits.bookmarks.widgets import ChipButton

    selection_bookmarks.register_bookmark_tool("tweener", "Tweener")
    chip = ChipButton(_bookmark(selection_bookmarks))
    toggled = []
    chip.tool_toggled.connect(lambda bm, tool, state: toggled.append((tool, state)))

    _show_in_tools_click(chip, monkeypatch)
    assert toggled == [("tweener", True)]

    selection_bookmarks.set_tool_config(chip.bookmark, "tweener", enabled=True)
    _show_in_tools_click(chip, monkeypatch)
    assert toggled[-1] == ("tweener", False)


def test_middle_click_keys_members(selection_bookmarks):
    """Middle-click keys the bookmark controls, the selection is kept."""
    from maya import cmds
    from mgear.vendor.Qt import QtCore
    from mgear.vendor.Qt import QtGui
    from mgear.animbits.bookmarks.widgets import ChipButton

    a = cmds.spaceLocator(name="a_ctl")[0]
    cmds.select(clear=True)
    cmds.currentTime(4)
    chip = ChipButton(_bookmark(selection_bookmarks, [a]))
    keyed = []
    chip.key_members_requested.connect(
        lambda bm: keyed.append(selection_bookmarks.key_bookmark_members(bm))
    )
    event = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonRelease,
        QtCore.QPointF(2, 2),
        QtCore.QPointF(2, 2),
        QtCore.Qt.MiddleButton,
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
    )
    chip.mouseReleaseEvent(event)
    assert keyed == [["|a_ctl"]]
    assert cmds.keyframe(a, query=True, timeChange=True)[0] == 4
    assert cmds.ls(selection=True) == []


def test_helpers_tooltip(selection_bookmarks):
    from mgear.animbits.bookmarks import helpers

    text = helpers.build_tooltip(
        _bookmark(selection_bookmarks, ["chrA:ctl", "chrA:body.f[0:2]"])
    )
    assert "Selection Bookmark" in text
    assert "chrA:ctl" in text
    assert "1 f" in text
