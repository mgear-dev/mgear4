"""Shifter Guide Explorer tests

The Guide Explorer rebuilds its tree only when the guide or its components
change, keeps the selected items across rebuilds and builds the settings
panels without changing the Maya selection (forum thread 5389: flicker with
ngSkinTools paint mode).
"""

import json

import pytest


@pytest.fixture
def small_guide(rig_plugins, setup_path, monkeypatch):
    """A guide with a ``control_C0`` root and an ``arm_C0`` below it.

    Returns:
        callable: Draws a new component under ``control_C0_root``, called
            with the component type. Returns the new component root name.
    """
    from maya import cmds

    import mgear
    import mgear.pymaya as pm
    from mgear.shifter import guide

    monkeypatch.setattr(mgear, "log", lambda *args, **kwargs: None)
    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    guide.Rig().drawNewComponent(
        pm.PyNode("control_C0_root"), "arm_2jnt_01", showUI=False
    )
    cmds.select(clear=True)

    def add(comp_type):
        before = set(cmds.ls("*.comp_type", objectsOnly=True))
        guide.Rig().drawNewComponent(
            pm.PyNode("control_C0_root"), comp_type, showUI=False
        )
        cmds.select(clear=True)
        return (set(cmds.ls("*.comp_type", objectsOnly=True)) - before).pop()

    return add


@pytest.fixture
def no_main_window(monkeypatch):
    """Let Maya's dockable mixin build widgets without a main window."""
    import qt_helpers

    qt_helpers.stub_main_window(monkeypatch.setattr)


@pytest.fixture
def explorer(qt_app, small_guide, no_main_window, monkeypatch):
    """Guide Explorer widget showing the small guide, not shown on screen.

    Its settings are never saved, so the user's explorer settings don't
    change.
    """
    from mgear.shifter.guide_explorer import guide_explorer_widget
    from mgear.shifter.guide_explorer import utils

    monkeypatch.setattr(utils, "_blueprint_cache", {})
    monkeypatch.setattr(
        guide_explorer_widget.GuideExplorerWidget,
        "_save_settings",
        lambda self: None,
    )
    widget = guide_explorer_widget.GuideExplorerWidget()
    widget.refresh()
    yield widget
    widget.teardown()
    widget.deleteLater()


@pytest.fixture
def selection_changes(run_with_maya_standalone):
    """Count the Maya selection changes.

    Returns:
        list: Gets one entry per selection change.
    """
    from maya.api import OpenMaya as om

    events = []
    callback = om.MEventMessage.addEventCallback(
        "SelectionChanged", lambda *args: events.append(1)
    )
    yield events
    om.MMessage.removeCallback(callback)


def _item(tree, text):
    """Return the tree item showing a text in its first column."""
    root = tree.topLevelItem(0)
    if root.text(0) == text:
        return root
    for index in range(root.childCount()):
        if root.child(index).text(0) == text:
            return root.child(index)
    raise AssertionError("No tree item {}".format(text))


def _select_item(tree, text):
    """Select a tree item as a click does."""
    tree.setCurrentItem(_item(tree, text))


def _selected_texts(tree):
    return [item.text(0) for item in tree.selectedItems()]


# Settings root ---------------------------------------------------------------


def test_settings_root_nested_and_restored(small_guide):
    from maya import cmds

    from mgear.shifter import guide

    cmds.select("arm_C0_root")
    with guide.settings_root("guide") as root:
        assert root == "guide"
        with pytest.raises(RuntimeError):
            with guide.settings_root("control_C0_root"):
                assert guide.get_settings_root().name() == "control_C0_root"
                raise RuntimeError("inner failure")
        assert guide.get_settings_root().name() == "guide"
    assert guide.get_settings_root().name() == "arm_C0_root"


def test_component_settings_root_from_context(
    qt_app, small_guide, no_main_window, selection_changes
):
    from maya import cmds

    from mgear import shifter
    from mgear.shifter import guide

    cmds.select("guide")
    del selection_changes[:]
    settings_cls = shifter.importComponentGuide("arm_2jnt_01").componentSettings
    with guide.settings_root("arm_C0_root"):
        panel = settings_cls()
    try:
        assert panel.root.name() == "arm_C0_root"
        assert cmds.ls(selection=True) == ["guide"]
        assert not selection_changes
    finally:
        panel.deleteLater()


def test_guide_settings_root_from_selection(qt_app, small_guide, no_main_window):
    from maya import cmds

    from mgear.shifter import guide

    cmds.select("guide")
    panel = guide.GuideSettings()
    try:
        assert panel.root.name() == "guide"
    finally:
        panel.deleteLater()


def test_referenced_groups_message_only_on_user_refresh(
    qt_app, small_guide, no_main_window, count_calls
):
    import mgear.pymaya as pm
    from mgear.shifter import guide

    infos = count_calls(pm, "displayInfo", record=lambda args, kwargs: args[0])
    with guide.settings_root("guide"):
        panel = guide.GuideSettings()
    try:
        assert not [msg for msg in infos if "referenced groups" in msg]
        panel.refreshReferencedGroups()
        assert "No referenced groups found to refresh." in infos
    finally:
        panel.deleteLater()


def _referenced_group(source_file, step_names):
    """Referenced custom step group data, as stored in the step attributes."""
    return {
        "type": "group",
        "name": "rig_steps",
        "collapsed": False,
        "active": True,
        "items": [
            {"type": "step", "name": name, "path": name + ".py", "active": True}
            for name in step_names
        ],
        "referenced": True,
        "source_file": source_file,
    }


def test_unchanged_referenced_group_not_written(
    qt_app, small_guide, no_main_window, tmp_path, count_calls
):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import custom_step_widget
    from mgear.shifter import guide

    source = str(tmp_path / "steps.scs")
    group = _referenced_group(source, ["a"])
    with open(source, "w") as f:
        json.dump({"items": [group]}, f)
    stored = json.dumps({"version": 2, "items": [group]})
    cmds.setAttr("guide.preCustomStep", stored, type="string")

    writes = count_calls(custom_step_widget.CustomStepMixin, "_updateStepListAttr")
    infos = count_calls(pm, "displayInfo", record=lambda args, kwargs: args[0])
    with guide.settings_root("guide"):
        panel = guide.GuideSettings()
    try:
        assert not writes
        assert not infos
        assert cmds.getAttr("guide.preCustomStep") == stored

        # -- A changed source file is still refreshed by the user
        with open(source, "w") as f:
            json.dump({"items": [_referenced_group(source, ["a", "b"])]}, f)
        panel.refreshReferencedGroups()
        assert len(writes) == 1
        items = json.loads(cmds.getAttr("guide.preCustomStep"))["items"]
        assert [step["name"] for step in items[0]["items"]] == ["a", "b"]
    finally:
        panel.deleteLater()


# Guide snapshot and component query ------------------------------------------


def _old_get_components(guide_name):
    """get_components before the Guide Explorer refresh change."""
    import mgear.pymaya as pm

    components = pm.listRelatives(
        guide_name,
        children=True,
        allDescendents=True,
        type="transform",
        fullPath=True,
    )
    return [cmp for cmp in components if cmp.hasAttr("comp_type")]


def test_get_components_unchanged(import_template):
    from mgear.shifter import utils

    guide_root = import_template("biped.sgt")
    expected = [node.longName() for node in _old_get_components(guide_root)]
    result = utils.get_components(guide_root)
    assert len(result) == 38
    assert [node.longName() for node in result] == expected


def test_scene_state_follows_guide_changes(small_guide):
    from maya import cmds

    from mgear.shifter.guide_explorer import utils

    state = utils.GuideSceneState()
    assert state.update()
    assert len(state.snapshot) == 3
    assert state.snapshot[0] == cmds.ls("guide", uuid=True)[0]

    other = cmds.createNode("transform", name="unrelated")
    assert not state.update()
    cmds.delete(other)
    assert not state.update()

    added = small_guide("control_01")
    assert state.update()
    assert len(state.snapshot) == 4
    cmds.delete(added)
    assert state.update()
    assert len(state.snapshot) == 3

    cmds.delete("guide")
    assert state.update()
    assert state.snapshot == ()
    assert not state.update()


# Explorer refresh ------------------------------------------------------------


def test_unrelated_transform_does_not_rebuild(explorer, count_calls, monkeypatch):
    from maya import cmds

    from mgear.shifter.guide_explorer import guide_explorer_widget
    from mgear.shifter.guide_explorer import guide_tree_widget

    tree = explorer.guide_tree_widget
    populates = count_calls(guide_tree_widget.GuideTreeWidget, "_populate")
    panels = count_calls(guide_explorer_widget.GuideExplorerWidget, "_show_panel")
    monkeypatch.setattr(tree, "isVisible", lambda: True)

    node = cmds.createNode("transform", name="unrelated")
    tree._pending_scene_refresh = True
    tree._process_pending_scene_refresh()
    cmds.delete(node)
    assert not explorer.refresh()
    assert not populates
    assert not panels


def test_rebuild_keeps_selection(explorer, small_guide, count_calls):
    from mgear.shifter.guide_explorer import guide_explorer_widget
    from mgear.shifter.guide_explorer import guide_tree_widget
    from mgear.shifter.guide_explorer.models import ShifterComponent

    tree = explorer.guide_tree_widget
    _select_item(tree, "arm_C0")
    assert explorer.current_widget.root.name() == "arm_C0_root"
    panels = count_calls(guide_explorer_widget.GuideExplorerWidget, "_show_panel")

    added = small_guide("control_01")
    assert tree.refresh()
    assert _selected_texts(tree) == ["arm_C0"]
    assert tree.currentItem().text(0) == "arm_C0"
    assert tree.topLevelItem(0).childCount() == 3
    assert not panels

    # -- Deleting the selected component selects the guide root
    from maya import cmds

    cmds.delete("arm_C0_root")
    assert tree.refresh()
    assert _selected_texts(tree) == [tree.topLevelItem(0).text(0)]
    assert explorer.current_widget.root.name() == "guide"
    data = [
        tree.topLevelItem(0).child(i).data(0, guide_tree_widget.DATA_ROLE)
        for i in range(tree.topLevelItem(0).childCount())
    ]
    assert all(isinstance(d, ShifterComponent) for d in data)
    assert added in [d.root_name for d in data]


def test_same_item_does_not_rebuild_panel(explorer, count_calls):
    from mgear.shifter.guide_explorer import guide_explorer_widget

    tree = explorer.guide_tree_widget
    _select_item(tree, "arm_C0")
    panels = count_calls(guide_explorer_widget.GuideExplorerWidget, "_show_panel")
    _select_item(tree, "arm_C0")
    explorer.open_guide_widget()
    explorer.open_guide_widget()
    assert len(panels) == 1
    assert explorer.current_widget.root.name() == "guide"


def test_rename_updates_label_and_panel(explorer, count_calls):
    from maya import cmds

    from mgear.shifter.guide_explorer import guide_explorer_widget
    from mgear.shifter.guide_explorer import guide_tree_widget

    tree = explorer.guide_tree_widget
    _select_item(tree, "arm_C0")
    panels = count_calls(guide_explorer_widget.GuideExplorerWidget, "_show_panel")
    cmds.setAttr("arm_C0_root.comp_name", "limb", type="string")
    assert tree.currentItem().text(0) == "limb_C0"
    data = tree.currentItem().data(0, guide_tree_widget.DATA_ROLE)
    assert data.full_name == "limb_C0"
    assert len(panels) == 1


def test_renamed_node_name_reused(explorer):
    from maya import cmds

    from mgear.shifter.guide_explorer import guide_tree_widget

    tree = explorer.guide_tree_widget
    cmds.rename("arm_C0_root", "renamed_root")
    impostor = cmds.createNode("transform", name="arm_C0_root")
    cmds.addAttr(impostor, longName="comp_name", dataType="string")
    cmds.setAttr(impostor + ".comp_name", "other", type="string")
    assert _item(tree, "arm_C0")

    cmds.setAttr("renamed_root.comp_name", "limb", type="string")
    data = _item(tree, "limb_C0").data(0, guide_tree_widget.DATA_ROLE)
    assert data.root_name == "renamed_root"


def test_panels_keep_maya_selection(explorer, selection_changes):
    from maya import cmds

    from mgear.shifter.guide_explorer import guide_tree_widget

    cube = cmds.polyCube(name="mesh", constructionHistory=False)[0]
    cmds.select(cube)
    del selection_changes[:]

    tree = explorer.guide_tree_widget
    explorer.open_guide_widget(force=True)
    comp = _item(tree, "arm_C0").data(0, guide_tree_widget.DATA_ROLE)
    explorer.open_component_widget(comp, force=True)
    assert explorer.current_widget.root.name() == "arm_C0_root"
    assert cmds.ls(selection=True) == [cube]
    assert not selection_changes


def test_delete_rebuilds_once(explorer, count_calls, monkeypatch):
    from maya import cmds

    from mgear.shifter.guide_explorer import guide_tree_widget

    tree = explorer.guide_tree_widget
    monkeypatch.setattr(tree, "isVisible", lambda: True)
    _select_item(tree, "arm_C0")
    populates = count_calls(guide_tree_widget.GuideTreeWidget, "_populate")
    tree._enable_scene_callbacks()
    try:
        tree.on_delete_action_clicked()
    finally:
        tree._disable_scene_callbacks()
    assert not cmds.objExists("arm_C0_root")
    # -- The debounced node removed refresh, if the timer hasn't run it yet
    tree._pending_scene_refresh = True
    tree._process_pending_scene_refresh()
    assert len(populates) == 1
    assert _selected_texts(tree) == [tree.topLevelItem(0).text(0)]


def test_shortcuts_unique(explorer):
    tree = explorer.guide_tree_widget
    shortcuts = [
        action.shortcut().toString()
        for action in tree.actions()
        if not action.shortcut().isEmpty()
    ]
    assert len(shortcuts) == len(set(shortcuts))
    assert tree.unbuild_action.shortcut().toString() == "Ctrl+U"
    assert tree.update_component_type_action.shortcut().toString() == "Ctrl+T"


def _blueprint_file(tmp_path, names):
    """Write a blueprint guide file with the given component names."""
    path = tmp_path / "blueprint.sgt"
    path.write_text(json.dumps({"components_dict": {name: {} for name in names}}))
    return str(path)


def test_blueprint_read_once(explorer, tmp_path, count_calls):
    from maya import cmds

    from mgear.shifter import guide

    loads = count_calls(guide, "load_blueprint_guide")
    cmds.setAttr("guide.use_blueprint", True)
    cmds.setAttr(
        "guide.blueprint_path", _blueprint_file(tmp_path, ["arm_C0"]), type="string"
    )
    tree = explorer.guide_tree_widget
    tree.refresh(force=True)
    tree.refresh(force=True)
    assert len(loads) == 1


def test_blueprint_colors_follow_settings(explorer, tmp_path, count_calls):
    from maya import cmds

    from mgear.vendor.Qt import QtCore

    from mgear.shifter.guide_explorer import guide_tree_widget

    tree = explorer.guide_tree_widget
    populates = count_calls(guide_tree_widget.GuideTreeWidget, "_populate")

    def color(text):
        brush = _item(tree, text).data(0, QtCore.Qt.ForegroundRole)
        return brush.color() if brush is not None else None

    assert color("arm_C0") is None

    # -- Enabling a blueprint colors its components, without a rebuild
    cmds.setAttr(
        "guide.blueprint_path", _blueprint_file(tmp_path, ["arm_C0"]), type="string"
    )
    cmds.setAttr("guide.use_blueprint", True)
    assert color("arm_C0") == guide_tree_widget.BLUEPRINT_COLOR_ACTIVE
    assert color("control_C0") is None
    assert "Blueprint: Active" in _item(tree, "arm_C0").toolTip(0)

    # -- A local override turns the component yellow
    cmds.setAttr("arm_C0_root.blueprint_local_override", True)
    assert color("arm_C0") == guide_tree_widget.BLUEPRINT_COLOR_OVERRIDE

    # -- A rename out of the blueprint drops the color
    cmds.setAttr("arm_C0_root.comp_name", "limb", type="string")
    assert color("limb_C0") is None

    # -- Disabling the blueprint clears the colors
    cmds.setAttr("arm_C0_root.comp_name", "arm", type="string")
    assert color("arm_C0") == guide_tree_widget.BLUEPRINT_COLOR_OVERRIDE
    cmds.setAttr("guide.use_blueprint", False)
    assert color("arm_C0") is None
    assert _item(tree, "arm_C0").toolTip(0) == "arm_C0"
    assert not populates


def test_delete_after_root_renamed(explorer):
    from maya import cmds

    tree = explorer.guide_tree_widget
    cmds.rename("arm_C0_root", "renamed_root")
    _select_item(tree, "arm_C0")
    tree.on_delete_action_clicked()
    assert not cmds.objExists("renamed_root")
    assert [
        tree.topLevelItem(0).child(i).text(0)
        for i in range(tree.topLevelItem(0).childCount())
    ] == ["control_C0"]


def test_sync_selection_from_viewport(explorer):
    from maya import cmds

    tree = explorer.guide_tree_widget
    explorer.sync_checkbox.setChecked(True)
    tree._enable_scene_callbacks()
    try:
        cmds.select("arm_C0_elbow")
        assert tree.currentItem().text(0) == "arm_C0"
        assert explorer.current_widget.root.name() == "arm_C0_root"
        assert cmds.ls(selection=True) == ["arm_C0_elbow"]

        # -- A tree click still selects the component root in Maya
        _select_item(tree, "control_C0")
        assert cmds.ls(selection=True) == ["control_C0_root"]
    finally:
        tree._disable_scene_callbacks()
