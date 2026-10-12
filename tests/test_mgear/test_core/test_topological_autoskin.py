"""mgear.core.skin topological autoskin test"""

import pytest


@pytest.fixture
def cmds(run_with_maya_standalone, setup_path):
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


@pytest.fixture
def plane(cmds):
    """8x8 polyPlane, 81 vertices. The center vertex is 40."""
    return cmds.polyPlane(
        name="sheet",
        width=8,
        height=8,
        subdivisionsX=8,
        subdivisionsY=8,
        constructionHistory=False,
    )[0]


def _joint(cmds, name, x=0.0):
    cmds.select(clear=True)
    return cmds.joint(name=name, position=(x, 0, 0))


def _weights(cmds, skin_cluster, vertex):
    influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
    values = cmds.skinPercent(
        skin_cluster, "sheet.vtx[{}]".format(vertex), query=True, value=True
    )
    return dict(zip(influences, values))


def _legacy_profile(rigid_loops, falloff_loops):
    """The Eye Rigger 2.1 skinPercList, without its padding."""
    values = [1.0]
    for _ in range(rigid_loops):
        values += [1.0, 1.0]
    increment = 1.0 / float(falloff_loops)
    inv = 1.0 - increment
    for _ in range(falloff_loops):
        values += [max(inv, 0.0)] * 2
        inv -= increment
    return values


def test_profile_matches_eye_rigger_21(setup_path):
    from mgear.core import skin

    legacy = _legacy_profile(2, 4)
    # 2.1 listed every ring twice, one entry per side of the loop
    collapsed = [legacy[0]] + legacy[1::2]
    assert skin.compute_falloff_profile(2, 4) == pytest.approx(collapsed)
    assert skin.compute_falloff_profile(1, 2) == pytest.approx([1.0, 1.0, 0.5, 0.0])
    assert skin.compute_falloff_profile(0, 0) == [1.0]


def test_compute_weights(setup_path):
    from mgear.core import skin

    seed_map = {1: (0, 1), 2: (1, 1), 3: (2, 1), 4: (1, 9)}
    weights = skin.compute_topological_weights(
        seed_map, {1: "jnt"}, [1.0, 0.5, 0.0], "head"
    )
    assert weights == {
        1: {"jnt": 1.0},
        2: {"jnt": 0.5, "head": 0.5},
        3: {"head": 1.0},
    }
    weights = skin.compute_topological_weights(
        seed_map, {1: "jnt"}, [1.0, 0.5, 0.0], {1: "a", 3: "b"}
    )
    assert weights == {1: {"jnt": 1.0}, 3: {"b": 1.0}}


def test_seed_and_falloff(cmds, plane):
    from mgear.core import meshNavigation
    from mgear.core import skin

    root = _joint(cmds, "root")
    lid = _joint(cmds, "lid")
    skin_cluster = skin.apply_topological_autoskin(
        plane, [(lid, 40)], base_influence=root, rigid_loops=1, falloff_loops=2
    )
    assert skin_cluster == "sheet_skinCluster"
    rings = meshNavigation.get_concentric_vertex_rings(plane, [40], 4)
    expected = [1.0, 1.0, 0.5, 0.0]
    for ring, weight in zip(rings, expected):
        for vertex in ring:
            assert _weights(cmds, skin_cluster, vertex)["lid"] == pytest.approx(weight)
    for vertex in rings[4]:
        assert _weights(cmds, skin_cluster, vertex)["root"] == pytest.approx(1.0)
    for vertex in range(81):
        assert sum(_weights(cmds, skin_cluster, vertex).values()) == pytest.approx(1.0)


def test_dominant_influence(cmds, plane):
    from mgear.core import skin

    left = _joint(cmds, "left", 4)
    right = _joint(cmds, "right", -4)
    skin_cluster = cmds.skinCluster(
        [left, right], plane, toSelectedBones=True, name="existing"
    )[0]
    for vertex in range(81):
        x = cmds.pointPosition("sheet.vtx[{}]".format(vertex), world=True)[0]
        owner = left if x >= 0 else right
        cmds.skinPercent(
            skin_cluster, "sheet.vtx[{}]".format(vertex), transformValue=[(owner, 1)]
        )
    lid = _joint(cmds, "lid")
    # row of vertices along X through the center (36-44)
    row = list(range(36, 45))
    skin.apply_topological_autoskin(
        plane, [(lid, 40)], rigid_loops=0, falloff_loops=2, loop_vertices=row
    )
    # one ring off the row: half lid, half the side's own influence
    assert _weights(cmds, skin_cluster, 27) == pytest.approx(
        {"left": 0.0, "right": 0.5, "lid": 0.5}
    )
    assert _weights(cmds, skin_cluster, 35) == pytest.approx(
        {"left": 0.5, "right": 0.0, "lid": 0.5}
    )


def test_idempotent(cmds, plane):
    from mgear.core import skin

    root = _joint(cmds, "root")
    a = _joint(cmds, "a", -1)
    b = _joint(cmds, "b", 1)
    seeds = [(a, 39), (b, 41)]
    first = skin.apply_topological_autoskin(plane, seeds, root, 1, 2, "lid_skin")
    before = [_weights(cmds, first, v) for v in range(81)]
    second = skin.apply_topological_autoskin(plane, seeds, root, 1, 2, "lid_skin")
    assert second == first == "lid_skin"
    assert len(cmds.ls(type="skinCluster")) == 1
    after = [_weights(cmds, first, v) for v in range(81)]
    for b_weights, a_weights in zip(before, after):
        assert a_weights == pytest.approx(b_weights)


def test_no_cluster_no_base_raises(cmds, plane):
    from mgear.core import skin

    lid = _joint(cmds, "lid")
    with pytest.raises(ValueError):
        skin.apply_topological_autoskin(plane, [(lid, 40)])
