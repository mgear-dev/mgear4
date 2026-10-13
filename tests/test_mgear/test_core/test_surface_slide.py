"""mgear.core.applyop surface_slide test"""

import math

import pytest


@pytest.fixture
def sphere_slide(setup_path):
    """A sphere surface of radius 1 and a driver 0.2 above its +Z side.

    Returns:
        dict: "surface", "driver", "slider" and "offset" (offset plug).
    """
    from maya import cmds
    from mgear.core import applyop

    cmds.file(new=True, force=True)
    surface = cmds.sphere(radius=1, axis=(0, 1, 0), constructionHistory=False)[0]
    driver = cmds.createNode("transform", name="driver")
    cmds.setAttr(driver + ".translate", 0, 0, 1.2)
    slider = cmds.createNode("transform", name="slider")
    cmds.addAttr(driver, longName="offset", attributeType="double")
    applyop.surface_slide(driver, slider, surface, driver + ".offset")
    return {
        "surface": surface,
        "driver": driver,
        "slider": slider,
        "offset": driver + ".offset",
    }


def _position(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def _surface_distance(slide, node):
    """Distance of a node to the surface along the surface normal."""
    from mgear.core import surface

    position = _position(node)
    point, normal, _, _ = surface.get_closest_point_normal(slide["surface"], position)
    return sum((position[i] - point[i]) * normal[i] for i in range(3)), normal


def test_rest_on_driver(sphere_slide):
    from maya import cmds

    assert _position(sphere_slide["slider"]) == pytest.approx([0, 0, 1.2], abs=1e-4)
    assert cmds.getAttr(sphere_slide["slider"] + ".restDistance") == pytest.approx(
        0.2, abs=1e-4
    )


def test_slides_at_rest_distance(sphere_slide):
    from maya import cmds

    # the driver moves sideways in a straight line: the slider stays 0.2
    # from the sphere
    cmds.setAttr(sphere_slide["driver"] + ".translate", 0.6, 0.3, 1.2)
    distance, _ = _surface_distance(sphere_slide, sphere_slide["slider"])
    assert distance == pytest.approx(0.2, abs=1e-4)
    # the slider is on the sphere side of the driver, not at the driver
    radius = math.sqrt(sum(v * v for v in _position(sphere_slide["slider"])))
    assert radius == pytest.approx(1.2, abs=0.01)


def test_offset(sphere_slide):
    from maya import cmds

    cmds.setAttr(sphere_slide["offset"], 0.1)
    distance, _ = _surface_distance(sphere_slide, sphere_slide["slider"])
    assert distance == pytest.approx(0.3, abs=1e-4)


def test_orientation(sphere_slide):
    from maya import cmds

    cmds.setAttr(sphere_slide["driver"] + ".translate", 0.6, 0, 1.2)
    m = cmds.xform(sphere_slide["slider"], query=True, worldSpace=True, matrix=True)
    _, normal = _surface_distance(sphere_slide, sphere_slide["slider"])
    # Z on the surface normal, Y toward the driver Y (world up)
    assert [abs(v) for v in m[8:11]] == pytest.approx(
        [abs(v) for v in normal], abs=1e-4
    )
    assert m[5] == pytest.approx(1.0, abs=1e-3)
    assert not cmds.ls(type=("normalConstraint", "aimConstraint"))


def test_surface_distance(sphere_slide):
    from maya import cmds
    from mgear.core import applyop

    plug = applyop.surface_distance(sphere_slide["driver"], sphere_slide["surface"])
    assert cmds.getAttr(plug) == pytest.approx(0.2, abs=1e-3)
    cmds.setAttr(sphere_slide["driver"] + ".translateZ", 1.5)
    assert cmds.getAttr(plug) == pytest.approx(0.5, abs=1e-3)
