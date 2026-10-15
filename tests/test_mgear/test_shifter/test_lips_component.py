"""Shifter lips_01 component test"""

import math

import pytest


@pytest.fixture
def lips_guide(lips_face, rig_plugins):
    """Function drawing a lips_01 guide for the lips_face mouth.

    Returns:
        callable: Called with parent (guide locator, optional), aim (aim
            locator world position), lip (lip locator height above the
            root: the thickness) and guide settings. Returns the guide root
            name.
    """
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    def draw(parent=None, aim=(0, 0, 1.2), lip=0.03, **settings):
        before = set(cmds.ls("*_root", type="transform"))
        guide.Rig().drawNewComponent(
            pm.PyNode(parent) if parent else None, "lips_01", showUI=False
        )
        root = (set(cmds.ls("*_root", type="transform")) - before).pop()
        cmds.xform(root, worldSpace=True, translation=(0, 0, 0.75))
        cmds.xform(_aim(root), worldSpace=True, translation=aim)
        cmds.xform(
            root.replace("_root", "_lip"), worldSpace=True, translation=(0, lip, 0.75)
        )
        cmds.setAttr(root + ".vertexLoop", lips_face["vertex_loop"], type="string")
        for key, value in settings.items():
            if isinstance(value, str):
                cmds.setAttr("{}.{}".format(root, key), value, type="string")
            else:
                cmds.setAttr("{}.{}".format(root, key), value)
        return root

    return draw


def _aim(root):
    return root.replace("_root", "_aim")


def _draw_control(name, position):
    """Draw a control_01 guide with joints, named name_C0."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    parent = pm.PyNode("guide") if cmds.objExists("guide") else None
    guide.Rig().drawNewComponent(parent, "control_01", showUI=False)
    guide.Rig().updateProperties(pm.PyNode("control_C0_root"), name, "C", 0)
    root = "{}_C0_root".format(name)
    cmds.setAttr(root + ".joint", True)
    cmds.xform(root, worldSpace=True, translation=position)
    return root


def _build():
    from maya import cmds
    from mgear import shifter

    cmds.select("guide")
    rig = shifter.Rig()
    rig.buildFromSelection()
    cmds.select(clear=True)
    return rig


def _position(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def _joints(pattern):
    from maya import cmds

    return sorted(
        cmds.ls(pattern, type="joint"),
        key=lambda name: int("".join(c for c in name.split("_")[2] if c.isdigit())),
    )


def _ctl(name):
    return "lips_C0_{}_ctl".format(name)


def test_guide_params(lips_guide):
    from maya import cmds

    root = lips_guide()
    assert root == "lips_C0_root"
    assert cmds.objExists("lips_C0_aim")
    assert cmds.objExists("lips_C0_lip")
    for key in ("vertexLoop", "edgeLoop", "invertLips", "ropeCount", "jawRef"):
        assert cmds.attributeQuery(key, node=root, exists=True), key
    for key in ("namePrefix", "headJnt", "jawJnt", "upperRef", "thickness"):
        assert not cmds.attributeQuery(key, node=root, exists=True), key
    assert cmds.getAttr(root + ".doSkin") is False
    assert cmds.getAttr(root + ".loopType") == 1


def test_standard_build(lips_guide, lips_face):
    from maya import cmds
    from mgear.core import meshNavigation
    from mgear.core.facial import lips_solver
    from mgear.shifter_classic_components.lips_01 import guide

    head = _draw_control("head", (0, 0, 0))
    lips_guide(parent=head, lip=0.0)
    _build()
    assert len(cmds.ls("lips_C0_*_ctl", type="transform")) == 12
    upper = _joints("lips_C0_upLip*_jnt")
    lower = _joints("lips_C0_lowLip*_jnt")
    assert len(upper) == 11 and len(lower) == 9
    # lower joints hang from the same parent joint as the upper ones
    parents = set(cmds.listRelatives(j, parent=True)[0] for j in upper + lower)
    assert parents == {"head_C0_0_jnt"}
    _, geometry = guide.solve(
        {"vertexLoop": lips_face["vertex_loop"]},
        {"root": (0, 0, 0.75), "aim": (0, 0, 1.2), "lip": (0, 0, 0.75)},
    )
    points = meshNavigation.get_vertex_world_positions(
        lips_face["mesh"], geometry.upper
    )
    for joint, point in zip(upper, points):
        assert math.dist(_position(joint), point) < 1e-3
    # the corners follow the parent
    rest = _position(_ctl("corner_L"))
    cmds.setAttr("head_C0_ctl.ty", 0.5)
    assert _position(_ctl("corner_L"))[1] == pytest.approx(rest[1] + 0.5, abs=1e-4)
    assert isinstance(geometry, lips_solver.LipsGeometry)


def test_lower_ref(lips_guide):
    from maya import cmds

    head = _draw_control("head", (0, 0, 0))
    _draw_control("jaw", (0, 0, 0))
    lips_guide(parent=head, jawRef="jaw_C0_root")
    _build()
    rest = {name: _position(_ctl(name)) for name in ("upper", "lower", "corner_L")}
    cmds.setAttr("jaw_C0_ctl.rx", 20)
    assert _position(_ctl("upper")) == pytest.approx(rest["upper"], abs=1e-5)
    assert math.dist(_position(_ctl("lower")), rest["lower"]) > 0.05
    corner = math.dist(_position(_ctl("corner_L")), rest["corner_L"])
    assert corner > 0.01
    cmds.setAttr(_ctl("corner_L") + ".jawFollow", 0)
    assert _position(_ctl("corner_L")) == pytest.approx(rest["corner_L"], abs=1e-5)


def test_mouth_connector(lips_guide):
    from maya import cmds

    from mgear.shifter import guide

    guide.Rig().drawNewComponent(None, "mouth_01", showUI=False)
    root = lips_guide(parent="mouth_C0_root")
    assert cmds.getAttr(root + ".connector") == "mouth_01"
    _build()
    rig_root = [r for r in cmds.ls("lips_C0_root", long=True) if "guide" not in r][0]
    assert "mouth_C0_root" in rig_root
    rest = {name: _position(_ctl(name)) for name in ("upper", "lower", "corner_L")}
    lower_lip = _position("mouth_C0_liplow_ctl")
    # the mouth jaw control opens the jaw with ty
    cmds.setAttr("mouth_C0_jaw_ctl.ty", -0.5)
    moved = [_position("mouth_C0_liplow_ctl")[i] - lower_lip[i] for i in range(3)]
    assert math.dist(moved, (0, 0, 0)) > 0.01
    # the mouth lipup control follows the jaw a little, liplow all the way
    upper = math.dist(_position(_ctl("upper")), rest["upper"])
    lower = math.dist(_position(_ctl("lower")), rest["lower"])
    assert lower > 0.01
    assert upper < lower * 0.5
    corner = math.dist(_position(_ctl("corner_L")), rest["corner_L"])
    cmds.setAttr(_ctl("corner_L") + ".jawFollow", 1)
    assert math.dist(_position(_ctl("corner_L")), rest["corner_L"]) > corner


def test_mouth_connector_without_mouth(lips_guide, count_calls):
    from maya import cmds

    import mgear.pymaya as pm

    warnings = count_calls(pm, "displayWarning", lambda args, kwargs: args[0])
    head = _draw_control("head", (0, 0, 0))
    root = lips_guide(parent=head)
    cmds.setAttr(root + ".connector", "mouth_01", type="string")
    _build()
    assert cmds.objExists(_ctl("upper"))
    assert any("mouth_01 connector" in warning for warning in warnings)


def test_tilted_guide(lips_guide):
    from maya import cmds

    angle = math.radians(30)
    aim = (0, 0.45 * math.sin(angle), 0.75 + 0.45 * math.cos(angle))
    lips_guide(aim=aim)
    _build()
    m = cmds.xform(_ctl("upper"), query=True, worldSpace=True, matrix=True)
    z_axis = m[8:11]
    length = math.sqrt(sum(v * v for v in z_axis))
    direction = [(aim[i] - (0, 0, 0.75)[i]) / 0.45 for i in range(3)]
    assert [v / length for v in z_axis] == pytest.approx(direction, abs=1e-3)
    assert _position(_ctl("corner_L"))[0] > 0.5
    assert _position(_ctl("corner_R"))[0] < -0.5


def test_loop_not_set_skips(lips_guide, count_calls):
    from maya import cmds

    import mgear

    logs = count_calls(
        mgear,
        "log",
        lambda args, kwargs: str(args[0]) if len(args) > 1 else None,
    )
    head = _draw_control("head", (0, 0, 0))
    root = lips_guide(parent=head)
    cmds.setAttr(root + ".vertexLoop", "", type="string")
    cmds.setAttr("guide.stop_build_on_validation_fail", False)
    _build()
    assert logs == [
        "lips_C0: Set the lips vertex loop. Check the lips_01 component "
        "settings. The component is skipped"
    ]
    assert cmds.objExists("head_C0_ctl")
    assert not cmds.objExists(_ctl("upper"))


def test_invert_lips(lips_guide):
    lips_guide(invertLips=True)
    _build()
    assert _position(_ctl("upper"))[1] < 0
    assert _position(_ctl("lower"))[1] > 0


def test_center_symmetrize_keeps_loop(lips_guide):
    from mgear.shifter import guide

    root = lips_guide()
    component = guide.Rig()
    component.setFromHierarchy(__import__("mgear.pymaya", fromlist=["x"]).PyNode(root))
    lips = component.components["lips_C0"]
    loop = lips.values["vertexLoop"]
    assert lips.symmetrize() is False
    assert lips.values["vertexLoop"] == loop


def test_mirror_ready_names(lips_guide):
    from maya import cmds
    from mgear.core import string

    lips_guide()
    _build()
    controls = cmds.ls("lips_C0_*_ctl", type="transform")
    left = [c for c in controls if "_L_" in c]
    assert len(left) == 5
    for ctl in left:
        assert string.convertRLName(ctl) in controls
    plugs = [
        "{}.{}".format(node, attr)
        for node in cmds.ls(type="transform")
        for attr in cmds.listAttr(node, userDefined=True) or []
        if attr.endswith("secondaryVis")
    ]
    assert len(plugs) == 1
    assert plugs[0].startswith("world_ctl.") or plugs[0].split(".")[0].endswith("_ctl")
    cmds.setAttr(plugs[0], False)
    shape = cmds.listRelatives(_ctl("upOuter_L"), shapes=True)[0]
    assert not cmds.getAttr(shape + ".visibility")


def test_autoskin(lips_guide, lips_face):
    from maya import cmds
    from mgear.core import skin

    head = _draw_control("head", (0, 0, 0))
    lips_guide(parent=head, doSkin=True)
    _build()
    cluster = skin.getSkinCluster(lips_face["mesh"]).name()
    influences = cmds.skinCluster(cluster, query=True, influence=True)
    for joint in _joints("lips_C0_upLip*_jnt") + _joints("lips_C0_lowLip*_jnt"):
        assert joint in influences
    assert "head_C0_0_jnt" in influences


def test_no_autoskin(lips_guide, lips_face):
    from mgear.core import skin

    lips_guide()
    _build()
    assert skin.getSkinCluster(lips_face["mesh"]) is None


def test_joints_off(lips_guide):
    from maya import cmds

    lips_guide(doSkin=True)
    cmds.setAttr("guide.joint_rig", False)
    _build()
    assert cmds.objExists(_ctl("upper"))
    assert len(cmds.ls("lips_C0_upLip*_jnt", type="joint")) == 11


def test_solved_once_per_build(lips_guide, count_calls):
    from mgear.core.facial import lips_solver

    calls = count_calls(lips_solver, "solve")
    lips_guide()
    _build()
    assert len(calls) == 1


def test_global_scale(lips_guide):
    from maya import cmds

    head = _draw_control("head", (0, 0, 0))
    lips_guide(parent=head)
    _build()
    joints = _joints("lips_C0_upLip*_jnt") + _joints("lips_C0_lowLip*_jnt")
    rest = {joint: _position(joint) for joint in joints}
    for axis in "xyz":
        cmds.setAttr("global_C0_ctl.s" + axis, 2)
    for joint, position in rest.items():
        assert _position(joint) == pytest.approx([v * 2 for v in position], abs=1e-3)


def test_thickness_from_lip_locator(lips_guide, lips_face):
    from mgear.core.facial import lips_solver
    from mgear.shifter_classic_components.lips_01 import guide

    settings, geometry = guide.solve(
        {"vertexLoop": lips_face["vertex_loop"]},
        {"root": (0, 0, 0.75), "aim": (0, 0, 1.2), "lip": (0, -0.08, 0.75)},
    )
    assert settings["thickness"] == pytest.approx(0.08)
    mid = len(geometry.upper) // 2
    moved = geometry.upper_curve_points[mid][1] - geometry.upper_points[mid][1]
    assert moved == pytest.approx(0.08, abs=1e-6)
    assert isinstance(geometry, lips_solver.LipsGeometry)


def test_joints_translate_only(lips_guide):
    from maya import cmds

    head = _draw_control("head", (0, 0, 0))
    root = lips_guide(parent=head)
    assert cmds.getAttr(root + ".jointsFollowCurve") is True
    cmds.setAttr(root + ".jointsFollowCurve", False)
    _build()
    assert not cmds.ls("lips_C0_*LipUpv*", type="transform")
    upper = _joints("lips_C0_upLip*_jnt")
    joint = upper[len(upper) // 2 - 2]
    rest = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
    rest_position = _position(joint)
    cmds.setAttr(_ctl("upper") + ".ty", 0.1)
    now = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
    assert now[:11] == pytest.approx(rest[:11], abs=1e-4)
    assert _position(joint)[1] > rest_position[1] + 0.02


def test_squash_stretch(lips_guide):
    from maya import cmds

    head = _draw_control("head", (0, 0, 0))
    lips_guide(parent=head, squashStretch=True)
    _build()
    upper = _joints("lips_C0_upLip*_jnt")
    mid = upper[len(upper) // 2]
    for name in ("corner_R", "corner_L"):
        cmds.setAttr(_ctl(name) + ".tx", 0.3)
    scale = cmds.xform(mid, query=True, worldSpace=True, scale=True)
    assert scale[1] < 0.95
    cmds.setAttr(_ctl("upper") + ".squashStretch", 0)
    scale = cmds.xform(mid, query=True, worldSpace=True, scale=True)
    assert scale == pytest.approx([1, 1, 1], abs=1e-3)
