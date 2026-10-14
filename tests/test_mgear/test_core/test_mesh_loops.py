"""mgear.core.meshNavigation ordered loops, mirror indices and rings test"""

import pytest


@pytest.fixture
def cmds(run_with_maya_standalone, setup_path):
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


@pytest.fixture
def sphere(cmds):
    """20x20 polySphere. Its equator ring is vertices 180-199."""
    return cmds.polySphere(
        name="ball",
        subdivisionsAxis=20,
        subdivisionsHeight=20,
        constructionHistory=False,
    )[0]


def _edges_of(cmds, mesh, vertices):
    edges = cmds.ls(
        cmds.polyListComponentConversion(
            ["{}.vtx[{}]".format(mesh, v) for v in vertices],
            toEdge=True,
            internal=True,
        ),
        flatten=True,
    )
    return [int(e.split("[")[1][:-1]) for e in edges]


def _is_linked_path(cmds, mesh, ordered, closed):
    from mgear.core import meshNavigation

    neighbours = meshNavigation._vertex_neighbours(mesh, ordered)
    pairs = list(zip(ordered, ordered[1:]))
    if closed:
        pairs.append((ordered[-1], ordered[0]))
    return all(b in neighbours[a] for a, b in pairs)


def _same_cycle(a, b):
    if sorted(a) != sorted(b):
        return False
    start = b.index(a[0])
    rotated = b[start:] + b[:start]
    return rotated == a or [rotated[0]] + rotated[1:][::-1] == a


def test_parse_legacy_string(setup_path):
    from mgear.core import meshNavigation

    result = meshNavigation.parse_component_string(
        "head.e[10],head.e[11],head.e[12:14]"
    )
    assert result == ("head", "edge", [10, 11, 12, 13, 14])
    assert meshNavigation.parse_component_string("") == (None, None, [])


def test_component_string_round_trip(setup_path):
    from mgear.core import meshNavigation

    text = meshNavigation.format_component_string("m", "vertex", [7, 1, 2, 3, 9])
    assert text == "m.vtx[1:3],m.vtx[7],m.vtx[9]"
    assert meshNavigation.parse_component_string(text) == (
        "m",
        "vertex",
        [1, 2, 3, 7, 9],
    )


@pytest.mark.parametrize("text", ["a.e[1],b.e[2]", "a.e[1],a.vtx[2]", "a.f[1]", "a"])
def test_parse_rejects_bad_strings(setup_path, text):
    from mgear.core import meshNavigation

    with pytest.raises(ValueError):
        meshNavigation.parse_component_string(text)


def test_closed_loop_from_edges(cmds, sphere):
    from mgear.core import meshNavigation

    ring = list(range(180, 200))
    ordered, closed = meshNavigation.get_ordered_loop(
        sphere, _edges_of(cmds, sphere, ring), "edge"
    )
    assert closed
    assert sorted(ordered) == ring
    assert _is_linked_path(cmds, sphere, ordered, True)


def test_vertex_input_matches_edge_input(cmds, sphere):
    from mgear.core import meshNavigation

    ring = list(range(180, 200))
    from_edges, _ = meshNavigation.get_ordered_loop(
        sphere, _edges_of(cmds, sphere, ring), "edge"
    )
    from_vertices, closed = meshNavigation.get_ordered_loop(sphere, ring, "vertex")
    assert closed
    assert _same_cycle(from_edges, from_vertices)


def test_open_path(cmds):
    from mgear.core import meshNavigation

    plane = cmds.polyPlane(
        name="sheet",
        subdivisionsX=10,
        subdivisionsY=4,
        constructionHistory=False,
    )[0]
    row = list(range(11, 22))
    ordered, closed = meshNavigation.get_ordered_loop(
        plane, _edges_of(cmds, plane, row), "edge"
    )
    assert not closed
    assert ordered in (row, row[::-1])
    ordered, closed = meshNavigation.get_ordered_loop(
        plane, row[::2] + row[1::2], "vertex"
    )
    assert not closed
    assert ordered in (row, row[::-1])


def test_branching_edges_raise(cmds):
    from mgear.core import meshNavigation

    plane = cmds.polyPlane(
        name="sheet", subdivisionsX=4, subdivisionsY=4, constructionHistory=False
    )[0]
    # row 6-8 plus the vertical edge from 7 up to 12: a T junction
    edges = _edges_of(cmds, plane, [6, 7, 8]) + _edges_of(cmds, plane, [7, 12])
    with pytest.raises(ValueError):
        meshNavigation.get_ordered_loop(plane, edges, "edge")


def test_vertex_loop_chord_is_pruned(cmds):
    from mgear.core import meshNavigation

    plane = cmds.polyPlane(
        name="sheet", subdivisionsX=4, subdivisionsY=4, constructionHistory=False
    )[0]
    # ring around the center vertex 12 (2 rows of 5 vertices per side)
    ring = [6, 7, 8, 13, 18, 17, 16, 11]
    # split the corner face 6-7-12-11 so the diagonal 7-11 is a chord
    cmds.polyConnectComponents(plane + ".vtx[7]", plane + ".vtx[11]")
    assert 11 in meshNavigation._vertex_neighbours(plane, [7])[7]
    ordered, closed = meshNavigation.get_ordered_loop(plane, ring, "vertex")
    assert closed
    assert sorted(ordered) == sorted(ring)
    assert ordered.index(7) - ordered.index(11) not in (1, -1, 7, -7)
    assert _is_linked_path(cmds, plane, ordered, True)


def test_split_and_order(setup_path):
    from mgear.core import meshNavigation

    loop = list(range(20))
    path, other = meshNavigation.split_loop_at_vertices(loop, True, 0, 8)
    assert path == list(range(9))
    assert other == [0] + list(range(19, 7, -1))
    assert len(other) == 13
    path, other = meshNavigation.split_loop_at_vertices([5, 6, 7, 8], False, 8, 6)
    assert path == [8, 7, 6]
    assert other == []
    # An open path ordered from its last vertex comes back reversed
    path, other = meshNavigation.split_loop_at_vertices([1, 2, 3], False, 3, 1)
    assert path == [3, 2, 1]
    assert other == []
    assert not hasattr(meshNavigation, "order_path_from")


def test_mirror_indices(cmds):
    from mgear.core import meshNavigation

    left = cmds.polySphere(subdivisionsAxis=12, subdivisionsHeight=8)[0]
    cmds.move(2, 0, 0, left)
    right = cmds.polySphere(subdivisionsAxis=12, subdivisionsHeight=8)[0]
    cmds.move(-2, 0, 0, right)
    mesh = cmds.polyUnite(left, right, name="pair", constructionHistory=False)[0]
    count = cmds.polyEvaluate(mesh, vertex=True)
    indices = list(range(count // 2))
    mirrors = meshNavigation.get_mirror_vertex_indices(mesh, indices)
    assert None not in mirrors
    positions = meshNavigation.get_vertex_world_positions(mesh, indices)
    mirrored = meshNavigation.get_vertex_world_positions(mesh, mirrors)
    for (x, y, z), (mx, my, mz) in zip(positions, mirrored):
        assert (mx, my, mz) == pytest.approx((-x, y, z), abs=1e-4)
    assert meshNavigation.get_mirror_vertex_indices(mesh, mirrors) == indices

    edges = list(range(10))
    mirror_edges = meshNavigation.get_mirror_edge_indices(mesh, edges)
    assert None not in mirror_edges
    assert meshNavigation.get_mirror_edge_indices(mesh, mirror_edges) == edges

    cmds.move(0.5, 0, 0, "{}.vtx[0]".format(mesh), relative=True)
    assert meshNavigation.get_mirror_vertex_indices(mesh, [0]) == [None]


def test_rings_and_normal(cmds):
    from mgear.core import meshNavigation

    plane = cmds.polyPlane(
        name="sheet", subdivisionsX=4, subdivisionsY=4, constructionHistory=False
    )[0]
    rings = meshNavigation.get_concentric_vertex_rings(plane, [12], 2)
    assert rings[0] == [12]
    assert sorted(rings[1]) == [7, 11, 13, 17]
    assert len(rings[2]) == 8
    flat = [v for ring in rings for v in ring]
    assert len(flat) == len(set(flat))

    seed_map = meshNavigation.get_nearest_seed_map(plane, [10, 14], 2)
    assert seed_map[11] == (1, 10)
    assert seed_map[13] == (1, 14)

    normal = meshNavigation.get_average_vertex_normal(plane, [6, 7, 8])
    assert normal == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
