"""Tests for mgear.core.selection_bookmarks, the bookmarks data layer."""

import pytest


@pytest.fixture
def scene(setup_path):
    """New empty scene."""
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


def _bookmark(module, items=None, bm_type=None, tools=None):
    bm = module.create_bookmark(
        "bm", bm_type or module.BOOKMARK_SELECTION, items or [], (1, 0, 0)
    )
    if tools is not None:
        bm["tools"] = tools
    return bm


def test_new_bookmark_has_tools(selection_bookmarks):
    assert _bookmark(selection_bookmarks)["tools"] == {}


def test_tools_round_trip_keeps_unknown(selection_bookmarks):
    tools = {"tweener": {"enabled": True}, "future": {"x": 1}}
    config = selection_bookmarks.bookmarks_to_config(
        [_bookmark(selection_bookmarks, tools=tools)]
    )
    bookmarks, _layout = selection_bookmarks.config_to_bookmarks(config)
    assert bookmarks[0]["tools"] == tools
    assert (
        selection_bookmarks.bookmarks_to_config(bookmarks)["bookmarks"][0]["tools"]
        == tools
    )


def test_tools_round_trip_is_a_copy(selection_bookmarks):
    bm = _bookmark(selection_bookmarks, tools={"tweener": {"enabled": True}})
    config = selection_bookmarks.bookmarks_to_config([bm])
    config["bookmarks"][0]["tools"]["tweener"]["enabled"] = False
    assert bm["tools"]["tweener"]["enabled"] is True


def test_old_config_gets_empty_tools(selection_bookmarks):
    config = {
        "version": selection_bookmarks.CONFIG_VERSION,
        "bookmarks": [{"name": "a", "type": "selection", "items": []}],
    }
    bookmarks, _layout = selection_bookmarks.config_to_bookmarks(config)
    assert bookmarks[0]["tools"] == {}


def test_tool_config_helpers(selection_bookmarks):
    bm = _bookmark(selection_bookmarks)
    assert selection_bookmarks.get_tool_config(bm, "tweener") == {}
    assert not selection_bookmarks.is_tool_enabled(bm, "tweener")
    selection_bookmarks.set_tool_config(bm, "tweener", enabled=True)
    selection_bookmarks.set_tool_config(bm, "tweener", order=2)
    assert selection_bookmarks.get_tool_config(bm, "tweener") == {
        "enabled": True,
        "order": 2,
    }
    assert selection_bookmarks.is_tool_enabled(bm, "tweener")


def test_bookmarks_for_tool(selection_bookmarks):
    enabled = _bookmark(selection_bookmarks, tools={"tweener": {"enabled": True}})
    disabled = _bookmark(selection_bookmarks, tools={"tweener": {"enabled": False}})
    isolate = _bookmark(
        selection_bookmarks,
        bm_type=selection_bookmarks.BOOKMARK_ISOLATE,
        tools={"tweener": {"enabled": True}},
    )
    result = selection_bookmarks.bookmarks_for_tool(
        [enabled, disabled, isolate], "tweener"
    )
    assert result == [enabled]


def test_register_tool_twice(selection_bookmarks):
    selection_bookmarks.register_bookmark_tool("tweener", "Tween")
    selection_bookmarks.register_bookmark_tool("other", "Other")
    selection_bookmarks.register_bookmark_tool("tweener", "Tweener")
    assert selection_bookmarks.registered_bookmark_tools() == [
        ("tweener", "Tweener"),
        ("other", "Other"),
    ]


def _namespaced_scene(cmds):
    for ns in ("chrA", "chrB"):
        cmds.namespace(add=ns)
        for name in ("arm_ctl", "hand_ctl"):
            cmds.spaceLocator(name="{}:{}".format(ns, name))
    cmds.select(clear=True)


def test_namespace_fallback_to_stored(selection_bookmarks, scene):
    _namespaced_scene(scene)
    selection_bookmarks.set_last_namespace("chrA")
    bm = _bookmark(selection_bookmarks, items=["chrB:arm_ctl"])
    bm["use_selected_namespace"] = True
    resolved, missing = selection_bookmarks.resolve_bookmark_items(bm)
    assert resolved == ["|chrA:arm_ctl"]
    assert missing == []


def test_namespace_selection_updates_store(selection_bookmarks, scene):
    _namespaced_scene(scene)
    scene.select("chrB:hand_ctl")
    bm = _bookmark(selection_bookmarks, items=["chrA:arm_ctl"])
    bm["use_selected_namespace"] = True
    resolved, _missing = selection_bookmarks.resolve_bookmark_items(bm)
    assert resolved == ["|chrB:arm_ctl"]
    assert selection_bookmarks.get_last_namespace() == "chrB"


def test_namespace_argument_wins(selection_bookmarks, scene):
    _namespaced_scene(scene)
    scene.select("chrB:hand_ctl")
    bm = _bookmark(selection_bookmarks, items=["chrB:arm_ctl"])
    bm["use_selected_namespace"] = True
    resolved, _missing = selection_bookmarks.resolve_bookmark_items(
        bm, namespace="chrA"
    )
    assert resolved == ["|chrA:arm_ctl"]


def test_namespace_no_source_raises(selection_bookmarks, scene):
    _namespaced_scene(scene)
    bm = _bookmark(selection_bookmarks, items=["chrA:arm_ctl"])
    bm["use_selected_namespace"] = True
    with pytest.raises(RuntimeError):
        selection_bookmarks.resolve_bookmark_items(bm)


def test_namespace_off_unchanged(selection_bookmarks, scene):
    _namespaced_scene(scene)
    selection_bookmarks.set_last_namespace("chrB")
    bm = _bookmark(selection_bookmarks, items=["chrA:arm_ctl"])
    resolved, _missing = selection_bookmarks.resolve_bookmark_items(bm)
    assert resolved == ["|chrA:arm_ctl"]


def test_key_bookmark_members(selection_bookmarks, scene):
    cmds = scene
    a = cmds.spaceLocator(name="a_ctl")[0]
    b = cmds.spaceLocator(name="b_ctl")[0]
    mesh = cmds.polyCube(name="body")[0]
    cmds.select(a)
    cmds.currentTime(7)
    bm = _bookmark(selection_bookmarks, items=[a, b, mesh + ".f[0:2]"])
    keyed = selection_bookmarks.key_bookmark_members(bm)
    assert keyed == ["|a_ctl", "|b_ctl"]
    assert cmds.keyframe(a, query=True, timeChange=True)[0] == 7
    assert cmds.keyframe(b, query=True, timeChange=True)[0] == 7
    assert not cmds.keyframe(mesh, query=True)
    assert cmds.ls(selection=True) == [a]
    cmds.undo()
    assert not cmds.keyframe(a, query=True)
    assert not cmds.keyframe(b, query=True)


def test_key_bookmark_members_isolate_does_nothing(selection_bookmarks, scene):
    a = scene.spaceLocator(name="a_ctl")[0]
    bm = _bookmark(
        selection_bookmarks, items=[a], bm_type=selection_bookmarks.BOOKMARK_ISOLATE
    )
    assert selection_bookmarks.key_bookmark_members(bm) == []
    assert not scene.keyframe(a, query=True)


# moved to core: component namespaces, data compatibility, layering ----------


def test_namespace_swap_keeps_component(selection_bookmarks, scene):
    cmds = scene
    for ns in ("chrA", "chrB"):
        cmds.namespace(add=ns, parent=":")
        cmds.polyCube(name="{}:body".format(ns))
    bm = _bookmark(selection_bookmarks, items=["chrA:body.f[0:2]"])
    bm["use_selected_namespace"] = True
    resolved, missing = selection_bookmarks.resolve_bookmark_items(bm, namespace="chrB")
    assert missing == []
    assert resolved == ["|chrB:body.f[0:2]"]


def test_namespace_swap_nested_and_root(selection_bookmarks, scene):
    cmds = scene
    cmds.namespace(add="c", parent=":")
    cmds.spaceLocator(name="c:arm_ctl")
    cmds.spaceLocator(name="arm_ctl")
    bm = _bookmark(selection_bookmarks, items=["a:b:arm_ctl"])
    bm["use_selected_namespace"] = True
    assert selection_bookmarks.resolve_bookmark_items(bm, namespace="c")[0] == [
        "|c:arm_ctl"
    ]
    assert selection_bookmarks.resolve_bookmark_items(bm, namespace="")[0] == [
        "|arm_ctl"
    ]


def test_selection_namespace_with_component(selection_bookmarks, scene):
    cmds = scene
    cmds.namespace(add="chrA", parent=":")
    cmds.polyCube(name="chrA:body")
    cmds.select("chrA:body.f[0:3]")
    assert selection_bookmarks.selection_namespace() == "chrA"


def test_sbk_files_v1_and_v2(selection_bookmarks, tmp_path):
    import json

    v1 = tmp_path / "old.sbk"
    v1.write_text(
        json.dumps(
            {
                "version": "1.0",
                "bookmarks": [
                    {
                        "name": "arm",
                        "color": [1, 0, 0],
                        "type": "selection",
                        "items": ["|rig|chrA:arm_ctl", "|rig|chrA:body.f[0:3]"],
                    }
                ],
            }
        )
    )
    bookmarks, _layout = selection_bookmarks.config_to_bookmarks(
        selection_bookmarks.import_bookmarks(str(v1))
    )
    assert bookmarks[0]["items"] == ["chrA:arm_ctl", "chrA:body.f[0:3]"]

    bm = _bookmark(
        selection_bookmarks,
        items=["chrA:arm_ctl"],
        tools={"tweener": {"enabled": True}},
    )
    path = str(tmp_path / "new")
    assert selection_bookmarks.export_bookmarks(path, [bm], layout="grid")
    config = selection_bookmarks.import_bookmarks(path + ".sbk")
    assert config["version"] == selection_bookmarks.CONFIG_VERSION
    bookmarks, layout = selection_bookmarks.config_to_bookmarks(config)
    assert layout == "grid"
    assert bookmarks[0]["items"] == ["chrA:arm_ctl"]
    assert bookmarks[0]["tools"] == {"tweener": {"enabled": True}}


def test_scene_storage_round_trip(selection_bookmarks, scene, tmp_path):
    cmds = scene
    bm = _bookmark(
        selection_bookmarks, items=["ctl"], tools={"key_tools": {"enabled": True}}
    )
    selection_bookmarks.save_to_scene([bm], layout="vertical")
    path = str(tmp_path / "bookmarks.ma")
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii", force=True)
    cmds.file(new=True, force=True)
    cmds.file(path, open=True, force=True)
    (loaded,) = selection_bookmarks.load_scene_bookmarks()
    assert loaded["items"] == ["ctl"]
    assert loaded["tools"] == {"key_tools": {"enabled": True}}


def test_core_imports_no_tool_package(scripts_path):
    """The data layer never imports a tool package (static check)."""
    import ast
    import os

    path = os.path.join(scripts_path, "mgear", "core", "selection_bookmarks.py")
    with open(path) as f:
        tree = ast.parse(f.read())
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    tools = [m for m in modules if m.startswith(("mgear.animbits", "mgear.utilbits"))]
    assert tools == []
    assert "mgear.core" in modules
