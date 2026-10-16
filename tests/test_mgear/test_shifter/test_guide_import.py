"""Shifter guide template import tests"""

import json

import pytest


def _guide_template():
    """Draw a control_01 + arm_2jnt_01 guide and return its template."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide
    from mgear.shifter import io

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    root = pm.PyNode("control_C0_root")
    guide.Rig().drawNewComponent(root, "arm_2jnt_01", showUI=False)
    return io.get_guide_template_dict(pm.PyNode("guide"))


def _short(nodes):
    """Short names of a list of long names."""
    return [node.split("|")[-1] for node in nodes]


def _world_pos(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, translation=True)


@pytest.fixture
def guide_scene(rig_plugins, setup_path):
    """Scene with the control + arm guide, and its template."""
    return _guide_template()


def test_import_clears_selection(rig_plugins, setup_path):
    """Importing a template leaves nothing selected."""
    from maya import cmds
    from mgear.shifter import io

    conf = _guide_template()
    cmds.file(new=True, force=True)
    roots = io.import_guide_template(conf=conf)
    # Only the top component is drawn directly under the new guide
    assert roots == ["|guide|control_C0_root"]
    assert cmds.objExists("arm_C0_root")
    assert cmds.ls(selection=True) == []


def test_partial_import_clears_selection(rig_plugins, setup_path):
    """Adding a component from a template leaves nothing selected."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import io

    conf = _guide_template()
    cmds.select("control_C0_root")
    io.import_partial_guide(
        partial="arm_C0", initParent=pm.PyNode("control_C0_root"), conf=conf
    )
    assert cmds.objExists("arm_C1_root")
    assert cmds.ls(selection=True) == []


# Selected guide element ------------------------------------------------------


def test_selected_guide_element(guide_scene):
    from maya import cmds
    from mgear.shifter import io

    cmds.select("control_C0_root")
    assert io.get_selected_guide_element().name() == "control_C0_root"

    cmds.select("arm_C0_elbow")
    assert io.get_selected_guide_element().name() == "arm_C0_elbow"

    cmds.select("guide")
    assert io.get_selected_guide_element() is None

    cmds.select(cmds.createNode("transform", name="outside"))
    assert io.get_selected_guide_element() is None

    cmds.select(clear=True)
    assert io.get_selected_guide_element() is None


def test_template_components(guide_scene):
    from mgear.shifter import io

    components = io.get_template_components(guide_scene)
    assert [c["name"] for c in components] == ["control_C0", "arm_C0"]
    assert components[0]["parent"] is None
    assert components[1]["parent"] == "control_C0"
    assert components[1]["comp_type"] == "arm_2jnt_01"


# Import into a guide element -------------------------------------------------


def test_import_into_whole_template(guide_scene):
    from maya import cmds
    from mgear.shifter import io

    cmds.select("control_C0_root")
    roots = io.import_guide_into("control_C0_root", conf=guide_scene)
    assert _short(roots) == ["control_C1_root"]
    assert cmds.listRelatives(roots[0], parent=True) == ["control_C0_root"]
    assert cmds.objExists("arm_C1_root")
    assert cmds.ls(selection=True) == []
    # Without snap the template positions are kept
    assert _world_pos(roots[0]) == pytest.approx(_world_pos("control_C0_root"))


def test_import_into_partial(guide_scene):
    from maya import cmds
    from mgear.shifter import io

    roots = io.import_guide_into(
        "control_C0_root", conf=guide_scene, partial=["arm_C0"]
    )
    assert _short(roots) == ["arm_C1_root"]
    assert not cmds.objExists("control_C1_root")


def test_import_into_not_a_guide(guide_scene):
    from maya import cmds
    from mgear.shifter import io

    outside = cmds.createNode("transform", name="outside")
    assert io.import_guide_into(outside, conf=guide_scene) == []
    assert not cmds.objExists("control_C1_root")


# Snap ------------------------------------------------------------------------


def test_import_into_snap(guide_scene):
    from maya import cmds
    from mgear.shifter import io

    cmds.xform("arm_C0_wrist", worldSpace=True, translation=(5, 2, 0))
    roots = io.import_guide_into("arm_C0_wrist", conf=guide_scene, snap=True)
    assert _short(roots) == ["control_C1_root"]
    assert _world_pos(roots[0]) == pytest.approx([5, 2, 0])


def test_snap_keeps_root_spacing(rig_plugins, setup_path):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide
    from mgear.shifter import io

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    guide.Rig().drawNewComponent(pm.PyNode("guide"), "control_01", showUI=False)
    cmds.xform("control_C1_root", worldSpace=True, translation=(3, 0, 0))
    conf = io.get_guide_template_dict(pm.PyNode("guide"))

    cmds.xform("control_C0_root", worldSpace=True, translation=(0, 4, 0))
    roots = io.import_guide_into(
        "control_C0_root",
        conf=conf,
        partial=["control_C0", "control_C1"],
        snap=True,
    )
    assert len(roots) == 2
    assert _world_pos(roots[0]) == pytest.approx([0, 4, 0])
    assert _world_pos(roots[1]) == pytest.approx([3, 4, 0])


# Interactive import ----------------------------------------------------------


@pytest.fixture
def sgt_file(guide_scene, tmp_path):
    path = tmp_path / "control_arm.sgt"
    path.write_text(json.dumps(guide_scene))
    return str(path)


@pytest.fixture
def ask(monkeypatch):
    """Patch the import options dialog.

    Returns:
        callable: Called with the result the dialog returns. Returns the
            list of the dialog calls.
    """
    from mgear.shifter import io

    calls = []

    def set_result(result):
        def fake(*args):
            calls.append(args)
            return result

        monkeypatch.setattr(io, "_ask_import_choice", fake)
        return calls

    return set_result


def test_interactive_no_target_no_prompt(sgt_file, ask):
    from maya import cmds
    from mgear.shifter import io

    calls = ask((io.IMPORT_CANCEL, None, False))
    cmds.file(new=True, force=True)
    io.import_guide_interactive(sgt_file)
    assert calls == []
    assert cmds.objExists("control_C0_root")


def test_interactive_add(sgt_file, ask):
    from maya import cmds
    from mgear.shifter import io

    calls = ask((io.IMPORT_ADD, None, False))
    cmds.select("control_C0_root")
    io.import_guide_interactive(sgt_file)
    file_name, components, target_name, allow_build = calls[0]
    assert file_name == "control_arm.sgt"
    assert [c["name"] for c in components] == ["control_C0", "arm_C0"]
    assert target_name == "control_C0_root"
    assert allow_build is False
    assert cmds.listRelatives("control_C1_root", parent=True) == ["control_C0_root"]


def test_interactive_partial_snap(sgt_file, ask):
    from maya import cmds
    from mgear.shifter import io

    ask((io.IMPORT_ADD, ["arm_C0"], True))
    cmds.xform("arm_C0_wrist", worldSpace=True, translation=(1, 7, 0))
    cmds.select("arm_C0_wrist")
    io.import_guide_interactive(sgt_file)
    assert not cmds.objExists("control_C1_root")
    assert cmds.listRelatives("arm_C1_root", parent=True) == ["arm_C0_wrist"]
    assert _world_pos("arm_C1_root") == pytest.approx([1, 7, 0])


def test_interactive_cancel(sgt_file, ask):
    from maya import cmds
    from mgear.shifter import io

    ask((io.IMPORT_CANCEL, None, False))
    cmds.select("control_C0_root")
    io.import_guide_interactive(sgt_file, allow_build=True)
    assert not cmds.objExists("control_C1_root")
    assert len(cmds.ls("*.ismodel")) == 1


def test_import_template_never_prompts(sgt_file, ask):
    from maya import cmds
    from mgear.shifter import io

    calls = ask((io.IMPORT_ADD, None, False))
    cmds.select("control_C0_root")
    io.import_guide_template(filePath=sgt_file)
    assert calls == []
    assert len(cmds.ls("*.ismodel")) == 2
