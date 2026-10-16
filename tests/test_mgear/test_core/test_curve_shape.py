"""mgear.core.curve.add_curve_shape tests"""

import pytest

POINTS = (
    [0.0, 0.0, -1.0],
    [0.7, 0.2, -0.7],
    [1.0, 0.0, 0.0],
    [0.7, -0.3, 0.7],
    [0.0, 0.0, 1.0],
    [-0.7, 0.1, 0.7],
    [-1.0, 0.0, 0.0],
    [-0.7, 0.0, -0.7],
)


@pytest.fixture
def curve_scene(setup_path):
    """New scene; returns the mgear.core.curve module."""
    from maya import cmds

    from mgear.core import curve

    cmds.file(new=True, force=True)
    return curve


@pytest.mark.parametrize(
    "count, close, degree",
    [
        (2, False, 1),
        (8, False, 1),
        (8, False, 3),
        (5, False, 3),
        (4, True, 1),
        (8, True, 3),
    ],
)
def test_add_curve_shape_matches_add_curve(
    curve_scene, describe_shapes, count, close, degree
):
    from maya import cmds

    curve = curve_scene
    points = [list(p) for p in POINTS[:count]]
    reference = curve.addCurve(None, "ref", list(points), close, degree, m=None)
    target = cmds.createNode("transform", name="target")
    before = set(cmds.ls(type="transform"))

    shape = curve.add_curve_shape(
        target, list(points), close, degree, name="targetShape"
    )

    assert shape.split("|")[-1] == "targetShape"
    assert set(cmds.ls(type="transform")) == before
    expected = describe_shapes(str(reference), names=False)
    assert describe_shapes(target, names=False) == expected


def test_add_curve_shape_vectors_and_pynode_parent(curve_scene, describe_shapes):
    import mgear.pymaya as pm
    from mgear.pymaya import datatypes

    curve = curve_scene
    target = pm.PyNode(pm.createNode("transform", name="target"))
    points = [datatypes.Vector(p) for p in POINTS]
    curve.add_curve_shape(target, points, True, 3)
    reference = curve.addCurve(None, "ref", [list(p) for p in POINTS], True, 3, m=None)

    assert describe_shapes("target", names=False) == describe_shapes(
        str(reference), names=False
    )


def test_add_curve_shape_undo(curve_scene):
    from maya import cmds

    curve = curve_scene
    cmds.undoInfo(state=True)
    target = cmds.createNode("transform", name="target")
    cmds.undoInfo(openChunk=True)
    try:
        curve.add_curve_shape(target, [list(p) for p in POINTS], True, 3)
    finally:
        cmds.undoInfo(closeChunk=True)
    assert len(cmds.listRelatives(target, shapes=True)) == 1

    cmds.undo()
    assert not cmds.listRelatives(target, shapes=True)
    cmds.redo()
    assert len(cmds.listRelatives(target, shapes=True)) == 1
