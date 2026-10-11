"""Tests for the tool settings, namespace fallback and keying of bookmarks."""

import pytest


@pytest.fixture
def bm_core(setup_path, tmp_path, monkeypatch):
    """The bookmarks core module, with settings in a temporary INI file."""
    from mgear.vendor.Qt import QtCore
    from mgear.utilbits.bookmarks import core

    ini = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        core,
        "get_user_settings",
        lambda: QtCore.QSettings(ini, QtCore.QSettings.IniFormat),
    )
    monkeypatch.setattr(core, "_registered_tools", {})
    return core


@pytest.fixture
def scene(setup_path):
    """New empty scene."""
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


def _bookmark(core, items=None, bm_type=None, tools=None):
    bm = core.create_bookmark(
        "bm", bm_type or core.BOOKMARK_SELECTION, items or [], (1, 0, 0)
    )
    if tools is not None:
        bm["tools"] = tools
    return bm


def test_new_bookmark_has_tools(bm_core):
    assert _bookmark(bm_core)["tools"] == {}


def test_tools_round_trip_keeps_unknown(bm_core):
    tools = {"tweener": {"enabled": True}, "future": {"x": 1}}
    config = bm_core.bookmarks_to_config([_bookmark(bm_core, tools=tools)])
    bookmarks, _layout = bm_core.config_to_bookmarks(config)
    assert bookmarks[0]["tools"] == tools
    assert bm_core.bookmarks_to_config(bookmarks)["bookmarks"][0]["tools"] == tools


def test_tools_round_trip_is_a_copy(bm_core):
    bm = _bookmark(bm_core, tools={"tweener": {"enabled": True}})
    config = bm_core.bookmarks_to_config([bm])
    config["bookmarks"][0]["tools"]["tweener"]["enabled"] = False
    assert bm["tools"]["tweener"]["enabled"] is True


def test_old_config_gets_empty_tools(bm_core):
    config = {
        "version": bm_core.CONFIG_VERSION,
        "bookmarks": [{"name": "a", "type": "selection", "items": []}],
    }
    bookmarks, _layout = bm_core.config_to_bookmarks(config)
    assert bookmarks[0]["tools"] == {}


def test_tool_config_helpers(bm_core):
    bm = _bookmark(bm_core)
    assert bm_core.get_tool_config(bm, "tweener") == {}
    assert not bm_core.is_tool_enabled(bm, "tweener")
    bm_core.set_tool_config(bm, "tweener", enabled=True)
    bm_core.set_tool_config(bm, "tweener", order=2)
    assert bm_core.get_tool_config(bm, "tweener") == {"enabled": True, "order": 2}
    assert bm_core.is_tool_enabled(bm, "tweener")


def test_bookmarks_for_tool(bm_core):
    enabled = _bookmark(bm_core, tools={"tweener": {"enabled": True}})
    disabled = _bookmark(bm_core, tools={"tweener": {"enabled": False}})
    isolate = _bookmark(
        bm_core,
        bm_type=bm_core.BOOKMARK_ISOLATE,
        tools={"tweener": {"enabled": True}},
    )
    result = bm_core.bookmarks_for_tool([enabled, disabled, isolate], "tweener")
    assert result == [enabled]


def test_register_tool_twice(bm_core):
    bm_core.register_bookmark_tool("tweener", "Tween")
    bm_core.register_bookmark_tool("other", "Other")
    bm_core.register_bookmark_tool("tweener", "Tweener")
    assert bm_core.registered_bookmark_tools() == [
        ("tweener", "Tweener"),
        ("other", "Other"),
    ]


def _namespaced_scene(cmds):
    for ns in ("chrA", "chrB"):
        cmds.namespace(add=ns)
        for name in ("arm_ctl", "hand_ctl"):
            cmds.spaceLocator(name="{}:{}".format(ns, name))
    cmds.select(clear=True)


def test_namespace_fallback_to_stored(bm_core, scene):
    _namespaced_scene(scene)
    bm_core.set_last_namespace("chrA")
    bm = _bookmark(bm_core, items=["chrB:arm_ctl"])
    bm["use_selected_namespace"] = True
    resolved, missing = bm_core.resolve_bookmark_items(bm)
    assert resolved == ["|chrA:arm_ctl"]
    assert missing == []


def test_namespace_selection_updates_store(bm_core, scene):
    _namespaced_scene(scene)
    scene.select("chrB:hand_ctl")
    bm = _bookmark(bm_core, items=["chrA:arm_ctl"])
    bm["use_selected_namespace"] = True
    resolved, _missing = bm_core.resolve_bookmark_items(bm)
    assert resolved == ["|chrB:arm_ctl"]
    assert bm_core.get_last_namespace() == "chrB"


def test_namespace_argument_wins(bm_core, scene):
    _namespaced_scene(scene)
    scene.select("chrB:hand_ctl")
    bm = _bookmark(bm_core, items=["chrB:arm_ctl"])
    bm["use_selected_namespace"] = True
    resolved, _missing = bm_core.resolve_bookmark_items(bm, namespace="chrA")
    assert resolved == ["|chrA:arm_ctl"]


def test_namespace_no_source_raises(bm_core, scene):
    _namespaced_scene(scene)
    bm = _bookmark(bm_core, items=["chrA:arm_ctl"])
    bm["use_selected_namespace"] = True
    with pytest.raises(RuntimeError):
        bm_core.resolve_bookmark_items(bm)


def test_namespace_off_unchanged(bm_core, scene):
    _namespaced_scene(scene)
    bm_core.set_last_namespace("chrB")
    bm = _bookmark(bm_core, items=["chrA:arm_ctl"])
    resolved, _missing = bm_core.resolve_bookmark_items(bm)
    assert resolved == ["|chrA:arm_ctl"]


def test_key_bookmark_members(bm_core, scene):
    cmds = scene
    a = cmds.spaceLocator(name="a_ctl")[0]
    b = cmds.spaceLocator(name="b_ctl")[0]
    mesh = cmds.polyCube(name="body")[0]
    cmds.select(a)
    cmds.currentTime(7)
    bm = _bookmark(bm_core, items=[a, b, mesh + ".f[0:2]"])
    keyed = bm_core.key_bookmark_members(bm)
    assert keyed == ["|a_ctl", "|b_ctl"]
    assert cmds.keyframe(a, query=True, timeChange=True)[0] == 7
    assert cmds.keyframe(b, query=True, timeChange=True)[0] == 7
    assert not cmds.keyframe(mesh, query=True)
    assert cmds.ls(selection=True) == [a]
    cmds.undo()
    assert not cmds.keyframe(a, query=True)
    assert not cmds.keyframe(b, query=True)


def test_key_bookmark_members_isolate_does_nothing(bm_core, scene):
    a = scene.spaceLocator(name="a_ctl")[0]
    bm = _bookmark(bm_core, items=[a], bm_type=bm_core.BOOKMARK_ISOLATE)
    assert bm_core.key_bookmark_members(bm) == []
    assert not scene.keyframe(a, query=True)


def _show_in_tools_click(core, chip, monkeypatch):
    """Open the chip menu and click the first "Show In Tools" action."""
    from mgear.vendor.Qt import QtCore
    from mgear.vendor.Qt import QtWidgets

    def fake_exec(menu, *args):
        for action in menu.actions():
            if action.menu() and action.text() == "Show In Tools":
                action.menu().actions()[0].trigger()
        return None

    class ContextEvent(object):
        def globalPos(self):
            return QtCore.QPoint(0, 0)

    monkeypatch.setattr(QtWidgets.QMenu, "exec_", fake_exec)
    chip.contextMenuEvent(ContextEvent())


def test_show_in_tools_checks_tool(bm_core, monkeypatch):
    """Checking an unchecked tool emits True (regression)."""
    from mgear.utilbits.bookmarks.widgets import ChipButton

    bm_core.register_bookmark_tool("tweener", "Tweener")
    chip = ChipButton(_bookmark(bm_core))
    toggled = []
    chip.tool_toggled.connect(lambda bm, tool, state: toggled.append((tool, state)))

    _show_in_tools_click(bm_core, chip, monkeypatch)
    assert toggled == [("tweener", True)]

    bm_core.set_tool_config(chip.bookmark, "tweener", enabled=True)
    _show_in_tools_click(bm_core, chip, monkeypatch)
    assert toggled[-1] == ("tweener", False)
