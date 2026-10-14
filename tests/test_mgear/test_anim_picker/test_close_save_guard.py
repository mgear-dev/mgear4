"""Anim Picker save guard and viewport independent pinned item data.

Regression tests for the save-on-close prompt showing in anim mode, and for
pinned items making the picker look modified after a pan / zoom / resize.
"""

import json

import pytest

PINNED_POS = [40.0, -25.0]
FREE_POS = [10.0, 5.0]


def _handles():
    return [[-10.0, -10.0], [10.0, -10.0], [10.0, 10.0], [-10.0, 10.0]]


def _picker_data():
    """Return picker data with one free and one pinned item."""
    free_item = {
        "color": [200, 50, 50, 255],
        "position": list(FREE_POS),
        "rotation": 0.0,
        "handles": _handles(),
    }
    pinned_item = {
        "color": [50, 200, 50, 255],
        "position": list(PINNED_POS),
        "rotation": 0.0,
        "handles": _handles(),
        "pinned": True,
        "anchor": "tr",
        "offset": [12, 12],
        "pin_scale": 1.0,
    }
    return {"tabs": [{"name": "main", "data": {"items": [free_item, pinned_item]}}]}


@pytest.fixture
def temp_settings(tmp_path):
    """Redirect QSettings to a temp INI so the user's prefs are untouched."""
    from mgear.vendor.Qt import QtCore

    previous = QtCore.QSettings.defaultFormat()
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    QtCore.QSettings.setPath(
        QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(tmp_path)
    )
    yield
    QtCore.QSettings.setDefaultFormat(previous)


@pytest.fixture
def picker(qt_app, temp_settings):
    """Yield a function building a loaded picker window in a new scene."""
    from maya import cmds

    from mgear.anim_picker import main_window
    from mgear.anim_picker import picker_node
    from mgear.anim_picker.handlers import __EDIT_MODE__

    cmds.file(new=True, force=True)
    windows = []

    def build(edit=True):
        data_node = picker_node.DataNode(name="PICKER_DATA")
        data_node.create()
        data_node.set_data(_picker_data())
        data_node.write_data(to_node=True, to_file=False)

        win = main_window.MainDockWindow(edit=edit)
        win.resize(476, 837)
        win.refresh()
        win.load_character()
        windows.append(win)
        return win

    yield build

    for win in windows:
        win._autosave_timer.stop()
        win.cb_manager.removeAllManagedCB()
        win.deleteLater()
    __EDIT_MODE__.set_init(False)
    cmds.file(new=True, force=True)


def _pinned_item(win):
    items = [item for item in win.get_all_picker_items() if item.pinned]
    assert len(items) == 1
    return items[0]


def _navigate(view):
    """Wheel-like zoom, pan, resize and frame the view."""
    view.scale(1.7, 1.7)
    view._update_pinned_items()
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + 40)
    view.verticalScrollBar().setValue(view.verticalScrollBar().value() - 30)
    view._update_pinned_items()
    view.resize(view.width() + 120, view.height() - 80)
    view._update_pinned_items()
    view.fit_scene_content()


def _node_data():
    from maya import cmds

    raw = cmds.getAttr("PICKER_DATA.picker_datas")
    return json.loads(raw) if raw else raw


def _close_event():
    from mgear.vendor.Qt import QtGui

    return QtGui.QCloseEvent()


# =============================================================================
# Viewport independent pinned item data ---


def test_navigation_does_not_dirty_pinned_picker(picker):
    """Pan / zoom / resize / frame on a picker with pins is not a change."""
    win = picker()
    view = win.tab_area.active_view()
    item = _pinned_item(win)
    live_before = (item.x(), item.y())

    _navigate(view)

    # The live scene position really moved (the view relocked the pin) ...
    assert (item.x(), item.y()) != live_before
    # ... but the saved data and the dirty check did not.
    assert item.get_data()["position"] == PINNED_POS
    assert not win.has_unsaved_changes()


def test_tiled_round_trip_does_not_dirty(picker):
    """Switching tabbed -> tiled -> tabbed with pins is not a change."""
    from mgear.anim_picker.widgets import tiled_view

    win = picker()
    win.tab_area.set_view_mode(tiled_view.MODE_GRID)
    assert not win.has_unsaved_changes()
    win.tab_area.set_view_mode(tiled_view.MODE_TABBED)
    assert not win.has_unsaved_changes()


def test_pinning_records_rest_position(picker):
    """Pinning an item at P saves P regardless of later navigation."""
    win = picker()
    view = win.tab_area.active_view()
    item = [i for i in win.get_all_picker_items() if not i.pinned][0]

    view.set_item_pinned(item, True)
    _navigate(view)
    assert item.get_data()["position"] == FREE_POS

    view.set_item_pinned(item, False)
    assert item.pin_rest_position is None


def test_rest_position_round_trips(picker):
    """Save and reload keeps the pinned item's position and anchor."""
    win = picker()
    _navigate(win.tab_area.active_view())

    win.save_widget.show()
    win.save_widget.file_option_cb.setChecked(False)
    win.save_widget.save_event()

    item = _node_data()["tabs"][0]["data"]["items"][1]
    assert item["position"] == PINNED_POS
    assert item["anchor"] == "tr"
    assert item["offset"] == [12, 12]

    win.load_character()
    assert _pinned_item(win).get_data()["position"] == PINNED_POS
    assert not win.has_unsaved_changes()


def test_offset_change_is_a_real_edit(picker):
    """Moving a pin's offset dirties the picker but keeps its position."""
    win = picker()
    view = win.tab_area.active_view()
    item = _pinned_item(win)

    item.set_offset([40, 30])
    view._update_pinned_items()

    assert win.has_unsaved_changes()
    assert item.get_data()["position"] == PINNED_POS


# =============================================================================
# Save guard ---


def test_can_save_rules(picker, monkeypatch):
    """Saving needs edit mode and a non-referenced data node."""
    from mgear.anim_picker import picker_node
    from mgear.anim_picker.handlers import __EDIT_MODE__

    win = picker(edit=True)
    assert win.can_save()

    __EDIT_MODE__.set(False)
    assert not win.can_save()

    __EDIT_MODE__.set(True)
    monkeypatch.setattr(picker_node.DataNode, "is_referenced", lambda self: True)
    assert not win.can_save()


def test_anim_mode_close_does_not_prompt(picker, monkeypatch):
    """Closing in anim mode never shows the save prompt, even when dirty."""
    win = picker(edit=False)
    closed = []
    monkeypatch.setattr(win, "close", lambda: closed.append(True))
    # Force dirty data so only the mode guard can stop the prompt.
    monkeypatch.setattr(win, "has_unsaved_changes", lambda: True)

    event = _close_event()
    win.closeEvent(event)

    assert closed == [True]
    assert not win.save_widget.isVisible()
    assert win.save_widget._on_finished is None


def test_referenced_close_does_not_prompt(picker, monkeypatch):
    """Closing on a referenced data node never shows the save prompt."""
    from mgear.anim_picker import picker_node

    win = picker(edit=True)
    closed = []
    monkeypatch.setattr(win, "close", lambda: closed.append(True))
    monkeypatch.setattr(win, "has_unsaved_changes", lambda: True)
    monkeypatch.setattr(picker_node.DataNode, "is_referenced", lambda self: True)

    win.closeEvent(_close_event())

    assert closed == [True]
    assert win.save_widget._on_finished is None


def test_edit_mode_close_with_changes_prompts(picker, monkeypatch):
    """In edit mode with real edits the close prompt still appears."""
    win = picker(edit=True)
    closed = []
    monkeypatch.setattr(win, "close", lambda: closed.append(True))
    _pinned_item(win).set_offset([40, 30])

    event = _close_event()
    win.closeEvent(event)

    assert closed == []
    assert not event.isAccepted()
    assert win.save_widget._on_finished is not None


def test_save_event_refused_in_anim_mode(picker):
    """The Save overlay writes nothing in anim mode and finishes as discard."""
    from mgear.anim_picker.handlers import __EDIT_MODE__

    win = picker(edit=True)
    before = _node_data()
    _pinned_item(win).set_offset([40, 30])

    outcomes = []
    win.save_widget.show_prompt(on_finished=outcomes.append)
    win.save_widget.file_option_cb.setChecked(False)
    __EDIT_MODE__.set(False)
    win.save_widget.save_event()

    assert outcomes == ["discard"]
    assert _node_data() == before
