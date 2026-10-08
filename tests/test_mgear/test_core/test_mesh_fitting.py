"""mgear.core mesh fitting, radius measuring, skin influence and proxy test"""

import math

import pytest


@pytest.fixture
def cmds(run_with_maya_standalone, setup_path):
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


def _sphere_points(radius, count=100):
    from mgear.core import mesh

    return [tuple(c * radius for c in d) for d in mesh.sphere_directions(count)]


def test_percentile(setup_path):
    from mgear.core import mesh

    assert mesh.percentile([], 50) is None
    assert mesh.percentile([3, 1, 2], 50) == 2
    assert mesh.percentile([0, 10], 25) == pytest.approx(2.5)


def test_fit_sphere_ignores_outlier(setup_path):
    from mgear.core import mesh

    points = _sphere_points(1.0) + [(10.0, 0.0, 0.0)]
    center, radius = mesh.fit_sphere_to_points(points, 75)
    assert radius == pytest.approx(1.0, rel=0.05)
    assert all(abs(c) < 0.1 for c in center)


def test_fit_capsule_tapered(setup_path):
    from mgear.core import mesh

    # cone along X from radius 2 at x=0 to radius 1 at x=10
    points = []
    for step in range(21):
        x = step * 0.5
        radius = 2.0 - x / 10.0
        for index in range(12):
            angle = 2 * math.pi * index / 12
            points.append((x, radius * math.cos(angle), radius * math.sin(angle)))
    start, end = mesh.fit_capsule_to_points(points, (0, 0, 0), (10, 0, 0), 75, 0.1)
    assert start == pytest.approx(2.0, rel=0.05)
    # the 75th percentile leans to the thick side of the slab on a cone
    assert end == pytest.approx(1.0, rel=0.15)
    assert mesh.fit_capsule_to_points(points, (0, 0, 0), (0, 0, 0)) == (None, None)


def test_measure_radius_along_segment(cmds):
    from mgear.core import mesh

    cylinder = cmds.polyCylinder(
        radius=2, height=10, subdivisionsAxis=32, constructionHistory=False
    )[0]
    radii = mesh.measure_radius_along_segment(cylinder, (0, -4, 0), (0, 4, 0), 5, 8)
    assert len(radii) == 5
    for radius in radii:
        assert radius == pytest.approx(2.0, rel=0.05)


def test_measure_radius_around_point(cmds):
    from mgear.core import mesh

    sphere = cmds.polySphere(
        radius=3,
        subdivisionsAxis=32,
        subdivisionsHeight=32,
        constructionHistory=False,
    )[0]
    cmds.move(1, 2, 3, sphere)
    radius = mesh.measure_radius_around_point(sphere, (1, 2, 3), 26)
    assert radius == pytest.approx(3.0, rel=0.05)
    assert mesh.measure_radius_around_point(sphere, (50, 0, 0), 26) is None


def test_dominant_influence_vertices(cmds):
    from mgear.core import skin

    cylinder = cmds.polyCylinder(
        radius=1,
        height=10,
        subdivisionsHeight=10,
        subdivisionsAxis=8,
        constructionHistory=False,
    )[0]
    cmds.select(clear=True)
    low = cmds.joint(name="low_jnt", position=(0, -5, 0))
    high = cmds.joint(name="high_jnt", position=(0, 5, 0))
    cluster = cmds.skinCluster([low, high], cylinder, toSelectedBones=True)[0]
    positions = cmds.xform(cylinder + ".vtx[*]", query=True, translation=True)
    count = len(positions) // 3
    for index in range(count):
        y = positions[index * 3 + 1]
        cmds.skinPercent(
            cluster,
            "{}.vtx[{}]".format(cylinder, index),
            transformValue=[
                (low, 1.0 if y < 0 else 0.0),
                (high, 0.0 if y < 0 else 1.0),
            ],
        )
    result = skin.get_dominant_influence_vertices(cylinder, [low, high])
    assert set(result) == {low, high}
    assert all(positions[i * 3 + 1] < 0 for i in result[low])
    assert all(positions[i * 3 + 1] >= 0 for i in result[high])
    assert len(result[low]) + len(result[high]) == count
    assert skin.get_dominant_influence_vertices(low) == {}


def test_create_collision_proxy(cmds):
    from mgear.core import mesh

    sphere = cmds.polySphere(
        subdivisionsAxis=40, subdivisionsHeight=25, constructionHistory=False
    )[0]
    faces = cmds.polyEvaluate(sphere, face=True)
    proxy = mesh.create_collision_proxy(sphere, reduce_percent=50, follow=True)
    assert cmds.polyEvaluate(proxy, face=True) == pytest.approx(faces / 2, rel=0.2)
    assert cmds.polyEvaluate(sphere, face=True) == faces
    assert cmds.ls(cmds.listHistory(proxy), type="proximityWrap")
    assert not cmds.ls(cmds.listHistory(sphere), type="proximityWrap")
    fn = mesh.get_mesh_fn(proxy)
    assert all(fn.isEdgeSmooth(edge) for edge in range(fn.numEdges))
    cmds.move(0, 5, 0, sphere + ".vtx[*]", relative=True)
    proxy_y = cmds.xform(
        proxy + ".vtx[0]", query=True, translation=True, worldSpace=True
    )
    assert proxy_y[1] > 3.0
