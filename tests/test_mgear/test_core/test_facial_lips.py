"""mgear.core.facial lips schema, solver and builder test"""

import math

import pytest


def _settings(face, loop_type="vertex", **kwargs):
    from mgear.core import settings_schema
    from mgear.core.facial import lips_schema

    data = settings_schema.defaults(lips_schema.SCHEMA)
    data["loopType"] = lips_schema.LOOP_TYPES.index(loop_type)
    data["edgeLoop"] = face["edge_loop"]
    data["vertexLoop"] = face["vertex_loop"]
    data.update(kwargs)
    return settings_schema.coerce(data, lips_schema.SCHEMA)


def _node_count():
    from maya import cmds

    return len(cmds.ls())


# ----------------------------------------------------------------------
# shared engine base


def test_shared_builder_base(setup_path):
    from mgear.core.facial import _build_base
    from mgear.core.facial import _eyelid_build

    assert _eyelid_build.select_joint_indices is _build_base.select_joint_indices
    assert _eyelid_build.MAIN_KEYABLE == _build_base.MAIN_KEYABLE
    assert _eyelid_build.SECONDARY_KEYABLE == _build_base.SECONDARY_KEYABLE
    assert issubclass(_eyelid_build.EyelidBuilder, _build_base.FacialBuilder)


def test_tool_backend_jaw_parent(lips_face):
    from mgear.rigbits.facial_rigger3.tool_backend import ToolBackend
    from maya import cmds
    import mgear.pymaya as pm

    backend = ToolBackend(
        "lips", "C", head_joint=lips_face["head_jnt"], jaw_joint=lips_face["jaw_jnt"]
    )
    driver = pm.PyNode(cmds.createNode("transform", name="drv"))
    head = backend.add_deform_joint(driver, "a_jnt")
    jaw = backend.add_deform_joint(driver, "b_jnt", parent="jaw")
    assert head.getParent().name() == lips_face["head_jnt"]
    assert jaw.getParent().name() == lips_face["jaw_jnt"]


# ----------------------------------------------------------------------
# schema


def test_schema(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import lips_schema

    defaults = settings_schema.defaults(lips_schema.SCHEMA)
    shared = settings_schema.filter_scope(defaults, lips_schema.SCHEMA, "shared")
    for key in ("vertexLoop", "invertLips", "zipperFalloff", "skinSmooth"):
        assert key in shared
    for key in ("namePrefix", "headJnt", "jawJnt", "upperRef", "lowerRef"):
        assert key not in shared
    assert lips_schema.LOOP_TYPES[defaults["loopType"]] == "vertex"
    for param in lips_schema.SCHEMA:
        assert param.tooltip, param.key
    form_keys = [key for _, keys in lips_schema.FORM_GROUPS for key in keys]
    assert sorted(form_keys) == sorted(defaults)


def test_legacy_keys(setup_path):
    from mgear.core.facial import lips_schema

    settings, warnings = lips_schema.settings_from_data(
        {"edge_loop": "m.e[1:4]", "rigid_loops": 3, "control_name": "ctl"}
    )
    assert settings["edgeLoop"] == "m.e[1:4]"
    assert settings["rigidLoops"] == 3
    assert settings["ctlName"] == "ctl"
    assert settings["loopType"] == lips_schema.LOOP_TYPES.index("edge")
    assert settings["falloffLoops"] == 8
    assert not warnings


def test_legacy_mid_vertices_dropped(setup_path):
    from mgear.core.facial import lips_schema

    settings, warnings = lips_schema.settings_from_data(
        {"edge_loop": "m.e[1]", "up_vertex": "m.vtx[1]", "low_vertex": "m.vtx[2]"}
    )
    assert "up_vertex" not in settings
    assert "upVertex" not in settings
    assert len(warnings) == 2


def test_envelope_round_trip(setup_path, tmp_path):
    from mgear.core import settings_schema
    from mgear.core.facial import lips_schema

    settings = settings_schema.defaults(lips_schema.SCHEMA)
    settings["vertexLoop"] = "m.vtx[1:9]"
    settings["invertLips"] = True
    path = str(tmp_path / "test.lips")
    lips_schema.save_settings(path, settings)
    loaded, warnings = lips_schema.load_settings(path)
    assert loaded == settings
    assert not warnings


def test_row_visibility(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import lips_schema

    settings = settings_schema.defaults(lips_schema.SCHEMA)
    rows = lips_schema.row_visibility(settings)
    assert rows["vertexLoop"] and not rows["edgeLoop"]
    assert rows["everyNVertex"] and not rows["fixedJointsNumber"]
    settings.update(loopType=0, fixedJoints=True, doSkin=False)
    rows = lips_schema.row_visibility(settings)
    assert rows["edgeLoop"] and not rows["vertexLoop"]
    assert rows["fixedJointsNumber"] and not rows["rigidLoops"]


def test_follow_row_visibility(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import lips_schema

    settings = settings_schema.defaults(lips_schema.SCHEMA)
    assert lips_schema.row_visibility(settings)["upvOffset"]
    settings["jointsFollowCurve"] = False
    assert not lips_schema.row_visibility(settings)["upvOffset"]


def test_follow_curve_default_for_old_settings(setup_path):
    from mgear.core.facial import lips_schema

    # settings saved before the option build with the joints aiming
    settings, warnings = lips_schema.settings_from_data({"edge_loop": "m.e[1:4]"})
    assert settings["jointsFollowCurve"] is True
    assert not warnings


# ----------------------------------------------------------------------
# solver


def test_solve_creates_nothing(lips_face):
    from mgear.core.facial import lips_solver

    count = _node_count()
    lips_solver.solve(_settings(lips_face))
    assert _node_count() == count


def test_solve_lips(lips_face):
    from mgear.core import vector
    from mgear.core.facial import lips_solver

    g = lips_solver.solve(_settings(lips_face, thickness=0.0))
    assert sorted(g.loop) == sorted(lips_face["vertices"])
    # corners on the X axis, right first
    assert g.upper[0] == g.lower[0] == g.r_corner
    assert g.upper[-1] == g.lower[-1] == g.l_corner
    assert g.upper_points[0][0] < 0 < g.upper_points[-1][0]
    assert len(g.upper) + len(g.lower) - 2 == len(g.loop)
    assert all(p[1] > -1e-4 for p in g.upper_points)
    assert all(p[1] < 1e-4 for p in g.lower_points)
    # mid vertices at the center
    up_mid = g.upper_points[g.upper.index(g.up_mid)]
    low_mid = g.lower_points[g.lower.index(g.low_mid)]
    assert abs(up_mid[0]) < 1e-3 and up_mid[1] > 0
    assert abs(low_mid[0]) < 1e-3 and low_mid[1] < 0
    assert g.mouth_width == pytest.approx(
        vector.distance(g.upper_points[0], g.upper_points[-1])
    )
    frame = g.frame
    for axis, expected in (("lateral", (1, 0, 0)), ("up", (0, 1, 0))):
        assert vector._dot(frame[axis], expected) == pytest.approx(1.0, abs=1e-3)


def test_edge_and_vertex_input(lips_face):
    from mgear.core.facial import lips_solver

    edge = lips_solver.solve(_settings(lips_face, "edge"))
    vertex = lips_solver.solve(_settings(lips_face, "vertex"))
    assert edge.upper == vertex.upper
    assert edge.lower == vertex.lower


def test_solve_without_math_dist(lips_face, monkeypatch):
    # Maya 2022 runs Python 3.7, which has no math.dist
    from mgear.core.facial import lips_solver

    reference = lips_solver.solve(_settings(lips_face))
    monkeypatch.delattr(math, "dist", raising=False)
    geometry = lips_solver.solve(_settings(lips_face))
    assert geometry.upper == reference.upper
    assert geometry.mouth_width == pytest.approx(reference.mouth_width)


def test_thickness_along_frame(lips_face):
    from mgear.core.facial import lips_solver

    g = lips_solver.solve(_settings(lips_face, thickness=0.1))
    mid = len(g.upper) // 2
    moved = [g.upper_curve_points[mid][i] - g.upper_points[mid][i] for i in range(3)]
    assert moved == pytest.approx([0, 0.1, 0], abs=1e-6)
    moved = [g.lower_curve_points[mid][i] - g.lower_points[mid][i] for i in range(3)]
    assert moved == pytest.approx([0, -0.1, 0], abs=1e-6)
    # corners move back and outward
    moved = [g.upper_curve_points[-1][i] - g.upper_points[-1][i] for i in range(3)]
    assert moved == pytest.approx([0.1, 0, -0.1], abs=1e-6)


@pytest.mark.parametrize("rotation", [(30, 0, 0), (0, 30, 0), (0, 0, 90)])
def test_rotated_mouth(lips_face, rotation):
    from maya import cmds
    from mgear.core import vector
    from mgear.core.facial import lips_solver

    rest = lips_solver.solve(_settings(lips_face))
    cmds.setAttr(lips_face["mesh"] + ".rotate", *rotation)
    if rotation[2] == 90:
        # the mouth faces front sideways: the lateral hint is world X, so
        # the corners are the vertices that were on the Y axis. The upper
        # lip is the one higher in the frame.
        g = lips_solver.solve(_settings(lips_face))
        up = [vector.to_frame_coordinates(p, g.frame)[1] for p in g.upper_points]
        low = [vector.to_frame_coordinates(p, g.frame)[1] for p in g.lower_points]
        assert sum(up) / len(up) > sum(low) / len(low)
        return
    g = lips_solver.solve(_settings(lips_face, thickness=0.1))
    assert (g.r_corner, g.l_corner) == (rest.r_corner, rest.l_corner)
    assert g.upper == rest.upper
    mid = len(g.upper) // 2
    moved = [g.upper_curve_points[mid][i] - g.upper_points[mid][i] for i in range(3)]
    assert [m / 0.1 for m in moved] == pytest.approx(list(g.frame["up"]), abs=1e-3)


def test_closed_lips_crossing(lips_face):
    from maya import cmds
    from mgear.core.facial import lips_solver

    rest = lips_solver.solve(_settings(lips_face))
    mesh = lips_face["mesh"]
    low_y = cmds.pointPosition("{}.vtx[{}]".format(mesh, rest.low_mid))[1]
    # the upper mid vertex dips under the lower one
    cmds.xform(
        "{}.vtx[{}]".format(mesh, rest.up_mid),
        relative=True,
        translation=(
            0,
            low_y * 2.5 - cmds.pointPosition("{}.vtx[{}]".format(mesh, rest.up_mid))[1],
            0,
        ),
    )
    assert cmds.pointPosition("{}.vtx[{}]".format(mesh, rest.up_mid))[1] < low_y
    g = lips_solver.solve(_settings(lips_face))
    assert g.upper == rest.upper
    assert g.up_mid == rest.up_mid
    assert g.low_mid == rest.low_mid


def test_invert_lips(lips_face):
    from mgear.core.facial import lips_solver

    rest = lips_solver.solve(_settings(lips_face))
    g = lips_solver.solve(_settings(lips_face, invertLips=True))
    assert g.upper == rest.lower
    assert g.lower == rest.upper
    assert g.up_mid == rest.low_mid
    assert g.low_mid == rest.up_mid


def test_detection_selection(lips_face):
    from maya import cmds
    from mgear.core import meshNavigation
    from mgear.core.facial import lips_solver

    for invert in (False, True):
        g = lips_solver.solve(_settings(lips_face, invertLips=invert))
        count = _node_count()
        selection = lips_solver.detection_selection(g)
        assert _node_count() == count
        cmds.select(selection)
        _, _, indices = meshNavigation.parse_component_string(
            meshNavigation.components_from_selection("vertex")
        )
        assert sorted(indices) == sorted(g.upper)
        assert g.r_corner in indices and g.l_corner in indices


@pytest.mark.parametrize(
    "change, message",
    [
        ({"vertexLoop": ""}, "Set the lips vertex loop"),
        ({"vertexLoop": "nope.vtx[1:3]"}, "doesn't exist"),
        ("open", "closed"),
    ],
)
def test_solve_errors(lips_face, change, message):
    from mgear.core import meshNavigation
    from mgear.core.facial import lips_solver

    if change == "open":
        change = {
            "vertexLoop": meshNavigation.format_component_string(
                lips_face["mesh"], "vertex", lips_face["vertices"][:-3]
            )
        }
    with pytest.raises(ValueError, match=message):
        lips_solver.solve(_settings(lips_face, **change))


def test_mirrored_control_matrix(lips_face):
    from mgear.core.facial import lips_solver

    g = lips_solver.solve(_settings(lips_face))
    assert g.side_matrix("L") == g.rig_matrix
    assert g.side_matrix("C") == g.rig_matrix
    assert g.side_matrix("R")[:3] == pytest.approx([-v for v in g.rig_matrix[:3]])
    assert g.side_matrix("R")[4:] == pytest.approx(g.rig_matrix[4:])
    g = lips_solver.solve(_settings(lips_face, mirrorBehavior=False))
    assert g.side_matrix("R") == g.rig_matrix


# ----------------------------------------------------------------------
# builder


def _build(face, **kwargs):
    from mgear.rigbits.facial_rigger3 import lips

    kwargs.setdefault("vertexLoop", face["vertex_loop"])
    kwargs.setdefault("headJnt", face["head_jnt"])
    kwargs.setdefault("jawJnt", face["jaw_jnt"])
    kwargs.setdefault("doSkin", False)
    return lips.rig(**kwargs)


def _position(node):
    from maya import cmds

    return cmds.xform(str(node), query=True, worldSpace=True, translation=True)


def _joints(prefix="lips"):
    from maya import cmds

    def index(name):
        return int(name.split("_")[1][1:])

    upper = sorted(cmds.ls(prefix + "_C*_upLip_jnt"), key=index)
    lower = sorted(cmds.ls(prefix + "_C*_lowLip_jnt"), key=index)
    return upper, lower


def _cvs(crv):
    import mgear.pymaya as pm

    return [(p[0], p[1], p[2]) for p in pm.PyNode(crv).getCVs(space="world")]


def _flat(points):
    return [value for point in points for value in point]


def _ctl(name, prefix="lips"):
    return "{}_C_{}_ctl".format(prefix, name)


def test_builder_uses_backend(lips_face):
    from mgear.core.facial import lips_solver
    from mgear.core.facial._lips_build import LipsBuilder
    from mgear.rigbits.facial_rigger3.tool_backend import ToolBackend

    class RecordingBackend(ToolBackend):
        def __init__(self, *args, **kwargs):
            super(RecordingBackend, self).__init__(*args, **kwargs)
            self.ctls = []
            self.joints = []

        def add_ctl(self, parent, name, *args, **kwargs):
            self.ctls.append(name)
            return super(RecordingBackend, self).add_ctl(parent, name, *args, **kwargs)

        def add_deform_joint(self, driver, name, idx=None, parent=None):
            self.joints.append((name, parent))
            return super(RecordingBackend, self).add_deform_joint(
                driver, name, idx, parent
            )

    settings = _settings(lips_face)
    geometry = lips_solver.solve(settings)
    backend = RecordingBackend("lips", "C")
    builder = LipsBuilder(settings, geometry, backend)
    builder.build_objects()
    builder.build_attributes()
    builder.build_operators()
    assert sorted(backend.ctls) == sorted(
        [
            "corner_R",
            "corner_L",
            "upper",
            "lower",
            "upOuter_R",
            "upInner_R",
            "upInner_L",
            "upOuter_L",
            "lowOuter_R",
            "lowInner_R",
            "lowInner_L",
            "lowOuter_L",
        ]
    )
    assert backend.joints.count(("upLip_jnt", "head")) == len(geometry.upper)
    assert backend.joints.count(("lowLip_jnt", "jaw")) == len(geometry.lower) - 2
    assert len(backend.joints) == len(geometry.upper) + len(geometry.lower) - 2


def test_tool_rig(lips_face):
    from maya import cmds

    root = _build(lips_face)
    assert root.name() == "lips_C_root"
    upper, lower = _joints()
    assert len(upper) == 11 and len(lower) == 9
    for jnt in upper:
        assert cmds.listRelatives(jnt, parent=True)[0] == "head_jnt"
    for jnt in lower:
        assert cmds.listRelatives(jnt, parent=True)[0] == "jaw_jnt"
    assert len(cmds.ls("lips_C_*_ctl", type="transform")) == 12
    assert cmds.sets("rig_controllers_grp", query=True)


def test_rest_pose(lips_face):
    from mgear.core import meshNavigation
    from mgear.core import vector
    from mgear.core.facial import lips_solver

    _build(lips_face, thickness=0.0)
    g = lips_solver.solve(_settings(lips_face, thickness=0.0))
    upper, lower = _joints()
    mesh = lips_face["mesh"]
    for joints, vertices in ((upper, g.upper), (lower, g.lower[1:-1])):
        points = meshNavigation.get_vertex_world_positions(mesh, vertices)
        for jnt, point in zip(joints, points):
            assert vector.distance(_position(jnt), point) < 1e-3


def test_jaw_follow(lips_face):
    from maya import cmds
    from mgear.core import vector

    _build(lips_face)
    jaw = lips_face["jaw_jnt"]
    corner = _ctl("corner_L")
    rigid = cmds.createNode("transform", name="rigid", parent=jaw)
    cmds.xform(rigid, worldSpace=True, translation=_position(corner))
    rest = {name: _position(_ctl(name)) for name in ("corner_L", "upper", "lower")}
    rigid_rest = _position(rigid)
    cmds.setAttr(jaw + ".rotateX", 20)
    moved = [_position(rigid)[i] - rigid_rest[i] for i in range(3)]
    for follow, ratio in ((0.5, 0.5), (1.0, 1.0), (0.0, 0.0)):
        cmds.setAttr(corner + ".jawFollow", follow)
        delta = [_position(corner)[i] - rest["corner_L"][i] for i in range(3)]
        assert delta == pytest.approx([m * ratio for m in moved], abs=1e-4)
    assert _position(_ctl("upper")) == pytest.approx(rest["upper"], abs=1e-5)
    assert vector.distance(_position(_ctl("lower")), rest["lower"]) > 0.01


def _zipper_rig(face):
    from maya import cmds

    _build(face)
    cmds.setAttr(_ctl("lower") + ".ty", -0.2)
    return {
        "up": "lips_C_upZipper_crv",
        "low": "lips_C_lowZipper_crv",
        "up_rope": "lips_C_upRope_crv",
        "low_rope": "lips_C_lowRope_crv",
    }


def test_zipper_full_zip(lips_face):
    from maya import cmds

    # the joints sit a thickness inside each lip (the fixture frame up is +Y)
    thickness = 0.03
    crvs = _zipper_rig(lips_face)
    upper, lower = _joints()
    lower_rest = [_position(j) for j in lower]
    up_rope = _cvs(crvs["up_rope"])
    low_rope = _cvs(crvs["low_rope"])
    for name in ("corner_R", "corner_L"):
        cmds.setAttr(_ctl(name) + ".zipper", 1)

    def shifted(points, offset):
        return [(p[0], p[1] + offset, p[2]) for p in points]

    middle = [
        tuple((a[i] + b[i]) * 0.5 for i in range(3)) for a, b in zip(up_rope, low_rope)
    ]
    # each lip stops a thickness away from the middle: the surfaces meet
    assert _flat(_cvs(crvs["up"])) == pytest.approx(
        _flat(shifted(middle, thickness)), abs=1e-4
    )
    assert _flat(_cvs(crvs["low"])) == pytest.approx(
        _flat(shifted(middle, -thickness)), abs=1e-4
    )
    # the lower joints went up to the zip
    assert all(_position(j)[1] > rest[1] + 0.01 for j, rest in zip(lower, lower_rest))
    cmds.setAttr(_ctl("upper") + ".zipperHeight", 1)
    assert _flat(_cvs(crvs["low"])) == pytest.approx(
        _flat(shifted(up_rope, -2 * thickness)), abs=1e-4
    )
    assert _flat(_cvs(crvs["up"])) == pytest.approx(_flat(up_rope), abs=1e-4)


def test_zipper_one_side(lips_face):
    from maya import cmds

    crvs = _zipper_rig(lips_face)
    rope = _cvs(crvs["low_rope"])
    cmds.setAttr(_ctl("corner_L") + ".zipper", 0.5)
    zipper = _cvs(crvs["low"])
    half = len(rope) // 2
    # right half untouched, left corner side zipped up
    assert _flat(zipper[:half]) == pytest.approx(_flat(rope[:half]), abs=1e-5)
    assert zipper[11][1] > rope[11][1] + 0.01


def test_zipper_rest(lips_face):
    crvs = _zipper_rig(lips_face)
    for key in ("up", "low"):
        assert _flat(_cvs(crvs[key])) == pytest.approx(
            _flat(_cvs(crvs[key + "_rope"])), abs=1e-5
        )


def _world_matrix(node):
    from maya import cmds
    from maya.api import OpenMaya as om2

    return om2.MMatrix(cmds.xform(node, query=True, worldSpace=True, matrix=True))


def _follow_point(node, rest_matrix, point):
    """Where a world point at rest, attached to node, is now."""
    from maya.api import OpenMaya as om2

    local = om2.MPoint(point) * rest_matrix.inverse()
    result = local * _world_matrix(node)
    return (result.x, result.y, result.z)


def test_lip_roll(lips_face):
    from maya import cmds

    _build(lips_face, thickness=0.05)
    upper, lower = _joints()
    rest = {j: _world_matrix(j) for j in upper + lower}
    mid = upper[len(upper) // 2]
    low_mid = lower[len(lower) // 2]
    # the lip edges: below the upper joints, above the lower ones
    up_edge = [v - u for v, u in zip(_position(mid), (0, 0.05, 0))]
    low_edge = [v + u for v, u in zip(_position(low_mid), (0, 0.05, 0))]

    cmds.setAttr(_ctl("upper") + ".roll", 30)
    y_rest = [rest[mid][4 + i] for i in range(3)]
    y_now = [_world_matrix(mid)[4 + i] for i in range(3)]
    cosine = sum(a * b for a, b in zip(y_rest, y_now))
    assert math.degrees(math.acos(min(1.0, cosine))) == pytest.approx(30, abs=0.5)
    # the upper lip edge rolls out, forward
    assert _follow_point(mid, rest[mid], up_edge)[2] > up_edge[2] + 0.01
    for jnt in [upper[0], upper[-1]] + lower:
        assert list(_world_matrix(jnt)) == pytest.approx(list(rest[jnt]), abs=1e-4)

    cmds.setAttr(_ctl("lower") + ".roll", 30)
    assert _follow_point(low_mid, rest[low_mid], low_edge)[2] > low_edge[2] + 0.01


def _turn(rest, now):
    """Get the rotation between two world matrices.

    Returns:
        tuple: (unit axis as a tuple, angle in degrees)
    """
    from maya.api import OpenMaya as om2

    def quaternion(m):
        return om2.MTransformationMatrix(m).rotation(asQuaternion=True)

    axis, angle = (quaternion(rest).inverse() * quaternion(now)).asAxisAngle()
    if angle > math.pi:
        angle = 2.0 * math.pi - angle
    return (axis.x, axis.y, axis.z), math.degrees(angle)


def test_joints_translate_only(lips_face):
    from maya import cmds

    _build(lips_face, jointsFollowCurve=False)
    upper, lower = _joints()
    assert not cmds.ls("lips_C*_upLipUpv", "lips_C*_lowLipUpv")
    rest = {joint: _world_matrix(joint) for joint in upper + lower}
    rest_position = _position(upper[3])
    cmds.setAttr(_ctl("upper") + ".ty", 0.1)
    # the joints move but keep their orientation
    assert _position(upper[3])[1] > rest_position[1] + 0.02
    for joint in upper + lower:
        assert _turn(rest[joint], _world_matrix(joint))[1] < 1e-2


def test_translate_only_follows_refs(lips_face):
    from maya import cmds

    _build(lips_face, jointsFollowCurve=False)
    upper, lower = _joints()
    rest = {joint: _world_matrix(joint) for joint in upper + lower}
    # the lower lip turns with the jaw, the upper lip and corners don't
    cmds.setAttr(lips_face["jaw_jnt"] + ".rotateX", 20)
    for joint in lower:
        axis, angle = _turn(rest[joint], _world_matrix(joint))
        assert angle == pytest.approx(20, abs=1e-2)
        assert abs(axis[0]) == pytest.approx(1, abs=1e-3)
    for joint in upper:
        assert _turn(rest[joint], _world_matrix(joint))[1] < 1e-2


def test_translate_only_rest_axes(lips_face):
    from maya import cmds

    _build(lips_face)
    upper, _ = _joints()
    aiming = _world_matrix(upper[len(upper) // 2])
    cmds.delete("lips_C_root")
    _build(lips_face, jointsFollowCurve=False)
    upper, _ = _joints()
    fixed = _world_matrix(upper[len(upper) // 2])
    assert _turn(aiming, fixed)[1] < 2.0


def test_translate_only_roll(lips_face):
    from maya import cmds

    _build(lips_face, thickness=0.05, jointsFollowCurve=False)
    upper, _ = _joints()
    mid = upper[len(upper) // 2]
    rest = {joint: _world_matrix(joint) for joint in upper}
    up_edge = [v - u for v, u in zip(_position(mid), (0, 0.05, 0))]
    cmds.setAttr(_ctl("upper") + ".roll", 30)
    axis, angle = _turn(rest[mid], _world_matrix(mid))
    assert angle == pytest.approx(30, abs=0.5)
    assert abs(axis[0]) == pytest.approx(1, abs=1e-3)
    # the upper lip edge rolls out, forward
    assert _follow_point(mid, rest[mid], up_edge)[2] > up_edge[2] + 0.01
    for joint in (upper[0], upper[-1]):
        assert _turn(rest[joint], _world_matrix(joint))[1] < 1e-2


def test_joints_follow_curve(lips_face):
    from maya import cmds

    _build(lips_face)
    upper, _ = _joints()
    # between the corner and the upper control, where the curve bends
    joint = upper[2]
    rest = _world_matrix(joint)
    cmds.setAttr(_ctl("upper") + ".ty", 0.1)
    assert _turn(rest, _world_matrix(joint))[1] > 1.0


def test_no_legacy_mult_node(lips_face):
    from maya import cmds
    from mgear.core import node

    _build(lips_face)
    mult = node.createMulDL()
    assert cmds.ls("lips_C*_upRoll_mult", type=cmds.nodeType(str(mult)))


def test_roll_falloff_off(lips_face):
    from mgear.core.facial._lips_build import roll_weight

    assert roll_weight(0.0, 1.0) == 1.0
    assert roll_weight(1.0, 1.0) == 0.0
    assert roll_weight(0.5, 1.0) == pytest.approx(0.5)
    assert roll_weight(1.0, 1.0, falloff=False) == 1.0


def test_zipper_distances(setup_path):
    from mgear.core.facial._lips_build import zipper_distances

    assert zipper_distances(5) == [
        ("R", 0.0),
        ("R", 0.5),
        ("C", 1.0),
        ("L", 0.5),
        ("L", 0.0),
    ]
    assert [side for side, _ in zipper_distances(4)] == ["R", "R", "L", "L"]


def test_joint_distribution(lips_face):
    from maya import cmds

    _build(lips_face, everyNVertex=2)
    upper, lower = _joints()
    assert [int(j.split("_")[1][1:]) for j in upper] == [0, 2, 4, 6, 8, 10]
    assert len(lower) == 4
    cmds.file(new=True, force=True)


def test_fixed_joints(lips_face):
    _build(lips_face, fixedJoints=True, fixedJointsNumber=5)
    upper, lower = _joints()
    assert len(upper) == 5
    assert len(lower) == 3


def test_mirrored_corners(lips_face):
    from maya import cmds

    _build(lips_face)
    rest = _position(_ctl("corner_L"))
    for name in ("corner_R", "corner_L"):
        cmds.setAttr(_ctl(name) + ".tx", 0.1)
        cmds.setAttr(_ctl(name) + ".ty", 0.05)
    left = _position(_ctl("corner_L"))
    right = _position(_ctl("corner_R"))
    assert right == pytest.approx([-left[0], left[1], left[2]], abs=1e-5)
    # positive tx pulls both corners out
    assert left[0] == pytest.approx(rest[0] + 0.1, abs=1e-5)


def test_mirror_ready_names(lips_face):
    from maya import cmds
    from mgear.core import string

    _build(lips_face)
    controls = cmds.ls("lips_C_*_ctl", type="transform")
    left = [c for c in controls if "_L_" in c]
    assert len(left) == 5
    for ctl in left:
        assert string.convertRLName(ctl) in controls


def test_mirror_pose(lips_face):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.core import anim_utils

    _build(lips_face)
    corner = _ctl("corner_L")
    cmds.setAttr(corner + ".tx", 0.1)
    cmds.setAttr(corner + ".ty", 0.05)
    cmds.setAttr(corner + ".rz", 10)
    anim_utils.mirrorPose(nodes=[pm.PyNode(corner)])
    left = _position(corner)
    right = _position(_ctl("corner_R"))
    assert right == pytest.approx([-left[0], left[1], left[2]], abs=1e-5)
    # a center control mirrors onto itself
    upper = _ctl("upper")
    cmds.setAttr(upper + ".tx", 0.1)
    cmds.setAttr(upper + ".ry", 10)
    anim_utils.mirrorPose(nodes=[pm.PyNode(upper)])
    assert cmds.getAttr(upper + ".tx") == pytest.approx(-0.1)
    assert cmds.getAttr(upper + ".ry") == pytest.approx(-10)


def test_global_scale(lips_face):
    from maya import cmds

    root = _build(lips_face, thickness=0.05)
    upper, lower = _joints()
    rest = {j: _position(j) for j in upper + lower}
    # global scale: the rig and the head it follows scale together
    world = cmds.group(empty=True, name="world")
    cmds.parent(root.name(), lips_face["head_jnt"], world)
    cmds.setAttr(world + ".scale", 2, 2, 2)
    for jnt, position in rest.items():
        assert _position(jnt) == pytest.approx([v * 2 for v in position], abs=1e-3)
    scale = cmds.xform(upper[3], query=True, worldSpace=True, scale=True)
    assert scale == pytest.approx([2, 2, 2], abs=1e-3)


def test_secondary_visibility(lips_face):
    from maya import cmds

    _build(lips_face)
    upper = _ctl("upper")
    cmds.setAttr(upper + ".secondaryVis", False)
    secondaries = [
        c
        for c in cmds.ls("lips_C_*_ctl", type="transform")
        if ("Outer" in c or "Inner" in c)
    ]
    assert len(secondaries) == 8
    for ctl in secondaries:
        for shape in cmds.listRelatives(ctl, shapes=True):
            assert not cmds.getAttr(shape + ".visibility")
    for name in ("corner_L", "upper", "lower"):
        for shape in cmds.listRelatives(_ctl(name), shapes=True):
            assert cmds.getAttr(shape + ".visibility")


def test_autoskin(lips_face):
    from maya import cmds
    from mgear.core.facial import lips_solver

    mesh = lips_face["mesh"]
    cmds.skinCluster(lips_face["head_jnt"], mesh, toSelectedBones=True)
    _build(lips_face, doSkin=True, rigidLoops=1, falloffLoops=2)
    upper, lower = _joints()
    cluster = cmds.ls(cmds.listHistory(mesh), type="skinCluster")[0]
    influences = cmds.skinCluster(cluster, query=True, influence=True)
    for jnt in upper + lower:
        assert jnt in influences
    g = lips_solver.solve(_settings(lips_face))
    weight = cmds.skinPercent(
        cluster, "{}.vtx[{}]".format(mesh, g.up_mid), transform=upper[5], query=True
    )
    assert weight == pytest.approx(1.0)


def test_autoskin_new_cluster(lips_face):
    from maya import cmds

    _build(lips_face, doSkin=True)
    mesh = lips_face["mesh"]
    assert cmds.ls(cmds.listHistory(mesh), type="skinCluster") == ["mouth_skinCluster"]


def _roll_angle(rest, now):
    """Rotation about the lip direction between two joint matrices."""
    x_axis = [now[i] for i in range(3)]

    def projected(m):
        y = [m[4 + i] for i in range(3)]
        along = sum(a * b for a, b in zip(y, x_axis))
        y = [y[i] - x_axis[i] * along for i in range(3)]
        length = math.sqrt(sum(v * v for v in y))
        return [v / length for v in y]

    cosine = sum(a * b for a, b in zip(projected(rest), projected(now)))
    return math.degrees(math.acos(min(1.0, cosine)))


def _zipper_rolls(face, zipped_up_vectors):
    from maya import cmds

    _zipper_rig(face)
    _, lower = _joints()
    if not zipped_up_vectors:
        # the up vectors before the fix: on the unzipped ropes
        for path in cmds.ls("lips_C*_lowLipUpv_motionPath"):
            cmds.connectAttr(
                "lips_C_lowRopeUpv_crvShape.worldSpace[0]",
                path + ".geometryPath",
                force=True,
            )
    rest = {joint: _world_matrix(joint) for joint in lower}
    for name in ("corner_R", "corner_L"):
        cmds.setAttr(_ctl(name) + ".zipper", 1)
    return max(_roll_angle(rest[j], _world_matrix(j)) for j in lower)


def test_zipper_keeps_orientation(lips_face):
    from maya import cmds

    unzipped = _zipper_rolls(lips_face, False)
    cmds.delete("lips_C_root")
    zipped = _zipper_rolls(lips_face, True)
    assert zipped < 1.0
    assert unzipped > zipped + 2.0


def test_smooth_topological_weights(setup_path):
    from mgear.core import skin

    # a chain 0-1-2-3-4: the ends are pinned to A and B
    weights = {
        0: {"A": 1.0},
        1: {"A": 1.0},
        2: {"A": 1.0},
        3: {"B": 1.0},
        4: {"B": 1.0},
    }
    neighbours = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}}
    smoothed = skin.smooth_topological_weights(weights, neighbours, {0, 4}, 10)
    assert smoothed[0] == {"A": 1.0}
    assert smoothed[4] == {"B": 1.0}
    for vertex in (1, 2, 3):
        assert sum(smoothed[vertex].values()) == pytest.approx(1.0)
    # the hard A/B boundary between 2 and 3 became a ramp
    b = [smoothed[v].get("B", 0.0) for v in range(5)]
    assert b == sorted(b)
    assert 0.0 < b[2] < b[3] < 1.0
    assert skin.smooth_topological_weights(weights, neighbours, set(), 0) == weights


def _joint_weight_jumps(mesh, cluster, joints, loop):
    """Largest weight change of a lip joint between neighbor vertices.

    The loop vertices are left out: each one is fully weighted to its joint.
    """
    from maya import cmds
    from mgear.core import meshNavigation

    count = cmds.polyEvaluate(mesh, vertex=True)
    values = {}
    for vertex in range(count):
        component = "{}.vtx[{}]".format(mesh, vertex)
        row = cmds.skinPercent(cluster, component, query=True, value=True)
        names = cmds.skinPercent(cluster, component, query=True, transform=None)
        values[vertex] = dict(zip(names, row))
    jump = 0.0
    neighbours = meshNavigation.get_vertex_neighbours(mesh, range(count))
    for vertex, around in neighbours.items():
        if vertex in loop:
            continue
        for other in around:
            if other in loop:
                continue
            for joint in joints:
                change = abs(values[vertex].get(joint, 0) - values[other].get(joint, 0))
                jump = max(jump, change)
    return jump


def test_autoskin_smooth(lips_face):
    from maya import cmds
    from mgear.core.facial import lips_solver
    from mgear.core.facial._lips_build import LipsBuilder
    from mgear.rigbits.facial_rigger3.tool_backend import ToolBackend

    mesh = lips_face["mesh"]
    cmds.skinCluster(lips_face["head_jnt"], mesh, toSelectedBones=True)
    settings = _settings(lips_face, rigidLoops=1, falloffLoops=3, skinSmooth=0)
    geometry = lips_solver.solve(settings)
    builder = LipsBuilder(
        settings, geometry, ToolBackend("lips", "C", head_joint=lips_face["head_jnt"])
    )
    builder.build_objects()
    cluster = builder.build_skin()
    joints = [builder.backend.deform_joint(h) for h, _ in builder.joint_seeds]
    hard = _joint_weight_jumps(mesh, cluster, joints, set(geometry.loop))
    settings["skinSmooth"] = 3
    builder.build_skin()
    smooth = _joint_weight_jumps(mesh, cluster, joints, set(geometry.loop))
    assert smooth < hard * 0.8
    # the loop vertices keep their joint
    weight = cmds.skinPercent(
        cluster,
        "{}.vtx[{}]".format(mesh, geometry.up_mid),
        query=True,
        transform=joints[len(geometry.upper) // 2],
    )
    assert weight == pytest.approx(1.0)


def test_frame_faces_world_front(lips_face):
    from maya import cmds
    from mgear.core.facial import lips_solver

    # a tilted mouth: without a front point the frame faces the scene front
    cmds.setAttr(lips_face["mesh"] + ".rotateX", -30)
    g = lips_solver.solve(_settings(lips_face))
    assert list(g.frame["normal"]) == pytest.approx([0, 0, 1], abs=1e-6)
    angle = math.radians(-30)
    front = (0, -math.sin(angle) * 5, math.cos(angle) * 5)
    g = lips_solver.solve(_settings(lips_face), front=front)
    direction = [v - c for v, c in zip(front, g.frame["center"])]
    length = math.sqrt(sum(v * v for v in direction))
    assert list(g.frame["normal"]) == pytest.approx(
        [v / length for v in direction], abs=1e-6
    )


def _lip_scale(joint):
    from maya import cmds

    return cmds.xform(joint, query=True, worldSpace=True, scale=True)


def test_squash_stretch(lips_face):
    from maya import cmds

    _build(lips_face, squashStretch=True)
    upper, lower = _joints()
    mid = upper[len(upper) // 2]
    assert _lip_scale(mid) == pytest.approx([1, 1, 1], abs=1e-4)
    # corners pulled out: the lips stretch and get thinner
    for name in ("corner_R", "corner_L"):
        cmds.setAttr(_ctl(name) + ".tx", 0.3)
    stretched = _lip_scale(mid)
    assert stretched[0] == pytest.approx(1, abs=1e-4)
    assert stretched[1] < 0.95 and stretched[2] == pytest.approx(stretched[1])
    assert _lip_scale(lower[len(lower) // 2])[1] < 0.95
    # the animators turn it off per lip
    cmds.setAttr(_ctl("upper") + ".squashStretch", 0)
    assert _lip_scale(mid) == pytest.approx([1, 1, 1], abs=1e-4)
    assert _lip_scale(lower[len(lower) // 2])[1] < 0.95
    cmds.setAttr(_ctl("upper") + ".squashStretch", 1)
    # corners pushed in: thicker
    for name in ("corner_R", "corner_L"):
        cmds.setAttr(_ctl(name) + ".tx", -0.2)
    assert _lip_scale(mid)[1] > 1.05


def test_squash_stretch_off(lips_face):
    from maya import cmds

    _build(lips_face)
    assert not cmds.attributeQuery("squashStretch", node=_ctl("upper"), exists=True)
    upper, _ = _joints()
    cmds.setAttr(_ctl("corner_L") + ".tx", 0.3)
    assert _lip_scale(upper[len(upper) // 2]) == pytest.approx([1, 1, 1], abs=1e-4)


def test_squash_stretch_global_scale(lips_face):
    from maya import cmds

    root = _build(lips_face, squashStretch=True)
    world = cmds.group(empty=True, name="world")
    cmds.parent(root.name(), lips_face["head_jnt"], world)
    cmds.setAttr(world + ".scale", 2, 2, 2)
    upper, _ = _joints()
    assert _lip_scale(upper[len(upper) // 2]) == pytest.approx([2, 2, 2], abs=1e-3)
