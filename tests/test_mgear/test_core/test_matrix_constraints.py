"""mgear.core.applyop matrix constraints test"""

import pytest


@pytest.fixture
def cmds(run_with_maya_standalone, setup_path):
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


def _world_position(cmds, node):
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def test_follow_with_offset(cmds):
    from mgear.core import applyop

    driver = cmds.createNode("transform", name="driver")
    parent = cmds.createNode("transform", name="parent")
    cmds.setAttr(parent + ".translate", 0, 3, 0)
    cmds.setAttr(parent + ".rotateY", 45)
    driven = cmds.createNode("transform", name="driven", parent=parent)
    cmds.xform(driven, worldSpace=True, translation=(1, 2, 3))
    applyop.matrix_constraint(driver, driven, "srt", offset=True)
    assert _world_position(cmds, driven) == pytest.approx([1, 2, 3], abs=1e-5)
    cmds.setAttr(driver + ".translateX", 1)
    assert _world_position(cmds, driven) == pytest.approx([2, 2, 3], abs=1e-5)


def test_translate_only(cmds):
    from mgear.core import applyop

    driver = cmds.createNode("transform", name="driver")
    driven = cmds.createNode("transform", name="driven")
    applyop.matrix_constraint(driver, driven, "t")
    cmds.setAttr(driver + ".rotateZ", 30)
    cmds.setAttr(driver + ".translateY", 2)
    assert cmds.getAttr(driven + ".rotateZ") == pytest.approx(0)
    assert cmds.getAttr(driven + ".translateY") == pytest.approx(2)


def test_blend_with_host_weights(cmds):
    from mgear.core import applyop

    a = cmds.createNode("transform", name="a")
    b = cmds.createNode("transform", name="b")
    cmds.setAttr(b + ".translateX", 2)
    host = cmds.createNode("transform", name="host")
    driven = cmds.createNode("transform", name="driven")
    applyop.matrix_blend_constraint([a, b], driven, [0.5, 0.5], "t", host=host)
    assert cmds.getAttr(driven + ".translateX") == pytest.approx(1)
    cmds.setAttr(host + ".b_weight", 1.0)
    cmds.setAttr(host + ".a_weight", 0.0)
    assert cmds.getAttr(driven + ".translateX") == pytest.approx(2)
    with pytest.raises(ValueError):
        applyop.matrix_blend_constraint([a, b], driven, [1.0])


def test_legacy_names(cmds):
    import mgear.pymaya as pm
    from mgear.rigbits.facial_rigger import constraints

    parent = pm.PyNode(cmds.createNode("transform", name="parent"))
    child = pm.PyNode(cmds.createNode("transform", name="child"))
    cmds.setAttr("child.translateX", 1)
    constraints.matrixConstraint(parent, child, "srt", True)
    cmds.setAttr("parent.translateY", 1)
    assert _world_position(cmds, "child") == pytest.approx([1, 1, 0], abs=1e-5)

    other = pm.PyNode(cmds.createNode("transform", name="other"))
    host = pm.PyNode(cmds.createNode("transform", name="host"))
    out = pm.PyNode(cmds.createNode("transform", name="out"))
    constraints.matrixBlendConstraint([parent, other], out, [0.5, 0.5], "t", host=host)
    assert cmds.attributeQuery("pCns_C_parent_wtWeight", node="host", exists=True)
    assert cmds.getAttr("out.translateY") == pytest.approx(0.5)
