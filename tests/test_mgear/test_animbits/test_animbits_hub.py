"""Tests for the Qt-free logic of the Animbits Hub."""

import pytest


@pytest.fixture
def qsettings(setup_path, tmp_path):
    """Function returning a QSettings on a temporary INI file."""
    from mgear.vendor.Qt import QtCore

    ini = str(tmp_path / "settings.ini")
    return lambda: QtCore.QSettings(ini, QtCore.QSettings.IniFormat)


@pytest.fixture
def hub_settings(setup_path):
    from mgear.animbits.animbits_hub import settings

    return settings


@pytest.fixture
def geometry(setup_path):
    from mgear.animbits.animbits_hub import geometry

    return geometry


@pytest.fixture
def registry(setup_path, monkeypatch):
    from mgear.animbits.animbits_hub import registry

    monkeypatch.setattr(registry, "_tools", {})
    return registry


# settings ---------------------------------------------------------------


def test_settings_defaults(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    assert settings.show_names == "hover"
    assert settings.placement == "cursor"
    assert settings.fixed_pos is None
    assert settings.scale == 1.0
    assert settings.selection_color == hub_settings.DEFAULT_SELECTION_COLOR


def test_settings_round_trip(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    settings.show_names = "always"
    settings.placement = "fixed"
    settings.fixed_pos = (120, -40)
    settings.scale = 1.5
    settings.selection_color = (0.1, 0.2, 0.3)

    restored = hub_settings.HubSettings(qsettings())
    assert restored.show_names == "always"
    assert restored.placement == "fixed"
    assert restored.fixed_pos == (120, -40)
    assert restored.scale == 1.5
    assert restored.selection_color == pytest.approx((0.1, 0.2, 0.3))


def test_settings_scale_clamped(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    settings.scale = 0.2
    assert settings.scale == 0.5
    settings.scale = 7
    assert settings.scale == 3.0
    settings.scale = 1.0 + 0.1 + 0.1
    assert settings.scale == 1.2


def test_settings_invalid_values(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    with pytest.raises(ValueError):
        settings.placement = "somewhere"
    with pytest.raises(ValueError):
        settings.show_names = "never"
    # broken stored values fall back to the defaults
    raw = qsettings()
    raw.setValue("animbits_hub/scale", "big")
    raw.setValue("animbits_hub/selection_color", "1,2")
    raw.sync()
    restored = hub_settings.HubSettings(qsettings())
    assert restored.scale == 1.0
    assert restored.selection_color == hub_settings.DEFAULT_SELECTION_COLOR


# geometry ---------------------------------------------------------------


def test_stop_fractions(geometry):
    fractions = geometry.stop_fractions()
    assert len(fractions) == 11
    assert fractions[0] == 0.0
    assert fractions[5] == 0.5
    assert fractions[3] == pytest.approx(0.3)
    assert fractions[-1] == 1.0


def test_fraction_from_x(geometry):
    assert geometry.fraction_from_x(50, 10, 100) == pytest.approx(0.4)
    assert geometry.fraction_from_x(-30, 10, 100) == 0.0
    assert geometry.fraction_from_x(500, 10, 100) == 1.0


def test_place_at_cursor_middle(geometry):
    screen = (0, 0, 1920, 1080)
    pos = geometry.place_at_cursor((960, 540), (100, 30), (200, 120), screen)
    assert pos == (860, 510)


def test_place_at_cursor_near_edge(geometry):
    screen = (0, 0, 1920, 1080)
    pos = geometry.place_at_cursor((1915, 1075), (100, 30), (200, 120), screen)
    assert pos == (1720, 960)
    pos = geometry.place_at_cursor((3, 3), (100, 30), (200, 120), screen)
    assert pos == (0, 0)


def test_place_at_cursor_second_screen(geometry):
    screen = (1920, 0, 1280, 1024)
    pos = geometry.place_at_cursor((1925, 500), (100, 30), (200, 120), screen)
    assert pos == (1920, 470)


def test_place_fixed_monitor_removed(geometry):
    screens = [(0, 0, 1920, 1080)]
    pos = geometry.place_fixed((2500, 300), (200, 120), screens)
    assert pos == (1720, 300)


def test_place_fixed_keeps_valid_position(geometry):
    screens = [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]
    assert geometry.place_fixed((2000, 100), (200, 120), screens) == (2000, 100)


def test_place_fixed_no_screens(geometry):
    assert geometry.place_fixed((10, 20), (200, 120), []) == (10, 20)


# registry ---------------------------------------------------------------


def test_registry_order_and_replace(registry):
    def a(context):
        return []

    def b(context):
        return []

    def c(context):
        return []

    registry.register_tool("late", a, order=50)
    registry.register_tool("early", b, order=5)
    registry.register_tool("tie", c, order=50)
    assert [t for t, _f in registry.registered_tools()] == ["early", "late", "tie"]

    registry.register_tool("late", c, order=50)
    tools = dict(registry.registered_tools())
    assert len(tools) == 3
    assert tools["late"] is c

    registry.unregister_tool("early")
    registry.unregister_tool("unknown")
    assert [t for t, _f in registry.registered_tools()] == ["late", "tie"]


# tweener ----------------------------------------------------------------


@pytest.fixture
def tweener(setup_path):
    from mgear.animbits.animbits_hub.tools import tweener

    return tweener


def test_tweener_registered(setup_path):
    from mgear.animbits.animbits_hub import registry
    from mgear.animbits.animbits_hub.tools import tweener
    from mgear.utilbits.bookmarks import core as bm_core

    assert "tweener" in dict(registry.registered_tools())
    assert ("tweener", "Tweener") in bm_core.registered_bookmark_tools()
    assert tweener.TOOL_ID == "tweener"


def test_row_specs(tweener):
    from mgear.utilbits.bookmarks import core as bm_core

    def bookmark(name, bm_type, enabled):
        bm = bm_core.create_bookmark(name, bm_type, [], (0.2, 0.4, 0.6))
        bm_core.set_tool_config(bm, "tweener", enabled=enabled)
        return bm

    bookmarks = [
        bookmark("arm", bm_core.BOOKMARK_SELECTION, True),
        bookmark("leg", bm_core.BOOKMARK_SELECTION, False),
        bookmark("face", bm_core.BOOKMARK_SELECTION, True),
        bookmark("iso", bm_core.BOOKMARK_ISOLATE, True),
    ]
    specs = tweener.row_specs(bookmarks, (0.6, 0.85, 0.6))
    assert [spec["name"] for spec in specs] == ["Selection", "arm", "face"]
    assert specs[0]["bookmark"] is None
    assert specs[0]["color"] == (0.6, 0.85, 0.6)
    assert specs[1]["bookmark"] is bookmarks[0]
    assert specs[1]["color"] == (0.2, 0.4, 0.6)


def test_tween_targets(tweener):
    from maya import cmds
    from mgear.utilbits.bookmarks import core as bm_core

    cmds.file(new=True, force=True)
    a = cmds.spaceLocator(name="a_ctl")[0]
    b = cmds.spaceLocator(name="b_ctl")[0]
    mesh = cmds.polyCube(name="body")[0]

    cmds.select([a, mesh + ".f[0]"])
    assert tweener.tween_targets() == ["|a_ctl"]

    cmds.select(clear=True)
    bm = bm_core.create_bookmark("bm", bm_core.BOOKMARK_SELECTION, [b], (1, 1, 1))
    assert tweener.tween_targets(bm) == ["|b_ctl"]
    assert cmds.ls(selection=True) == []


class _MouseEvent(object):
    def __init__(self, pos):
        self._pos = pos

    def pos(self):
        return self._pos

    def button(self):
        from mgear.vendor.Qt import QtCore

        return QtCore.Qt.LeftButton

    def ignore(self):
        pass


def test_slider_tick_press_shows_handle(setup_path):
    """The handle shows on a pressed tick, then springs back (regression)."""
    from mgear.vendor.Qt import QtCore
    from mgear.animbits.animbits_hub.widgets import TweenSlider

    slider = TweenSlider((0.6, 0.85, 0.6))
    clicked = []
    slider.stop_clicked.connect(clicked.append)
    pos = QtCore.QPoint(int(round(slider._x_at(0.3))), slider.height() // 2)

    slider.mousePressEvent(_MouseEvent(pos))
    assert slider._fraction == pytest.approx(0.3)
    slider.mouseReleaseEvent(_MouseEvent(pos))
    assert clicked == [pytest.approx(0.3)]
    assert slider._fraction == 0.5
