"""Shifter brow_01 component test"""

import pytest

# guide root and aim of each brow of the brow_face fixture
GUIDE_POSITIONS = {
    "L": ((0.5, 0.3, 0.95), (0.5, 0.3, 1.5)),
    "R": ((-0.5, 0.3, 0.95), (-0.5, 0.3, 1.5)),
    "C": ((0.0, 0.3, 1.0), (0.0, 0.3, 1.5)),
}


@pytest.fixture
def brow_guide(brow_face, rig_plugins):
    """Function drawing a brow_01 guide for a brow_face brow.

    Returns:
        callable: Called with side ("L", "R" or "C"), parent (guide locator,
            optional) and guide settings. Returns the guide root name.
    """
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    def draw(side="L", parent=None, **settings):
        before = set(cmds.ls("*_root", type="transform"))
        guide.Rig().drawNewComponent(
            pm.PyNode(parent) if parent else None, "brow_01", showUI=False
        )
        root = (set(cmds.ls("*_root", type="transform")) - before).pop()
        if cmds.getAttr(root + ".comp_side") != side:
            guide.Rig().updateProperties(pm.PyNode(root), "brow", side, 0)
            root = "brow_{}0_root".format(side)
        position, aim = GUIDE_POSITIONS[side]
        cmds.xform(root, worldSpace=True, translation=position)
        cmds.xform(root.replace("_root", "_aim"), worldSpace=True, translation=aim)
        cmds.setAttr(
            root + ".vertexLoop", brow_face[side]["vertex_loop"], type="string"
        )
        for key, value in settings.items():
            if isinstance(value, str):
                cmds.setAttr("{}.{}".format(root, key), value, type="string")
            else:
                cmds.setAttr("{}.{}".format(root, key), value)
        return root

    return draw


def _head():
    """Draw a control_01 head guide with a joint."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    guide.Rig().updateProperties(pm.PyNode("control_C0_root"), "head", "C", 0)
    cmds.setAttr("head_C0_root.joint", True)
    return "head_C0_root"


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


def _joints(side="L"):
    from maya import cmds

    return sorted(
        cmds.ls("brow_{}0_brow*_jnt".format(side), type="joint"),
        key=lambda name: int("".join(c for c in name.split("_")[2] if c.isdigit())),
    )


def _log_calls(count_calls):
    import mgear

    return count_calls(
        mgear,
        "log",
        lambda args, kwargs: str(args[0]) if len(args) > 1 else None,
    )


def test_guide_params(brow_guide):
    from maya import cmds

    root = brow_guide()
    assert root == "brow_L0_root"
    assert cmds.objExists("brow_L0_aim")
    for key in ("vertexLoop", "mainControls", "slideSurface", "leftBrow", "rightBrow"):
        assert cmds.attributeQuery(key, node=root, exists=True), key
    for key in ("namePrefix", "side", "headJnt", "hookLeft", "frontNode"):
        assert not cmds.attributeQuery(key, node=root, exists=True), key
    assert cmds.getAttr(root + ".doSkin") is False


def test_left_brow_build(brow_guide, brow_face):
    from maya import cmds

    brow_guide(parent=_head())
    _build()
    for name in ("brow", "in", "mid01", "out", "in_tangent", "out_tangent", "sec00"):
        assert cmds.objExists("brow_L0_{}_ctl".format(name)), name
    joints = _joints()
    assert len(joints) == 7
    parents = set(cmds.listRelatives(j, parent=True)[0] for j in joints)
    assert parents == {"head_C0_0_jnt"}
    rest = _position(joints[3])
    cmds.setAttr("head_C0_ctl.ty", 0.5)
    assert _position(joints[3])[1] == pytest.approx(rest[1] + 0.5, abs=1e-3)


def test_three_brows(brow_guide):
    from maya import cmds

    head = _head()
    brow_guide("L", parent=head)
    brow_guide("R", parent=head)
    brow_guide("C", parent=head, leftBrow="brow_L0_root", rightBrow="brow_R0_root")
    _build()
    assert not cmds.objExists("brow_C0_out_L_ctl")
    center = _joints("C")
    rest_left = _position(center[-1])
    rest_right = _position(center[0])
    cmds.setAttr("brow_L0_in_ctl.ty", 0.1)
    assert _position(center[-1])[1] == pytest.approx(rest_left[1] + 0.1, abs=1e-3)
    assert _position(center[0]) == pytest.approx(rest_right, abs=1e-4)


def test_wrong_hook(brow_guide, count_calls):
    from maya import cmds

    logs = _log_calls(count_calls)
    head = _head()
    brow_guide("C", parent=head, leftBrow="head_C0_root", rightBrow="head_C0_root")
    cmds.setAttr("guide.stop_build_on_validation_fail", False)
    _build()
    assert logs and "leftBrow head_C0_root is not a brow_01 guide root" in logs[0]
    assert cmds.objExists("head_C0_ctl")
    assert not cmds.objExists("brow_C0_brow_ctl")


def test_symmetrize(brow_guide):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.core import meshNavigation
    from mgear.shifter import guide

    root = brow_guide("L", parent=_head())
    guide.Rig().duplicate(pm.PyNode(root), True)
    left = cmds.getAttr("brow_L0_root.vertexLoop")
    assert cmds.getAttr("brow_R0_root.vertexLoop") == (
        meshNavigation.mirror_component_string(left)[0]
    )
    _build()
    for l_joint, r_joint in zip(_joints("L"), _joints("R")):
        x, y, z = _position(l_joint)
        assert _position(r_joint) == pytest.approx([-x, y, z], abs=1e-3)


def test_slide_surface(brow_guide, brow_face):
    from maya import cmds

    brow_guide(parent=_head(), slideSurface=brow_face["surface"])
    _build()
    assert cmds.attributeQuery("surfaceOffset", node="brow_L0_mid01_ctl", exists=True)
    assert cmds.ls(type="closestPointOnSurface")
    joints = _joints()
    rest = _position(joints[3])
    cmds.setAttr("brow_L0_mid01_ctl.surfaceOffset", 0.1)
    assert _position(joints[3])[2] > rest[2] + 0.02


def test_joints_off(brow_guide):
    from maya import cmds

    brow_guide(doSkin=True)
    cmds.setAttr("guide.joint_rig", False)
    _build()
    assert cmds.objExists("brow_L0_brow_ctl")
    assert len(cmds.ls("brow_L0_brow*_jnt", type="joint")) == 7


def test_autoskin(brow_guide, brow_face):
    from maya import cmds
    from mgear.core import skin

    brow_guide(parent=_head(), doSkin=True)
    _build()
    cluster = skin.getSkinCluster(brow_face["mesh"]).name()
    influences = cmds.skinCluster(cluster, query=True, influence=True)
    for joint in _joints():
        assert joint in influences


def test_autoskin_off(brow_guide, brow_face):
    from maya import cmds
    from mgear.core import skin

    # the guide switch turns off every component autoskin
    brow_guide(parent=_head(), doSkin=True)
    cmds.setAttr("guide.autoskin", False)
    _build()
    assert skin.getSkinCluster(brow_face["mesh"]) is None
    assert len(_joints()) == 7


def test_guide_without_autoskin_option(brow_guide, brow_face, count_calls):
    from maya import cmds
    from mgear.core import skin

    # guides saved before the option still skin
    logs = _log_calls(count_calls)
    brow_guide(parent=_head(), doSkin=True)
    cmds.deleteAttr("guide.autoskin")
    _build()
    assert skin.getSkinCluster(brow_face["mesh"]) is not None
    assert not any("Can't find parameter" in message for message in logs)
