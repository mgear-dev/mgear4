"""Shifter eyelid_01 component and its facial backend test"""

import pytest

# loop center z of the eye_face eyelid loops
LID_Z = 0.891


@pytest.fixture
def eyelid_guide(eye_face, rig_plugins):
    """Function drawing an eyelid_01 guide for an eye_face eye.

    Returns:
        callable: Called with side ("L"/"R"), parent (guide locator, optional),
            aim_z (aim locator world z) and guide settings. Returns the guide
            root name.
    """
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    def draw(side="L", parent=None, aim_z=1.2, **settings):
        before = set(cmds.ls("*_root", type="transform"))
        guide.Rig().drawNewComponent(
            pm.PyNode(parent) if parent else None, "eyelid_01", showUI=False
        )
        root = (set(cmds.ls("*_root", type="transform")) - before).pop()
        if cmds.getAttr(root + ".comp_side") != side:
            guide.Rig().updateProperties(pm.PyNode(root), "eyelid", side, 0)
            root = "eyelid_{}0_root".format(side)
        x = 1.0 if side == "L" else -1.0
        cmds.xform(root, worldSpace=True, translation=(x, 0, 0.75))
        cmds.xform(
            root.replace("_root", "_aim"),
            worldSpace=True,
            translation=(x, 0, aim_z),
        )
        cmds.setAttr(root + ".vertexLoop", eye_face[side]["vertex_loop"], type="string")
        for key, value in settings.items():
            if isinstance(value, str):
                cmds.setAttr("{}.{}".format(root, key), value, type="string")
            else:
                cmds.setAttr("{}.{}".format(root, key), value)
        return root

    return draw


def _build():
    from maya import cmds
    from mgear import shifter

    cmds.select("guide")
    rig = shifter.Rig()
    rig.buildFromSelection()
    cmds.select(clear=True)
    return rig


def _position(cmds, node):
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def _joints(cmds, pattern):
    return sorted(
        cmds.ls(pattern, type="joint"),
        key=lambda name: int("".join(c for c in name.split("_")[2] if c.isdigit())),
    )


def test_guide_params(eyelid_guide):
    from maya import cmds

    root = eyelid_guide()
    assert root == "eyelid_L0_root"
    assert cmds.objExists("eyelid_L0_aim")
    for key in ("vertexLoop", "edgeLoop", "upperVTrack", "doSkin", "eyeMesh"):
        assert cmds.attributeQuery(key, node=root, exists=True), key
    for key in ("namePrefix", "trackingSource", "offset", "sideRange", "headJnt"):
        assert not cmds.attributeQuery(key, node=root, exists=True), key
    assert cmds.getAttr(root + ".loopType") == 1


def test_standard_build(eyelid_guide, eye_face):
    from maya import cmds
    from mgear.core.facial import eyelid_solver
    from mgear.core import settings_schema
    from mgear.core.facial import eyelid_schema

    eyelid_guide()
    _build()
    for name in (
        "eyelid_L0_aim_ctl",
        "eyelid_L0_upBlink_ctl",
        "eyelid_L0_lowBlink_ctl",
        "eyelid_L0_inCorner_ctl",
        "eyelid_L0_upMid_ctl",
        "eyelid_L0_upEyelid_jnt_ref3",
    ):
        assert cmds.objExists(name), name
    upper = _joints(cmds, "eyelid_L0_upEyelid*_jnt")
    assert len(upper) == 11
    assert len(_joints(cmds, "eyelid_L0_lowEyelid*_jnt")) == 9
    assert cmds.objExists("eyelid_L0_center_jnt")
    settings = settings_schema.defaults(eyelid_schema.SCHEMA)
    settings.update(loopType=1, vertexLoop=eye_face["L"]["vertex_loop"])
    geometry = eyelid_solver.solve(
        settings, eye_center=(1, 0, 0.75), aim=(1, 0, 1.2), side="L"
    )
    for joint, point in zip(upper, geometry.upper_points):
        assert _position(cmds, joint) == pytest.approx(list(point), abs=1e-3)
    # aim control: look up, the upper lid follows
    cmds.setAttr("eyelid_L0_aim_ctl.rx", -20)
    assert cmds.getAttr("eyelid_L0_upMid_trk.ty") > 0
    assert cmds.getAttr("eyelid_L0_aim_ctl.invRy")


def test_aim_depth_sets_control_offset(eyelid_guide):
    from maya import cmds

    eyelid_guide(aim_z=LID_Z + 0.4)
    _build()
    box = cmds.exactWorldBoundingBox("eyelid_L0_inCorner_ctl")
    assert (box[2] + box[5]) * 0.5 == pytest.approx(LID_Z + 0.4, abs=0.02)


def test_eye_connector(eyelid_guide, eye_face):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    guide.Rig().drawNewComponent(None, "eye_01", showUI=False)
    guide.Rig().updateProperties(pm.PyNode("eye_C0_root"), "eye", "L", 0)
    cmds.xform("eye_L0_root", worldSpace=True, translation=(1, 0, 0.75))
    cmds.xform("eye_L0_look", worldSpace=True, translation=(1, 0, 3))
    root = eyelid_guide(parent="eye_L0_look")
    assert cmds.getAttr(root + ".connector") == "eye_01"
    _build()
    assert not cmds.objExists("eyelid_L0_aim_ctl")
    assert not cmds.objExists("eyelid_L0_center_jnt")
    rig_root = [r for r in cmds.ls("eyelid_L0_root", long=True) if "guide" not in r][0]
    parent = cmds.listRelatives(rig_root, parent=True)[0]
    assert parent == "eye_L0_Over_ctl"
    # the eye looks up: the upper lid follows
    cmds.setAttr("eye_L0_ik_ctl.ty", 1)
    assert cmds.getAttr("eyelid_L0_upMid_trk.ty") > 0


def test_eye_connector_without_eye(eyelid_guide, count_calls):
    from maya import cmds

    import mgear.pymaya as pm

    warnings = count_calls(pm, "displayWarning", lambda args, kwargs: args[0])
    root = eyelid_guide()
    cmds.setAttr(root + ".connector", "eye_01", type="string")
    _build()
    assert cmds.objExists("eyelid_L0_aim_ctl")
    assert any("eye_01 connector" in warning for warning in warnings)


def test_symmetrize(eyelid_guide, eye_face):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.core import meshNavigation
    from mgear.shifter import guide

    root = eyelid_guide()
    guide.Rig().duplicate(pm.PyNode(root), True)
    assert cmds.objExists("eyelid_R0_root")
    left = cmds.getAttr("eyelid_L0_root.vertexLoop")
    right = cmds.getAttr("eyelid_R0_root.vertexLoop")
    assert right == meshNavigation.mirror_component_string(left)[0]
    assert _position(cmds, "eyelid_R0_aim")[0] == pytest.approx(-1.0, abs=1e-4)
    _build()
    left_joints = _joints(cmds, "eyelid_L0_upEyelid*_jnt")
    right_joints = _joints(cmds, "eyelid_R0_upEyelid*_jnt")
    assert len(left_joints) == len(right_joints)
    for l_joint, r_joint in zip(left_joints, right_joints):
        x, y, z = _position(cmds, l_joint)
        assert _position(cmds, r_joint) == pytest.approx([-x, y, z], abs=1e-3)


def test_symmetrize_without_mirror(eyelid_guide, eye_face, count_calls):
    from maya import cmds

    import mgear
    import mgear.pymaya as pm
    from mgear.shifter import guide

    logs = count_calls(mgear, "log", lambda args, kwargs: args[0])
    root = eyelid_guide()
    # break the symmetry under the right eye loop
    for vertex in eye_face["R"]["vertices"]:
        cmds.move(
            0, 0.05, 0, "{}.vtx[{}]".format(eye_face["mesh"], vertex), relative=True
        )
    guide.Rig().duplicate(pm.PyNode(root), True)
    assert cmds.getAttr("eyelid_R0_root.vertexLoop") == cmds.getAttr(
        root + ".vertexLoop"
    )
    assert any("no mirror" in str(message) for message in logs)


def _log_calls(count_calls):
    import mgear

    return count_calls(
        mgear,
        "log",
        lambda args, kwargs: str(args[0]) if len(args) > 1 else None,
    )


def test_missing_mesh_stops_build(eyelid_guide, count_calls):
    from maya import cmds

    logs = _log_calls(count_calls)
    root = eyelid_guide()
    cmds.setAttr(root + ".vertexLoop", "missing.vtx[1:4]", type="string")
    _build()
    # one clear error, no traceback, nothing built
    assert logs[0] == (
        "eyelid_L0: The eyelid mesh missing doesn't exist. Check the "
        "eyelid_01 component settings"
    )
    assert logs[1].startswith("Build stopped")
    assert not any("Traceback" in message for message in logs)
    assert not cmds.objExists("rig")


def test_loop_not_set_stops_build(eyelid_guide, count_calls):
    from maya import cmds

    logs = _log_calls(count_calls)
    root = eyelid_guide()
    cmds.setAttr(root + ".vertexLoop", "", type="string")
    _build()
    assert logs[0] == (
        "eyelid_L0: Set the eyelid vertex loop. Check the eyelid_01 component "
        "settings"
    )
    assert not cmds.objExists("rig")


def test_skip_when_option_off(eyelid_guide, count_calls):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    logs = _log_calls(count_calls)
    root = eyelid_guide()
    cmds.setAttr(root + ".vertexLoop", "", type="string")
    # another component in the same guide still builds
    guide.Rig().drawNewComponent(pm.PyNode("guide"), "control_01", showUI=False)
    cmds.setAttr("guide.stop_build_on_validation_fail", False)
    _build()
    assert logs == [
        "eyelid_L0: Set the eyelid vertex loop. Check the eyelid_01 component "
        "settings. The component is skipped"
    ]
    assert cmds.objExists("rig")
    assert cmds.objExists("control_C0_ctl")
    assert not cmds.objExists("eyelid_L0_upBlink_ctl")


def test_template_build_validates(eyelid_guide, count_calls):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import io

    root = eyelid_guide()
    cmds.setAttr(root + ".vertexLoop", "", type="string")
    conf = io.get_guide_template_dict(pm.PyNode("guide"))
    logs = _log_calls(count_calls)
    io.build_from_file(conf=conf)
    assert logs[0].startswith("eyelid_L0: Set the eyelid vertex loop")
    assert not cmds.objExists("eyelid_L0_upBlink_ctl")


def test_guide_without_the_option(eyelid_guide, count_calls):
    from maya import cmds

    # guides saved before the option still build, and stop by default
    eyelid_guide()
    cmds.deleteAttr("guide.stop_build_on_validation_fail")
    logs = _log_calls(count_calls)
    _build()
    assert cmds.objExists("eyelid_L0_upBlink_ctl")
    assert not any("Can't find parameter" in message for message in logs)


def test_guide_edits_without_loop(eye_face, rig_plugins, count_calls):
    import mgear
    import mgear.pymaya as pm
    from mgear.shifter import guide

    logs = count_calls(
        mgear,
        "log",
        lambda args, kwargs: str(args[0]) if len(args) > 1 else None,
    )
    guide.Rig().drawNewComponent(None, "eyelid_01", showUI=False)
    guide.Rig().updateProperties(pm.PyNode("eyelid_C0_root"), "eyelid", "L", 0)
    guide.Rig().duplicate(pm.PyNode("eyelid_L0_root"), True)
    assert logs == []


def test_autoskin(eyelid_guide, eye_face):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.core import skin
    from mgear.shifter import guide

    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    guide.Rig().updateProperties(pm.PyNode("control_C0_root"), "head", "C", 0)
    cmds.setAttr("head_C0_root.joint", True)
    eyelid_guide(parent="head_C0_root", doSkin=True)
    _build()
    skin_cluster = skin.getSkinCluster(eye_face["mesh"]).name()
    influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
    joints = _joints(cmds, "eyelid_L0_upEyelid*_jnt")
    for joint in joints:
        assert joint in influences
    vertex = eye_face["L"]["vertices"][0]
    weights = cmds.skinPercent(
        skin_cluster,
        "{}.vtx[{}]".format(eye_face["mesh"], vertex),
        query=True,
        value=True,
    )
    assert max(weights) == pytest.approx(1.0)


def test_no_autoskin(eyelid_guide, eye_face):
    from mgear.core import skin

    eyelid_guide()
    _build()
    assert skin.getSkinCluster(eye_face["mesh"]) is None


def test_joints_off(eyelid_guide):
    from maya import cmds

    eyelid_guide()
    cmds.setAttr("guide.joint_rig", False)
    _build()
    assert cmds.objExists("eyelid_L0_upBlink_ctl")
    assert len(cmds.ls("eyelid_L0_upEyelid*_jnt", type="joint")) == 11


def test_solved_once_per_build(eyelid_guide, count_calls):
    from mgear.core.facial import eyelid_solver

    # the build reuses the geometry the validation solved
    calls = count_calls(eyelid_solver, "solve")
    eyelid_guide()
    _build()
    assert len(calls) == 1
