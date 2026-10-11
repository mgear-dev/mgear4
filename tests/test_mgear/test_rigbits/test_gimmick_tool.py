"""mgear.rigbits.gimmick_tool tests: blend and support gimmick joints"""

import json
import sys

import pytest


def _round(values, digits=4):
    return [round(v, digits) + 0.0 for v in values]


def _world(node):
    from maya import cmds

    return _round(cmds.xform(node, query=True, matrix=True, worldSpace=True))


@pytest.fixture
def scene(setup_path):
    """New scene with a left arm chain and its behavior mirrored right arm.

    ``arm_L0_0_jnt`` > ``arm_L0_1_jnt`` > ``arm_L0_2_jnt`` and the same
    joints with ``R0``.
    """
    from maya import cmds

    cmds.file(new=True, force=True)
    cmds.select(clear=True)
    root = cmds.joint(name="arm_L0_0_jnt", position=(1, 10, 0))
    cmds.joint(name="arm_L0_1_jnt", position=(4, 9, -1))
    cmds.joint(name="arm_L0_2_jnt", position=(7, 9, 0))
    cmds.joint(
        root, edit=True, orientJoint="xyz", secondaryAxisOrient="yup", children=True
    )
    cmds.mirrorJoint(
        root, mirrorYZ=True, mirrorBehavior=True, searchReplace=("_L0_", "_R0_")
    )
    cmds.select(clear=True)
    return cmds


@pytest.fixture
def core(setup_path):
    from mgear.rigbits.gimmick_tool import core

    return core


def _legacy_blend(source, blend=0.5):
    """Blend joint made like the mGear 5.3 addBlendedJoint (no tag)."""
    from maya import cmds

    parent = cmds.listRelatives(source, parent=True)[0]
    jnt = cmds.createNode("joint", name="blend_" + source, parent=source)
    cmds.setAttr(jnt + ".radius", 1.5)
    jnt = cmds.parent(jnt, parent)[0]
    pb = cmds.createNode("pairBlend")
    cmds.setAttr(pb + ".rotInterpolation", 1)
    cmds.setAttr(pb + ".weight", blend)
    cmds.connectAttr(source + ".translate", pb + ".inTranslate1")
    cmds.connectAttr(source + ".translate", pb + ".inTranslate2")
    cmds.connectAttr(source + ".rotate", pb + ".inRotate1")
    for axis in "XYZ":
        cmds.connectAttr(pb + ".outRotate" + axis, jnt + ".rotate" + axis)
        cmds.connectAttr(pb + ".outTranslate" + axis, jnt + ".translate" + axis)
    cmds.connectAttr(source + ".scale", jnt + ".scale")
    return jnt


def _legacy_support(blend, index=0):
    from maya import cmds

    name = blend.replace("blend", "blendSupport_%d" % index)
    return cmds.createNode("joint", name=name, parent=blend)


# Blend joints ----------------------------------------------------------------


def test_blend_joint_at_rest_and_posed(scene, core):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt")
    assert blend == "blend_arm_L0_1_jnt"
    assert cmds.listRelatives(blend, parent=True) == ["arm_L0_0_jnt"]
    assert _world(blend) == _world("arm_L0_1_jnt")
    pb = cmds.listConnections(blend + ".rotateX", source=True, type="pairBlend")[0]
    assert cmds.getAttr(pb + ".rotInterpolation") == 1
    assert cmds.getAttr(pb + ".weight") == pytest.approx(0.5)
    assert cmds.getAttr(blend + ".radius") == pytest.approx(1.5)
    assert cmds.getAttr(blend + ".overrideColor") == 17
    assert cmds.getAttr(blend + ".segmentScaleCompensate")
    assert cmds.getAttr(blend + ".gimmickType") == 0
    cmds.setAttr("arm_L0_1_jnt.rotateZ", 90)
    assert _round(cmds.getAttr(blend + ".rotate")[0]) == [0.0, 0.0, 45.0]
    cmds.setAttr("arm_L0_1_jnt.scaleY", 2)
    assert cmds.getAttr(blend + ".scaleY") == pytest.approx(2)


def test_blend_joint_matches_legacy_at_rest(scene, core):
    cmds = scene
    legacy = _legacy_blend("arm_L0_1_jnt")
    legacy_world = _world(legacy)
    legacy_orient = _round(cmds.getAttr(legacy + ".jointOrient")[0])
    cmds.delete(legacy)
    blend = core.create_blend_joint("arm_L0_1_jnt")
    assert _world(blend) == legacy_world
    assert _round(cmds.getAttr(blend + ".jointOrient")[0]) == legacy_orient


def test_blend_joint_created_posed_is_correct_at_rest(scene, core):
    cmds = scene
    cmds.setAttr("arm_L0_1_jnt.rotate", 10, 20, 30)
    blend = core.create_blend_joint("arm_L0_1_jnt")
    cmds.setAttr("arm_L0_1_jnt.rotate", 0, 0, 0)
    assert _world(blend) == _world("arm_L0_1_jnt")


def test_blend_joint_custom_value_and_name(scene, core):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt", blend=0.25, name="elbow")
    assert blend == "blend_elbow"
    assert core.get_blend_value(blend) == pytest.approx(0.25)
    assert core.get_source_joint(blend) == "arm_L0_1_jnt"


def test_blend_joint_deformer_set(scene, core):
    cmds = scene
    assert not cmds.objExists("rig_deformers_grp")
    blend = core.create_blend_joint("arm_L0_1_jnt")
    assert cmds.sets(blend, isMember="rig_deformers_grp")


def test_blend_joint_existing(scene, core):
    cmds = scene
    first = core.create_blend_joint("arm_L0_1_jnt")
    again = core.create_blend_joint("arm_L0_1_jnt")
    assert again == first
    assert len(cmds.ls("blend_arm_L0_1_jnt*", type="joint")) == 1


def test_blend_joint_not_a_joint(scene, core):
    cmds = scene
    loc = cmds.spaceLocator(name="loc")[0]
    assert core.create_blend_joint(loc) is None
    assert not cmds.ls("blend_*")


# Support joints --------------------------------------------------------------


def test_support_joints_indices(scene, core):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt")
    s0 = core.create_support_joint(blend)
    s1 = core.create_support_joint(blend)
    assert s0 == "blendSupport_0_arm_L0_1_jnt"
    assert s1 == "blendSupport_1_arm_L0_1_jnt"
    assert cmds.listRelatives(s0, parent=True) == [blend]
    assert _world(s0) == _world(blend)
    assert cmds.getAttr(s0 + ".gimmickType") == 1
    assert cmds.sets(s0, isMember="rig_deformers_grp")


def test_support_index_reuse(scene, core):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt")
    supports = [core.create_support_joint(blend) for _ in range(3)]
    cmds.delete(supports[1])
    assert core.create_support_joint(blend) == "blendSupport_1_arm_L0_1_jnt"


def test_support_not_on_blend(scene, core):
    cmds = scene
    assert core.create_support_joint("arm_L0_1_jnt") is None
    assert not cmds.ls("blendSupport_*")


# Recognition -----------------------------------------------------------------


def test_legacy_joints_recognised(scene, core):
    cmds = scene
    legacy = _legacy_blend("arm_L0_1_jnt", blend=0.3)
    support = _legacy_support(legacy)
    assert core.is_blend_joint(legacy)
    assert core.is_support_joint(support)
    assert core.get_source_joint(legacy) == "arm_L0_1_jnt"
    assert core.list_gimmick_joints(kind=core.BLEND) == [legacy]
    assert core.list_gimmick_joints(kind=core.SUPPORT) == [support]


def test_unrelated_blend_name_ignored(scene, core):
    cmds = scene
    cmds.select(clear=True)
    cmds.joint(name="blend_test")
    assert core.list_gimmick_joints() == []


def test_list_by_side(scene, core):
    cmds = scene
    cmds.select(clear=True)
    cmds.joint(name="spine_C0_1_jnt")
    for jnt in ("arm_L0_1_jnt", "arm_R0_1_jnt", "spine_C0_1_jnt"):
        core.create_blend_joint(jnt)
    assert core.list_gimmick_joints(side=core.LEFT) == ["blend_arm_L0_1_jnt"]
    assert core.list_gimmick_joints(side=core.RIGHT) == ["blend_arm_R0_1_jnt"]
    assert core.list_gimmick_joints(side=[core.CENTER]) == ["blend_spine_C0_1_jnt"]


# Side rules ------------------------------------------------------------------


def test_side_without_rig(scene, core):
    assert core.get_side("arm_L0_1_jnt") == core.LEFT
    assert core.get_side("arm_R0_1_jnt") == core.RIGHT
    assert core.get_side("spine_C0_1_jnt") == core.CENTER
    assert core.get_mirror_name("leg_L0_1_jnt") == "leg_R0_1_jnt"
    assert core.get_mirror_name("blend_arm_L0_1_jnt") == "blend_arm_R0_1_jnt"
    assert core.get_mirror_name("ns:arm_R0_1_jnt") == "ns:arm_L0_1_jnt"


def test_side_with_rig_custom_names(scene, core):
    cmds = scene
    rig = cmds.createNode("transform", name="rig")
    cmds.addAttr(rig, longName="is_rig", attributeType="bool")
    params = {
        "joint_name_rule": "{component}_{side}{index}_{description}_{extension}",
        "side_joint_left_name": "Lf",
        "side_joint_right_name": "Rt",
        "side_joint_center_name": "Ct",
        "joint_name_ext": "jnt",
    }
    cmds.addAttr(rig, longName="guide_data", dataType="string")
    cmds.setAttr(
        rig + ".guide_data",
        json.dumps({"guide_root": {"param_values": params}}),
        type="string",
    )
    cmds.select(rig)
    left = cmds.joint(name="arm_Lf0_1_jnt", position=(3, 0, 0))
    cmds.select(rig)
    right = cmds.joint(name="arm_Rt0_1_jnt", position=(-3, 0, 0))
    assert core.get_side(left) == core.LEFT
    assert core.get_side(right) == core.RIGHT
    assert core.get_mirror_name(left) == "arm_Rt0_1_jnt"

    core.create_blend_joint(left)
    created = core.mirror_gimmick_joints()
    assert created == ["blend_arm_Rt0_1_jnt"]
    assert core.get_source_joint(created[0]) == "arm_Rt0_1_jnt"


def test_naming_rules_from_built_rig(setup_path, core, load_repo_plugin):
    from maya import cmds

    for name in ("mgear_solvers", "mGearWeightDriver"):
        if not load_repo_plugin(name):
            pytest.skip("{} plug-in not available".format(name))
    import mgear.pymaya as pm
    from mgear import shifter
    from mgear.shifter import guide

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    cmds.select("guide")
    shifter.Rig().buildFromSelection()
    rules = core.get_naming_rules("control_C0_ctl")
    assert rules["left"] == "L"
    assert rules["right"] == "R"
    assert rules["ext"] == "jnt"


# Mirror ----------------------------------------------------------------------


def test_mirror_blend_and_support(scene, core):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt", blend=0.3)
    support = core.create_support_joint(blend)
    cmds.setAttr(support + ".translate", 0, 1, 0.5)
    cmds.setAttr(support + ".jointOrient", 10, 0, 0)
    left_before = {
        n: (_world(n), cmds.listRelatives(n, parent=True)) for n in (blend, support)
    }

    created = core.mirror_gimmick_joints(direction=core.LEFT_TO_RIGHT)

    assert created == ["blend_arm_R0_1_jnt", "blendSupport_0_arm_R0_1_jnt"]
    r_blend, r_support = created
    assert core.get_source_joint(r_blend) == "arm_R0_1_jnt"
    assert core.get_blend_value(r_blend) == pytest.approx(0.3)
    assert cmds.listRelatives(r_support, parent=True) == [r_blend]
    left_pos = cmds.xform(support, query=True, translation=True, worldSpace=True)
    right_pos = cmds.xform(r_support, query=True, translation=True, worldSpace=True)
    assert _round(right_pos) == _round([-left_pos[0], left_pos[1], left_pos[2]])
    # behavior mirror: the X and Y axes are reflected and negated
    lm = cmds.xform(support, query=True, matrix=True, worldSpace=True)
    rm = cmds.xform(r_support, query=True, matrix=True, worldSpace=True)
    assert _round(rm[0:3]) == _round([lm[0], -lm[1], -lm[2]])
    assert _round(cmds.getAttr(r_support + ".rotate")[0]) == [0.0, 0.0, 0.0]
    for node, state in left_before.items():
        assert (_world(node), cmds.listRelatives(node, parent=True)) == state


def test_mirror_legacy_support_name(scene, core):
    cmds = scene
    legacy = _legacy_blend("arm_L0_1_jnt")
    _legacy_support(legacy, 0)
    created = core.mirror_gimmick_joints()
    assert "blendSupport_0_arm_R0_1_jnt" in created


def test_mirror_right_to_left(scene, core):
    core.create_blend_joint("arm_R0_1_jnt")
    created = core.mirror_gimmick_joints(direction=core.RIGHT_TO_LEFT)
    assert created == ["blend_arm_L0_1_jnt"]


def test_mirror_missing_opposite(scene, core):
    cmds = scene
    cmds.select(clear=True)
    cmds.joint(name="tail_L0_0_jnt")
    core.create_blend_joint("tail_L0_0_jnt")
    core.create_blend_joint("arm_L0_1_jnt")
    created = core.mirror_gimmick_joints()
    assert created == ["blend_arm_R0_1_jnt"]


def test_mirror_keeps_existing(scene, core):
    cmds = scene
    core.create_blend_joint("arm_L0_1_jnt", blend=0.2)
    right = core.create_blend_joint("arm_R0_1_jnt", blend=0.7)
    assert core.mirror_gimmick_joints() == []
    assert core.get_blend_value(right) == pytest.approx(0.7)
    created = core.mirror_gimmick_joints(replace=True)
    assert created == ["blend_arm_R0_1_jnt"]
    assert core.get_blend_value(created[0]) == pytest.approx(0.2)


# Flip and delete -------------------------------------------------------------


def test_flip_orientation(scene, core):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt")
    support = core.create_support_joint(blend)
    assert core.flip_orientation([support, blend], "Y") == [support]
    assert _round(cmds.getAttr(support + ".jointOrient")[0]) == [0.0, 180.0, 0.0]
    cmds.setAttr(support + ".jointOrientZ", 300)
    core.flip_orientation([support], "z")
    assert cmds.getAttr(support + ".jointOrientZ") == pytest.approx(120)


def test_delete_by_side(scene, core):
    cmds = scene
    left = core.create_blend_joint("arm_L0_1_jnt")
    core.create_support_joint(left)
    right = core.create_blend_joint("arm_R0_1_jnt")
    right_support = core.create_support_joint(right)
    left_pb = cmds.listConnections(left + ".rotateX", type="pairBlend")[0]

    deleted = core.delete_gimmick_joints(core.list_gimmick_joints(side=core.LEFT))

    assert set(deleted) == {"blend_arm_L0_1_jnt", "blendSupport_0_arm_L0_1_jnt"}
    assert not cmds.objExists(left)
    assert not cmds.objExists(left_pb)
    assert set(core.list_gimmick_joints()) == {right, right_support}


# File IO ---------------------------------------------------------------------


def test_file_round_trip(scene, core, tmp_path):
    cmds = scene
    blend = core.create_blend_joint("arm_L0_1_jnt", blend=0.35, comp_scale=False)
    cmds.setAttr(blend + ".radius", 2.5)
    cmds.setAttr(blend + ".overrideColor", 13)
    support = core.create_support_joint(blend)
    cmds.setAttr(support + ".translate", 0, 1.5, 0)
    cmds.setAttr(support + ".jointOrient", 0, 0, 25)
    custom = core.create_blend_joint("arm_R0_1_jnt", name="elbowR")
    before = {
        n: (
            _world(n),
            cmds.listRelatives(n, parent=True),
            cmds.getAttr(n + ".radius"),
            cmds.getAttr(n + ".overrideColor"),
            cmds.getAttr(n + ".segmentScaleCompensate"),
        )
        for n in (blend, support, custom)
    }
    path = core.export_file(str(tmp_path / "gimmick"))
    assert path.endswith(".gst")
    data = json.load(open(path))
    assert data["type"] == "gimmick_joints"
    assert data["schema_version"] == 1

    core.delete_gimmick_joints(core.list_gimmick_joints())
    assert core.list_gimmick_joints() == []
    created = core.import_file(path)

    assert set(created) == {blend, support, custom}
    assert core.get_blend_value(blend) == pytest.approx(0.35)
    assert core.get_source_joint(custom) == "arm_R0_1_jnt"
    for node, state in before.items():
        after = (
            _world(node),
            cmds.listRelatives(node, parent=True),
            cmds.getAttr(node + ".radius"),
            cmds.getAttr(node + ".overrideColor"),
            cmds.getAttr(node + ".segmentScaleCompensate"),
        )
        assert after == state


def test_file_import_skips_existing(scene, core, tmp_path):
    blend = core.create_blend_joint("arm_L0_1_jnt", blend=0.4)
    path = core.export_file(str(tmp_path / "g.gst"))
    from maya import cmds

    cmds.setAttr(cmds.listConnections(blend + ".rotateX")[0] + ".weight", 0.9)
    assert core.import_file(path, replace=False) == []
    assert core.get_blend_value(blend) == pytest.approx(0.9)
    core.import_file(path)
    assert core.get_blend_value(blend) == pytest.approx(0.4)


def test_file_wrong_type(scene, core, tmp_path):
    from mgear.core import config_io

    path = str(tmp_path / "x.lat")
    config_io.write_file(path, "lattice_config", 1, "lattices", [])
    with pytest.raises(ValueError):
        core.import_file(path)
    assert core.list_gimmick_joints() == []


def test_file_legacy_headerless(scene, core, tmp_path):
    cmds = scene
    target = cmds.xform("arm_L0_1_jnt", query=True, translation=True, worldSpace=True)
    target = [target[0], target[1] + 1, target[2]]
    data = {
        "Blend": {
            "arm_L0_1_jnt_blend": {
                "drive": "arm_L0_1_jnt",
                "weightValue": 0.6,
                "parent": "arm_L0_0_jnt",
                "jointSize": 1.0,
                "jointColor": 17,
            }
        },
        "Support": {
            "arm_L0_1_jnt_support1": {
                "parent": "arm_L0_1_jnt_blend",
                "translate": target,
                "rotate": [0, 0, 0, 1],
                "jointSize": 0.5,
                "jointColor": 17,
            }
        },
    }
    path = str(tmp_path / "old.gst")
    with open(path, "w") as f:
        json.dump(data, f)
    created = core.import_file(path)
    assert created == ["blend_arm_L0_1_jnt", "blendSupport_0_arm_L0_1_jnt"]
    assert core.get_blend_value(created[0]) == pytest.approx(0.6)
    pos = cmds.xform(created[1], query=True, translation=True, worldSpace=True)
    assert _round(pos) == _round(target)
    assert _round(
        cmds.xform(created[1], query=True, matrix=True, worldSpace=True)[:3]
    ) == [
        1.0,
        0.0,
        0.0,
    ]


# Rigbits functions -----------------------------------------------------------


def test_rigbits_add_blended_joint(scene, core):
    cmds = scene
    import mgear.pymaya as pm
    from mgear import rigbits

    result = rigbits.addBlendedJoint(pm.PyNode("arm_L0_1_jnt"), blend=0.5)
    assert [j.name() for j in result] == ["blend_arm_L0_1_jnt"]
    assert isinstance(result[0], pm.nodetypes.Joint)
    assert core.is_blend_joint("blend_arm_L0_1_jnt")
    assert cmds.ls(selection=True) == ["blend_arm_L0_1_jnt"]
    assert rigbits.addBlendedJoint(pm.PyNode("arm_L0_0_jnt"), select=False)
    assert cmds.ls(selection=True) == ["blend_arm_L0_1_jnt"]


def test_rigbits_add_support_joint_from_selection(scene, core):
    cmds = scene
    from mgear import rigbits

    cmds.select("arm_L0_1_jnt", "arm_R0_1_jnt")
    blends = rigbits.addBlendedJoint()
    assert len(blends) == 2
    cmds.select("blend_arm_L0_1_jnt")
    supports = rigbits.addSupportJoint()
    assert [j.name() for j in supports] == ["blendSupport_0_arm_L0_1_jnt"]
    assert cmds.ls(selection=True) == ["blendSupport_0_arm_L0_1_jnt"]
    assert rigbits.addSupportJoint(cmds.ls("arm_L0_1_jnt")) == []


def test_rigbits_add_joint(scene):
    cmds = scene
    from mgear import rigbits

    loc = cmds.spaceLocator(name="foo_loc")[0]
    cmds.setAttr(loc + ".translate", 1, 2, 3)
    cmds.select(loc)
    jnt = rigbits.addJnt()
    assert jnt.name() == "foo_jnt"
    assert cmds.sets("foo_jnt", isMember="rig_deformers_grp")
    pos = cmds.xform("foo_jnt", query=True, translation=True, worldSpace=True)
    assert _round(pos) == [1.0, 2.0, 3.0]


# File drop and menu ----------------------------------------------------------


def test_file_drop_imports_gst(scene, core, tmp_path):
    from mgear.core import dragdrop

    core.create_blend_joint("arm_L0_1_jnt")
    path = core.export_file(str(tmp_path / "drop.gst"))
    core.delete_gimmick_joints(core.list_gimmick_joints())
    assert dragdrop.mgear_file_drop_action(path) == 1
    assert core.list_gimmick_joints() == ["blend_arm_L0_1_jnt"]


def test_dragdrop_does_not_import_gimmick_core(setup_path, scripts_path):
    import subprocess

    code = (
        "import sys; sys.path.insert(0, {!r});"
        "import maya.standalone; maya.standalone.initialize();"
        "import mgear.core.dragdrop;"
        "print('LOADED' if 'mgear.rigbits.gimmick_tool.core' in sys.modules "
        "else 'NOT_LOADED')".format(scripts_path)
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=600
    ).stdout
    assert "NOT_LOADED" in out


def test_menu_has_tool_and_no_submenu(setup_path):
    from mgear.rigbits import menu

    assert not hasattr(menu, "gimmick_submenu")
    assert "gimmick_tool" in menu.str_gimmick_tool


def test_list_finds_namespaced_joints(scene, core):
    cmds = scene
    cmds.namespace(add="char")
    cmds.namespace(set="char")
    cmds.select(clear=True)
    cmds.joint(name="leg_L0_0_jnt")
    src = cmds.joint(name="leg_L0_1_jnt", position=(1, 0, 0))
    cmds.namespace(set=":")
    legacy = cmds.rename(_legacy_blend(src), "char:blend_leg_L0_1_jnt")
    tagged = core.create_blend_joint("arm_L0_1_jnt")
    assert set(core.list_gimmick_joints()) == {legacy, tagged}


def test_pymaya_missing_node_is_type_error(setup_path):
    import mgear.pymaya as pm

    with pytest.raises(TypeError):
        pm.PyNode("no_such_node_anywhere")
    with pytest.raises(RuntimeError):
        pm.PyNode("no_such_node_anywhere")


def test_rig_root_path_moved_to_dag(scene):
    cmds = scene
    from mgear.core import anim_utils
    from mgear.core import dag

    rig = cmds.createNode("transform", name="rig")
    cmds.addAttr(rig, longName="is_rig", attributeType="bool")
    cmds.parent("arm_L0_0_jnt", rig)
    assert dag.find_rig_root_path("arm_L0_1_jnt") == "|rig"
    assert anim_utils._find_rig_root_path("arm_L0_1_jnt") == "|rig"
    assert anim_utils.find_rig_root("arm_L0_1_jnt") == "rig"


def test_custom_step_template(scene, core, tmp_path):
    cmds = scene
    from mgear.shifter import custom_step_templates

    names = dict(custom_step_templates.get_template_names())
    assert names["import_gimmick_joints_config"] == (
        "Import Gimmick Joints Configuration"
    )
    code = custom_step_templates.get_template_content(
        "import_gimmick_joints_config", "gimmick_step"
    )
    namespace = {}
    exec(compile(code, "gimmick_step.py", "exec"), namespace)
    step = namespace["CustomShifterStep"]({})
    step.setup()
    assert step.name == "gimmick_step"
    assert step.gimmick_path is None
    assert step.replace is True

    blend = core.create_blend_joint("arm_L0_1_jnt", blend=0.3)
    core.create_support_joint(blend)
    path = core.export_file(str(tmp_path / "step.gst"))
    core.delete_gimmick_joints(core.list_gimmick_joints())

    step.gimmick_path = path
    step.run()
    assert set(core.list_gimmick_joints()) == {
        "blend_arm_L0_1_jnt",
        "blendSupport_0_arm_L0_1_jnt",
    }
    assert core.get_blend_value("blend_arm_L0_1_jnt") == pytest.approx(0.3)
