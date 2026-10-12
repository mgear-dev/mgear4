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


@pytest.fixture
def common(setup_path):
    from mgear.animbits.animbits_hub.tools import common

    return common


def test_tweener_registered(setup_path):
    from mgear.animbits.animbits_hub import registry
    from mgear.animbits.animbits_hub.tools import tweener
    from mgear.utilbits.bookmarks import core as bm_core

    assert "tweener" in dict(registry.registered_tools())
    assert ("tweener", "Tweener") in bm_core.registered_bookmark_tools()
    assert tweener.TOOL_ID == "tweener"


def test_row_specs(tweener, common):
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
    specs = common.row_specs(bookmarks, (0.6, 0.85, 0.6), tweener.TOOL_ID)
    assert [spec["name"] for spec in specs] == ["Selection", "arm", "face"]
    assert specs[0]["bookmark"] is None
    assert specs[0]["color"] == (0.6, 0.85, 0.6)
    assert specs[1]["bookmark"] is bookmarks[0]
    assert specs[1]["color"] == (0.2, 0.4, 0.6)


def test_tween_targets(tweener, common):
    from maya import cmds
    from mgear.utilbits.bookmarks import core as bm_core

    cmds.file(new=True, force=True)
    a = cmds.spaceLocator(name="a_ctl")[0]
    b = cmds.spaceLocator(name="b_ctl")[0]
    mesh = cmds.polyCube(name="body")[0]

    cmds.select([a, mesh + ".f[0]"])
    assert common.row_targets() == ["|a_ctl"]

    cmds.select(clear=True)
    bm = bm_core.create_bookmark("bm", bm_core.BOOKMARK_SELECTION, [b], (1, 1, 1))
    assert common.row_targets(bm) == ["|b_ctl"]
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
    pos = QtCore.QPoint(int(round(slider.x_at(0.3))), slider.height() // 2)

    slider.mousePressEvent(_MouseEvent(pos))
    assert slider._fraction == pytest.approx(0.3)
    slider.mouseReleaseEvent(_MouseEvent(pos))
    assert clicked == [pytest.approx(0.3)]
    assert slider._fraction == 0.5


# slider modes -----------------------------------------------------------


def test_mode_weights(setup_path):
    from mgear.animbits.animbits_hub import modes

    expected = {
        modes.TWEEN: (0.0, 0.5, 1.0),
        modes.DEFAULT: (-1.0, 0.0, 1.0),
        modes.MIRROR: (-1.0, 0.0, 1.0),
        modes.BUFFER: (-1.0, 0.0, 1.0),
        modes.PUSH: (0.0, 1.0, 2.0),
    }
    for mode_id, weights in expected.items():
        mode = modes.get_mode(mode_id)
        got = tuple(mode.weight_from_fraction(f) for f in (0.0, 0.5, 1.0))
        assert got == pytest.approx(weights), mode_id
    assert [m.label for m in modes.MODES] == ["TW", "BD", "BM", "BB", "PP"]
    assert modes.get_mode("unknown").mode_id == modes.TWEEN


def test_settings_mode_and_tooltips(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    assert settings.slider_mode == "tween"
    assert settings.show_tooltips is True
    settings.slider_mode = "mirror"
    settings.show_tooltips = False
    restored = hub_settings.HubSettings(qsettings())
    assert restored.slider_mode == "mirror"
    assert restored.show_tooltips is False
    with pytest.raises(ValueError):
        settings.slider_mode = "nope"
    raw = qsettings()
    raw.setValue("animbits_hub/slider_mode", "nope")
    raw.sync()
    assert hub_settings.HubSettings(qsettings()).slider_mode == "tween"


# buffers ----------------------------------------------------------------


@pytest.fixture
def buffers(setup_path):
    from maya import cmds
    from mgear.animbits.animbits_hub import buffers

    cmds.file(new=True, force=True)
    buffers.clear_all()
    yield buffers
    buffers.clear_all()


def test_capture_pose(buffers):
    from maya import cmds

    cmds.namespace(add="chrA")
    ctl = cmds.spaceLocator(name="chrA:hand_ctl")[0]
    cmds.setAttr(ctl + ".translateX", 6)
    cmds.currentTime(24)
    buffer = buffers.capture_pose([ctl])
    assert list(buffer.values) == [ctl]
    assert buffer.values[ctl]["translateX"] == 6
    assert buffer.frame == 24
    assert buffer.namespace == "chrA"
    assert buffer.describe().startswith("Frame 24 · 1 control · chrA · ")


def test_buffer_store_and_new_scene(buffers):
    from maya import cmds

    ctl = cmds.spaceLocator(name="ctl")[0]
    buffers.store_buffer("bookmark:Arms", buffers.capture_pose([ctl]))
    assert buffers.get_buffer("bookmark:Arms") is not None
    assert buffers.get_buffer("selection") is None
    cmds.file(new=True, force=True)
    assert buffers.get_buffer("bookmark:Arms") is None


def test_buffer_values_other_namespace(buffers):
    from maya import cmds

    cmds.namespace(add="chrA")
    cmds.namespace(add="chrB", parent=":")
    a = cmds.spaceLocator(name="chrA:hand_ctl")[0]
    b = cmds.spaceLocator(name="chrB:hand_ctl")[0]
    cmds.setAttr(a + ".translateX", 6)
    buffer = buffers.capture_pose([a])
    values = buffers.buffer_values(buffer, [b])
    assert list(values) == [b]
    assert values[b]["translateX"] == 6
    # nothing selected: paste on the stored controls
    assert list(buffers.buffer_values(buffer, [])) == [a]


# tweener caches per mode ------------------------------------------------


@pytest.fixture
def tween_scene(tweener):
    """Locator keyed 0 at frame 1, 8 at frame 6 and 10 at frame 11."""
    from maya import cmds
    from mgear.animbits.animbits_hub import buffers

    cmds.file(new=True, force=True)
    buffers.clear_all()
    ctl = cmds.spaceLocator(name="ctl")[0]
    for frame, value in ((1, 0), (6, 8), (11, 10)):
        cmds.setKeyframe(ctl, attribute="translateX", time=frame, value=value)
    cmds.currentTime(6)
    cmds.select(ctl)
    yield cmds
    buffers.clear_all()


def _apply(tweener, mode_id, fraction, bookmark=None):
    from mgear.animbits.animbits_hub import modes
    from mgear.core import anim_utils

    cache = tweener.build_cache(mode_id, bookmark)
    anim_utils.apply_blend(
        cache, modes.get_mode(mode_id).weight_from_fraction(fraction)
    )
    return cache


def test_tweener_default_halfway_and_exaggerate(tweener, tween_scene):
    cmds = tween_scene
    _apply(tweener, "default", 0.75)
    assert cmds.getAttr("ctl.translateX") == pytest.approx(4.0)
    _apply(tweener, "default", 0.0)
    assert cmds.getAttr("ctl.translateX") == pytest.approx(8.0)


def test_tweener_push_pull(tweener, tween_scene):
    cmds = tween_scene
    _apply(tweener, "push", 1.0)
    assert cmds.getAttr("ctl.translateX") == pytest.approx(11.0)
    _apply(tweener, "push", 0.0)
    assert cmds.getAttr("ctl.translateX") == pytest.approx(5.0)


def test_tweener_mirror_left_from_right(tweener, tween_scene):
    cmds = tween_scene
    left = cmds.createNode("transform", name="arm_L0_fk0_ctl")
    right = cmds.createNode("transform", name="arm_R0_fk0_ctl")
    cmds.setAttr(left + ".rotateZ", 10)
    cmds.setAttr(right + ".rotateZ", 30)
    cmds.select(left)
    _apply(tweener, "mirror", 1.0)
    assert cmds.getAttr(left + ".rotateZ") == pytest.approx(30.0)
    assert cmds.getAttr(right + ".rotateZ") == pytest.approx(30.0)


def test_tweener_buffer_other_namespace(tweener, tween_scene):
    from mgear.animbits.animbits_hub import buffers

    cmds = tween_scene
    cmds.namespace(add="chrA")
    cmds.namespace(add="chrB", parent=":")
    a = cmds.spaceLocator(name="chrA:hand_ctl")[0]
    b = cmds.spaceLocator(name="chrB:hand_ctl")[0]
    cmds.setAttr(a + ".translateX", 6)
    cmds.setAttr(b + ".translateX", 2)
    buffers.store_buffer("selection", buffers.capture_pose([a]))
    cmds.select(b)
    _apply(tweener, "buffer", 1.0)
    assert cmds.getAttr(b + ".translateX") == pytest.approx(6.0)


def test_tweener_buffer_empty(tweener, tween_scene):
    assert tweener.build_cache("buffer") == []


def test_row_key(common):
    assert common.row_key() == "selection"
    assert common.row_key({"name": "Arms"}) == "bookmark:Arms"


# tool area registry and settings ------------------------------------------


def test_registry_areas(registry):
    def rows(context):
        return []

    def tools(context):
        return []

    registry.register_tool("rows_tool", rows)
    registry.register_tool("late_tools", tools, order=50, area="tools")
    registry.register_tool("early_tools", tools, order=5, area="tools")
    assert [t for t, _f in registry.registered_tools()] == ["rows_tool"]
    assert [t for t, _f in registry.registered_tools("tools")] == [
        "early_tools",
        "late_tools",
    ]


def test_settings_nudge(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    assert settings.nudge_amount_for("selection") == 1
    assert settings.nudge_ripple_for("selection") is False
    settings.set_nudge_amount("selection", 4)
    settings.set_nudge_ripple("selection", True)
    restored = hub_settings.HubSettings(qsettings())
    assert restored.nudge_amount_for("selection") == 4
    assert restored.nudge_ripple_for("selection") is True
    settings.set_nudge_amount("selection", 500)
    assert settings.nudge_amount_for("selection") == 100
    settings.set_nudge_amount("selection", 0)
    assert settings.nudge_amount_for("selection") == 1
    raw = qsettings()
    raw.setValue("animbits_hub/nudge/selection/amount", "lots")
    raw.sync()
    assert hub_settings.HubSettings(qsettings()).nudge_amount_for("selection") == 1


# key tools ---------------------------------------------------------------


@pytest.fixture
def key_tools(setup_path, monkeypatch):
    """The key tools module, in a scene with ctl keyed at 1, 5 and 10."""
    from maya import cmds
    from mgear.animbits.animbits_hub import buffers
    from mgear.animbits.animbits_hub.tools import key_tools
    from mgear.core import anim_utils

    cmds.file(new=True, force=True)
    buffers.clear_all()
    ctl = cmds.spaceLocator(name="ctl")[0]
    for frame in (1, 5, 10):
        cmds.setKeyframe(ctl, attribute="translateX", time=frame, value=frame)
    cmds.selectKey(clear=True)
    cmds.currentTime(5)
    cmds.select(ctl)
    monkeypatch.setattr(anim_utils, "get_timeline_range", lambda: None)
    monkeypatch.setattr(key_tools, "channel_box_attributes", lambda: None)
    yield key_tools
    buffers.clear_all()


def _times(plug="ctl.translateX"):
    from maya import cmds

    return cmds.keyframe(plug, query=True, timeChange=True)


def test_resolve_priority(key_tools, monkeypatch):
    from maya import cmds
    from mgear.core import anim_utils

    kind, payload = key_tools.resolve_nudge_target()
    assert kind == "frame"
    assert payload[0] == ["|ctl"]
    assert payload[1] == 5
    monkeypatch.setattr(anim_utils, "get_timeline_range", lambda: (3.0, 8.0))
    assert key_tools.resolve_nudge_target() == ("range", (["|ctl"], 3.0, 8.0))
    cmds.selectKey("ctl.translateX", time=(10, 10))
    assert key_tools.resolve_nudge_target() == ("keys", None)
    cmds.selectKey(clear=True)
    cmds.select(clear=True)
    assert key_tools.resolve_nudge_target() == (None, None)


def test_nudge_frame_time_follows(key_tools):
    from maya import cmds

    assert key_tools.nudge(2) == 1
    assert _times() == [1.0, 7.0, 10.0]
    assert cmds.currentTime(query=True) == 7
    cmds.undo()
    assert _times() == [1.0, 5.0, 10.0]
    assert cmds.currentTime(query=True) == 5


def test_nudge_selected_keys_first(key_tools):
    from maya import cmds

    cmds.selectKey("ctl.translateX", time=(10, 10))
    key_tools.nudge(1)
    assert _times() == [1.0, 5.0, 11.0]


def test_nudge_channel_box_filter(key_tools, monkeypatch):
    from maya import cmds

    cmds.setKeyframe("ctl", attribute="translateY", time=5, value=1)
    monkeypatch.setattr(key_tools, "channel_box_attributes", lambda: ["ty"])
    key_tools.nudge(1)
    assert _times("ctl.translateY") == [6.0]
    assert _times() == [1.0, 5.0, 10.0]


def test_nudge_blocked(key_tools):
    from maya import cmds

    assert key_tools.nudge(5) == 0
    assert _times() == [1.0, 5.0, 10.0]
    assert cmds.currentTime(query=True) == 5


def test_nudge_nothing(key_tools):
    from maya import cmds

    cmds.select(clear=True)
    assert key_tools.nudge(1) == 0


def _matrix(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, matrix=True)


def test_copy_paste_world_current_frame(key_tools):
    from maya import cmds

    foot = cmds.spaceLocator(name="foot_ctl")[0]
    cmds.setAttr(foot + ".translate", 1, 2, 3)
    cmds.setAttr(foot + ".rotateY", 30)
    cmds.select(foot)
    copied = _matrix(foot)
    key_tools.copy_world_pose()
    cmds.setAttr(foot + ".translate", 0, 0, 0)
    cmds.setAttr(foot + ".rotateY", 0)
    assert key_tools.paste_world_pose() == ["|foot_ctl"]
    assert _matrix(foot) == pytest.approx(copied)
    assert cmds.keyframe(foot + ".translateX", query=True, timeChange=True) == [5.0]


def test_paste_world_over_range(key_tools, monkeypatch):
    from maya import cmds
    from mgear.core import anim_utils

    parent = cmds.group(empty=True, name="hip")
    foot = cmds.spaceLocator(name="foot_ctl")[0]
    cmds.parent(foot, parent)
    cmds.setKeyframe(parent, attribute="translateX", time=10, value=0)
    cmds.setKeyframe(parent, attribute="translateX", time=15, value=5)
    cmds.currentTime(10)
    cmds.select(foot)
    key_tools.copy_world_pose()
    copied = _matrix(foot)
    monkeypatch.setattr(anim_utils, "get_timeline_range", lambda: (10.0, 15.0))
    key_tools.paste_world_pose()
    times = cmds.keyframe("|hip|foot_ctl.translateX", query=True, timeChange=True)
    assert times == [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    for frame in (12, 15):
        cmds.currentTime(frame)
        assert _matrix(foot) == pytest.approx(copied, abs=1e-6)


def test_paste_world_other_namespace(key_tools):
    from maya import cmds

    cmds.namespace(add="chrA")
    cmds.namespace(add="chrB", parent=":")
    a = cmds.spaceLocator(name="chrA:hand_ctl")[0]
    b = cmds.spaceLocator(name="chrB:hand_ctl")[0]
    cmds.setAttr(a + ".translate", 4, 5, 6)
    cmds.select(a)
    key_tools.copy_world_pose()
    cmds.select(b)
    assert key_tools.paste_world_pose() == ["|chrB:hand_ctl"]
    assert _matrix(b) == pytest.approx(_matrix(a))


def test_paste_world_nothing_selected(key_tools):
    from maya import cmds

    foot = cmds.spaceLocator(name="foot_ctl")[0]
    cmds.setAttr(foot + ".translateX", 3)
    cmds.select(foot)
    key_tools.copy_world_pose()
    cmds.setAttr(foot + ".translateX", 0)
    cmds.select(clear=True)
    key_tools.paste_world_pose()
    assert cmds.getAttr(foot + ".translateX") == pytest.approx(3.0)


def test_paste_world_empty_buffer(key_tools):
    assert key_tools.paste_world_pose() == []


def test_copy_world_nothing_selected(key_tools):
    from maya import cmds

    cmds.select(clear=True)
    assert key_tools.copy_world_pose() is None


# key tool rows -----------------------------------------------------------


def test_settings_nudge_per_row(hub_settings, qsettings):
    settings = hub_settings.HubSettings(qsettings())
    settings.set_nudge_amount("selection", 2)
    settings.set_nudge_amount("bookmark:Arms", 5)
    settings.set_nudge_ripple("bookmark:Arms", True)
    restored = hub_settings.HubSettings(qsettings())
    assert restored.nudge_amount_for("selection") == 2
    assert restored.nudge_amount_for("selection") == 2
    assert restored.nudge_amount_for("bookmark:Arms") == 5
    assert restored.nudge_ripple_for("bookmark:Arms") is True
    assert restored.nudge_ripple_for("selection") is False
    assert restored.nudge_amount_for("bookmark:body") == 1


def test_key_tool_row_specs(setup_path):
    from mgear.animbits.animbits_hub.tools import common
    from mgear.animbits.animbits_hub.tools import key_tools
    from mgear.utilbits.bookmarks import core as bm_core

    arms = bm_core.create_bookmark("Arms", "selection", [], (1, 0, 1))
    body = bm_core.create_bookmark("body", "selection", [], (0, 1, 1))
    bm_core.set_tool_config(arms, "key_tools", enabled=True)
    bm_core.set_tool_config(body, "tweener", enabled=True)
    specs = common.row_specs([arms, body], (0.6, 0.85, 0.6), key_tools.TOOL_ID)
    assert [spec["name"] for spec in specs] == ["Selection", "Arms"]
    assert ("key_tools", "Key Tools") in bm_core.registered_bookmark_tools()


def test_bookmark_row_nudge_ignores_selected_keys(key_tools):
    from maya import cmds
    from mgear.utilbits.bookmarks import core as bm_core

    bookmark = bm_core.create_bookmark("Arms", "selection", ["ctl"], (1, 0, 1))
    cmds.selectKey("ctl.translateX", time=(10, 10))
    cmds.select(clear=True)
    kind, payload = key_tools.resolve_nudge_target(bookmark)
    assert kind == "frame"
    assert payload[2] is None
    key_tools.nudge(1, bookmark=bookmark)
    assert _times() == [1.0, 6.0, 10.0]


def test_world_buffers_per_row(key_tools):
    from maya import cmds
    from mgear.animbits.animbits_hub import buffers
    from mgear.utilbits.bookmarks import core as bm_core

    bookmark = bm_core.create_bookmark("Arms", "selection", ["ctl"], (1, 0, 1))
    cmds.select(clear=True)
    key_tools.copy_world_pose(bookmark)
    assert buffers.get_buffer(key_tools.world_buffer_key(bookmark)) is not None
    assert buffers.get_buffer(key_tools.world_buffer_key()) is None
    cmds.setAttr("ctl.translateY", 3)
    assert key_tools.paste_world_pose(bookmark) == ["|ctl"]
    assert cmds.getAttr("ctl.translateY") == pytest.approx(0.0)
    assert key_tools.paste_world_pose() == []


# temp pivot buttons -----------------------------------------------------------


@pytest.fixture
def pivot_rows(key_tools, qsettings):
    """Key tool rows (Selection, Arms) in a scene with ctl and arm_ctl keyed."""
    from maya import cmds
    from mgear.animbits.animbits_hub import registry
    from mgear.animbits.animbits_hub import settings as hub_settings
    from mgear.utilbits.bookmarks import core as bm_core

    arm = cmds.spaceLocator(name="arm_ctl")[0]
    for frame in (1, 10):
        cmds.setKeyframe(arm, attribute="translateX", time=frame, value=frame)
    arms = bm_core.create_bookmark("Arms", "selection", ["arm_ctl"], (1, 0, 1))
    bm_core.set_tool_config(arms, "key_tools", enabled=True)
    bm_core.save_to_scene([arms])
    context = registry.HubContext(hub_settings.HubSettings(qsettings()))
    rows = key_tools.build_tool_rows(context)
    return {row.name: row for row in rows}


def _click(button):
    button.mousePressEvent(_MouseEvent(None))


def test_pivot_row_flow(pivot_rows):
    from maya import cmds
    from mgear.core import temp_pivot

    sel_row, arms_row = pivot_rows["Selection"], pivot_rows["Arms"]
    cmds.select(clear=True)
    _click(arms_row.pivot_button)
    pivot = temp_pivot.find()
    assert pivot and temp_pivot.info(pivot)["label"] == "bookmark:Arms"
    assert cmds.ls(selection=True, long=True) == [pivot]
    assert arms_row.pivot_button.highlight and not arms_row.pivot_button.dim
    assert sel_row.pivot_button.dim
    assert arms_row.cancel_button.isHidden()

    _click(arms_row.pivot_button)
    assert temp_pivot.state(pivot) == "active"
    assert arms_row.pivot_button.icon == "mgear_check"
    assert not arms_row.cancel_button.isHidden()
    assert sel_row.pivot_button.dim

    cmds.setAttr(pivot + ".rotateY", 30)
    _click(arms_row.pivot_button)
    assert temp_pivot.find() is None
    assert not sel_row.pivot_button.dim
    assert arms_row.pivot_button.icon == "mgear_crosshair"
    assert arms_row.cancel_button.isHidden()
    assert not cmds.ls(type="pairBlend")


def test_pivot_other_row_warns(pivot_rows):
    from mgear.core import temp_pivot

    _click(pivot_rows["Arms"].pivot_button)
    _click(pivot_rows["Selection"].pivot_button)
    pivot = temp_pivot.find()
    assert temp_pivot.info(pivot)["label"] == "bookmark:Arms"
    assert temp_pivot.state(pivot) == "place"


def test_pivot_cancel_button(pivot_rows):
    from maya import cmds
    from mgear.core import temp_pivot

    arms_row = pivot_rows["Arms"]
    _click(arms_row.pivot_button)
    _click(arms_row.pivot_button)
    _click(arms_row.cancel_button)
    assert temp_pivot.find() is None
    assert cmds.keyframe("arm_ctl.translateX", query=True, timeChange=True) == [1, 10]


def test_pivot_undo_create(pivot_rows):
    from maya import cmds
    from mgear.core import temp_pivot

    _click(pivot_rows["Selection"].pivot_button)
    cmds.undo()
    assert temp_pivot.find() is None
    cmds.select("ctl")
    _click(pivot_rows["Selection"].pivot_button)
    assert temp_pivot.find() is not None


def test_pivot_resume_and_unknown_label(key_tools, qsettings):
    from maya import cmds
    from mgear.animbits.animbits_hub import registry
    from mgear.animbits.animbits_hub import settings as hub_settings
    from mgear.core import temp_pivot

    pivot = temp_pivot.create(["ctl"], label="bookmark:Gone")
    temp_pivot.activate(pivot)
    context = registry.HubContext(hub_settings.HubSettings(qsettings()))
    (sel_row,) = key_tools.build_tool_rows(context)
    assert sel_row.pivot_button.icon == "mgear_check"
    assert not sel_row.cancel_button.isHidden()
    temp_pivot.cancel(pivot)


def test_pivot_scene_read_once_per_build(pivot_rows, key_tools, qsettings, monkeypatch):
    """Opening the hub reads the temp pivot once, not once per row (regression)."""
    from mgear.animbits.animbits_hub import registry
    from mgear.animbits.animbits_hub import settings as hub_settings
    from mgear.core import temp_pivot

    calls = []
    original = temp_pivot.find
    monkeypatch.setattr(temp_pivot, "find", lambda: calls.append(1) or original())
    context = registry.HubContext(hub_settings.HubSettings(qsettings()))
    rows = key_tools.build_tool_rows(context)
    for row in rows:
        row.set_show_tooltips(True)
        row.set_show_names("hover")
    assert len(rows) == 2
    assert len(calls) == 1
