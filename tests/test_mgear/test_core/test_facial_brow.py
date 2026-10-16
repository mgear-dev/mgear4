"""mgear.core.facial brow schema, solver and builder test"""

import math

import pytest


def _settings(face, brow="L", loop_type="vertex", **kwargs):
    from mgear.core import settings_schema
    from mgear.core.facial import brow_schema

    data = settings_schema.defaults(brow_schema.SCHEMA)
    data["loopType"] = brow_schema.LOOP_TYPES.index(loop_type)
    data["edgeLoop"] = face[brow]["edge_loop"]
    data["vertexLoop"] = face[brow]["vertex_loop"]
    data.update(kwargs)
    return settings_schema.coerce(data, brow_schema.SCHEMA)


def _node_count():
    from maya import cmds

    return len(cmds.ls())


# ----------------------------------------------------------------------
# schema


def test_schema(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import brow_schema

    defaults = settings_schema.defaults(brow_schema.SCHEMA)
    shared = settings_schema.filter_scope(defaults, brow_schema.SCHEMA, "shared")
    for key in ("vertexLoop", "mainControls", "slideSurface", "squeezeDistance"):
        assert key in shared
    for key in ("namePrefix", "side", "headJnt", "hookLeft", "frontNode"):
        assert key not in shared
    assert defaults["slideSurface"] == ""
    for param in brow_schema.SCHEMA:
        assert param.tooltip, param.key
    form_keys = [key for _, keys in brow_schema.FORM_GROUPS for key in keys]
    assert sorted(form_keys) == sorted(defaults)


def test_legacy_keys(setup_path):
    from mgear.core.facial import brow_schema

    settings, warnings = brow_schema.settings_from_data(
        {
            "edge_loop": "m.e[1:4]",
            "main_div": 4,
            "sec_div": 6,
            "side": 2,
            "symmetry_mode": 0,
            "brow_jnt_C": "head_jnt",
        }
    )
    assert settings["edgeLoop"] == "m.e[1:4]"
    assert settings["mainControls"] == 4
    assert settings["secondaryControls"] == 6
    assert brow_schema.SIDES[settings["side"]] == "R"
    assert settings["headJnt"] == "head_jnt"
    assert settings["loopType"] == brow_schema.LOOP_TYPES.index("edge")
    assert any("symmetry_mode" in warning for warning in warnings)


def test_row_visibility(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import brow_schema

    settings = settings_schema.defaults(brow_schema.SCHEMA)
    rows = brow_schema.row_visibility(settings)
    assert not rows["hookLeft"] and not rows["hookRight"]
    settings["side"] = brow_schema.SIDES.index("C")
    settings["useSecondary"] = False
    rows = brow_schema.row_visibility(settings)
    assert rows["hookLeft"] and rows["hookRight"]
    assert not rows["secondaryControls"]


# ----------------------------------------------------------------------
# solver


def test_solve_creates_nothing(brow_face):
    from mgear.core.facial import brow_solver

    count = _node_count()
    brow_solver.solve(_settings(brow_face))
    assert _node_count() == count


@pytest.mark.parametrize("side", ["L", "R", "C"])
def test_solve_sides(brow_face, side):
    from mgear.core.facial import brow_solver

    g = brow_solver.solve(_settings(brow_face, side))
    assert g.side == side
    expected = brow_face[side]["vertices"]
    assert g.path == expected
    assert g.length == pytest.approx(0.1 * (len(expected) - 1), rel=0.05)


def test_inner_end_first_either_way(brow_face):
    from mgear.core import meshNavigation
    from mgear.core.facial import brow_solver

    reverse = meshNavigation.format_component_string(
        brow_face["mesh"], "vertex", brow_face["L"]["vertices"][::-1]
    )
    g = brow_solver.solve(_settings(brow_face, "L", vertexLoop=reverse))
    assert g.path[0] == brow_face["L"]["vertices"][0]


def test_edge_and_vertex_path(brow_face):
    from mgear.core.facial import brow_solver

    edge = brow_solver.solve(_settings(brow_face, "L", "edge"))
    vertex = brow_solver.solve(_settings(brow_face, "L", "vertex"))
    assert edge.path == vertex.path


def test_solve_without_math_dist(brow_face, monkeypatch):
    # Maya 2022 runs Python 3.7, which has no math.dist
    from mgear.core.facial import brow_solver

    reference = brow_solver.solve(_settings(brow_face))
    monkeypatch.delattr(math, "dist", raising=False)
    geometry = brow_solver.solve(_settings(brow_face))
    assert geometry.path == reference.path
    assert geometry.length == pytest.approx(reference.length)


def test_side_override(brow_face):
    from mgear.core.facial import brow_schema
    from mgear.core.facial import brow_solver

    settings = _settings(brow_face, "L", side=brow_schema.SIDES.index("C"))
    assert brow_solver.solve(settings).side == "C"
    assert brow_solver.solve(_settings(brow_face, "L"), side="R").side == "R"


def test_joint_depth(brow_face):
    from mgear.core.facial import brow_solver

    g = brow_solver.solve(_settings(brow_face, "L", thickness=0.05))
    moved = [g.curve_points[0][i] - g.points[0][i] for i in range(3)]
    assert moved == pytest.approx([0, 0, -0.05], abs=1e-6)


def test_mirrored_control_matrix(brow_face):
    from mgear.core.facial import brow_solver

    left = brow_solver.solve(_settings(brow_face, "L"))
    right = brow_solver.solve(_settings(brow_face, "R"))
    assert left.control_matrix[:3] == pytest.approx([1, 0, 0], abs=1e-6)
    # X from the inner to the outer end on both sides
    assert right.control_matrix[:3] == pytest.approx([-1, 0, 0], abs=1e-6)
    right = brow_solver.solve(_settings(brow_face, "R", mirrorBehavior=False))
    assert right.control_matrix == right.rig_matrix


def test_front_point(brow_face):
    from mgear.core.facial import brow_solver

    g = brow_solver.solve(_settings(brow_face, "L"), front=(0.5, 0.3, 10))
    direction = [v - c for v, c in zip((0.5, 0.3, 10), g.frame["center"])]
    length = math.sqrt(sum(v * v for v in direction))
    assert list(g.frame["normal"]) == pytest.approx(
        [v / length for v in direction], abs=1e-6
    )


@pytest.mark.parametrize(
    "change, message",
    [
        ({"vertexLoop": ""}, "Set the brow vertex path"),
        ({"vertexLoop": "nope.vtx[1:3]"}, "doesn't exist"),
    ],
)
def test_solve_errors(brow_face, change, message):
    from mgear.core.facial import brow_solver

    with pytest.raises(ValueError, match=message):
        brow_solver.solve(_settings(brow_face, "L", **change))


def test_closed_loop_error(lips_face):
    from mgear.core import settings_schema
    from mgear.core.facial import brow_schema
    from mgear.core.facial import brow_solver

    settings = settings_schema.defaults(brow_schema.SCHEMA)
    settings["vertexLoop"] = lips_face["vertex_loop"]
    with pytest.raises(ValueError, match="open path"):
        brow_solver.solve(settings_schema.coerce(settings, brow_schema.SCHEMA))


def test_detection_selection(brow_face):
    from mgear.core.facial import brow_solver

    g = brow_solver.solve(_settings(brow_face, "R"))
    assert brow_solver.detection_selection(g) == [
        "{}.vtx[{}]".format(brow_face["mesh"], brow_face["R"]["vertices"][0])
    ]


# ----------------------------------------------------------------------
# builder


def _build(face, brow="L", **kwargs):
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    kwargs.setdefault("vertexLoop", face[brow]["vertex_loop"])
    kwargs.setdefault("headJnt", face["head_jnt"])
    kwargs.setdefault("doSkin", False)
    return brow_rigger.rig(**kwargs)


def _position(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def _joints(prefix="brow", side="L"):
    from maya import cmds

    def index(name):
        return int(name.split("_")[1][1:])

    return sorted(cmds.ls("{}_{}*_brow_jnt".format(prefix, side)), key=index)


def _ctl(name, side="L", prefix="brow"):
    return "{}_{}_{}_ctl".format(prefix, side, name)


def test_builder_uses_backend(brow_face):
    from mgear.core.facial import brow_solver
    from mgear.core.facial._brow_build import BrowBuilder
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
            self.joints.append(idx)
            return super(RecordingBackend, self).add_deform_joint(
                driver, name, idx, parent
            )

    settings = _settings(brow_face, "L")
    geometry = brow_solver.solve(settings)
    backend = RecordingBackend("brow", "L")
    builder = BrowBuilder(settings, geometry, backend)
    builder.build_objects()
    builder.build_attributes()
    builder.build_operators()
    assert sorted(backend.ctls) == sorted(
        ["brow", "in", "mid01", "out", "in_tangent", "out_tangent"]
        + ["sec{:02d}".format(i) for i in range(5)]
    )
    assert backend.joints == list(range(7))


def test_rest_pose(brow_face):
    from mgear.core import meshNavigation
    from mgear.core import vector

    _build(brow_face, "L")
    points = meshNavigation.get_vertex_world_positions(
        brow_face["mesh"], brow_face["L"]["vertices"]
    )
    for joint, point in zip(_joints(), points):
        assert vector.distance(_position(joint), point) < 1e-3


def test_squeeze(brow_face):
    from maya import cmds
    from mgear.core.facial import brow_solver

    _build(brow_face, "L")
    length = brow_solver.solve(_settings(brow_face, "L")).length
    rest = {name: _position(_ctl(name)) for name in ("in", "mid01", "out")}
    joints = _joints()
    joint_rest = _position(joints[1])
    cmds.setAttr(_ctl("brow") + ".squeeze", 1)
    moved = _position(_ctl("in"))
    # the inner control slides toward the head center by 0.3 x length
    assert moved[0] == pytest.approx(rest["in"][0] - 0.3 * length, abs=1e-3)
    assert _position(_ctl("out")) == pytest.approx(rest["out"], abs=1e-5)
    assert _position(joints[1])[0] < joint_rest[0] - 0.01


def test_center_hooks(brow_face):
    from maya import cmds

    _build(brow_face, "L")
    _build(brow_face, "R")
    _build(brow_face, "C", hookLeft=_ctl("in"), hookRight=_ctl("in", "R"))
    assert not cmds.objExists(_ctl("out_L", "C"))
    center = _joints(side="C")
    rest_left = _position(center[-1])
    rest_right = _position(center[0])
    rest_brow = _position(_ctl("brow", "C"))
    cmds.setAttr(_ctl("in") + ".ty", 0.1)
    assert _position(center[-1])[1] == pytest.approx(rest_left[1] + 0.1, abs=1e-3)
    assert _position(center[0]) == pytest.approx(rest_right, abs=1e-4)
    # the center brow control stays halfway between both inner controls
    assert _position(_ctl("brow", "C"))[1] == pytest.approx(
        rest_brow[1] + 0.05, abs=1e-4
    )
    cmds.setAttr(_ctl("in", "R") + ".ty", 0.1)
    assert _position(_ctl("brow", "C"))[1] == pytest.approx(
        rest_brow[1] + 0.1, abs=1e-4
    )


def _surface_distance(face, point):
    from mgear.core import surface

    closest, normal, _, _ = surface.get_closest_point_normal(face["surface"], point)
    return sum((point[i] - closest[i]) * normal[i] for i in range(3))


def test_slide_surface(brow_face):
    from maya import cmds

    _build(brow_face, "L", slideSurface=brow_face["surface"])
    slider = "brow_L_mid01_slide"
    rest = _surface_distance(brow_face, _position(slider))
    rest_position = _position(slider)
    cmds.setAttr(_ctl("mid01") + ".tx", 0.3)
    # the control moved in a straight line, the slider follows the skull
    assert _surface_distance(brow_face, _position(slider)) == pytest.approx(
        rest, abs=1e-3
    )
    assert _position(slider)[2] < rest_position[2] - 0.01
    cmds.setAttr(_ctl("mid01") + ".surfaceOffset", 0.1)
    assert _surface_distance(brow_face, _position(slider)) == pytest.approx(
        rest + 0.1, abs=1e-3
    )


def test_slide_surface_rest(brow_face):
    _build(brow_face, "L")
    plain = [_position(j) for j in _joints()]
    _build(brow_face, "L", namePrefix="slid", slideSurface=brow_face["surface"])
    slid = [_position(j) for j in _joints("slid")]
    assert [v for p in slid for v in p] == pytest.approx(
        [v for p in plain for v in p], abs=1e-4
    )


def test_no_surface(brow_face):
    from maya import cmds

    _build(brow_face, "L")
    assert not cmds.ls(type="closestPointOnSurface")
    assert not cmds.attributeQuery("surfaceOffset", node=_ctl("mid01"), exists=True)


def test_joint_distribution(brow_face):
    from maya import cmds

    _build(brow_face, "L", everyNVertex=2)
    assert len(_joints()) == 4
    cmds.delete("brow_L_root", _joints())
    _build(brow_face, "L", fixedJoints=True, fixedJointsNumber=3)
    assert len(_joints()) == 3


def test_mirrored_brows(brow_face):
    from maya import cmds
    from mgear.core import string

    _build(brow_face, "L")
    _build(brow_face, "R")
    for side in "LR":
        cmds.setAttr(_ctl("in", side) + ".ty", 0.1)
        cmds.setAttr(_ctl("in", side) + ".tx", 0.05)
    left = _position(_ctl("in"))
    right = _position(_ctl("in", "R"))
    assert right == pytest.approx([-left[0], left[1], left[2]], abs=1e-5)
    controls = cmds.ls("brow_*_ctl", type="transform")
    for ctl in [c for c in controls if "_L_" in c]:
        assert string.convertRLName(ctl) in controls


def test_global_scale(brow_face):
    from maya import cmds

    root = _build(brow_face, "L")
    rest = {joint: _position(joint) for joint in _joints()}
    world = cmds.group(empty=True, name="world")
    cmds.parent(root.name(), brow_face["head_jnt"], world)
    cmds.setAttr(world + ".scale", 2, 2, 2)
    for joint, position in rest.items():
        assert _position(joint) == pytest.approx([v * 2 for v in position], abs=1e-3)


def test_secondary_visibility(brow_face):
    from maya import cmds

    _build(brow_face, "L")
    cmds.setAttr(_ctl("brow") + ".secondaryVis", False)
    for i in range(5):
        shape = cmds.listRelatives(_ctl("sec{:02d}".format(i)), shapes=True)[0]
        assert not cmds.getAttr(shape + ".visibility")
    shape = cmds.listRelatives(_ctl("mid01"), shapes=True)[0]
    assert cmds.getAttr(shape + ".visibility")


def test_no_secondary(brow_face):
    from maya import cmds

    _build(brow_face, "L", useSecondary=False)
    assert not cmds.ls("brow_L_sec*_ctl")
    assert len(_joints()) == 7


def test_autoskin(brow_face):
    from maya import cmds

    mesh = brow_face["mesh"]
    _build(brow_face, "L", doSkin=True)
    cluster = cmds.ls(cmds.listHistory(mesh), type="skinCluster")[0]
    influences = cmds.skinCluster(cluster, query=True, influence=True)
    joints = _joints()
    for joint in joints:
        assert joint in influences
    weight = cmds.skinPercent(
        cluster,
        "{}.vtx[{}]".format(mesh, brow_face["L"]["vertices"][3]),
        transform=joints[3],
        query=True,
    )
    assert weight == pytest.approx(1.0)


def test_global_scale_with_surface(brow_face):
    from maya import cmds

    root = _build(brow_face, "L", slideSurface=brow_face["surface"])
    rest = {joint: _position(joint) for joint in _joints()}
    world = cmds.group(empty=True, name="world")
    cmds.parent(root.name(), brow_face["head_jnt"], brow_face["surface"], world)
    cmds.setAttr(world + ".scale", 2, 2, 2)
    for joint, position in rest.items():
        assert _position(joint) == pytest.approx([v * 2 for v in position], abs=1e-3)


def test_main_offset_reaches_joints(brow_face):
    from maya import cmds

    # the secondary layer slides too: it keeps the main controls offset
    _build(brow_face, "L", slideSurface=brow_face["surface"])
    joint = _joints()[3]
    rest = _surface_distance(brow_face, _position(joint))
    cmds.setAttr(_ctl("mid01") + ".surfaceOffset", 0.1)
    # the main curve is a cubic CV curve: its points move less than the
    # control points
    main = _surface_distance(brow_face, _position(joint))
    assert rest + 0.03 < main < rest + 0.1 + 1e-3
    cmds.setAttr(_ctl("sec02") + ".surfaceOffset", 0.05)
    assert _surface_distance(brow_face, _position(joint)) > main + 0.01


def _rotation(node):
    from maya import cmds

    m = cmds.xform(node, query=True, worldSpace=True, matrix=True)
    return [m[i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)]


def test_joints_follow_curve(brow_face):
    from maya import cmds

    _build(brow_face, "L")
    joint = _joints()[3]
    rest = _rotation(joint)
    # the brow arcs up: the joint aims along the bent curve
    cmds.setAttr(_ctl("mid01") + ".ty", 0.2)
    assert _rotation(joint) != pytest.approx(rest, abs=1e-3)


def test_joints_translate_only(brow_face):
    from maya import cmds

    _build(brow_face, "L", jointsFollowCurve=False)
    joints = _joints()
    assert not cmds.ls("brow_L*_browUpv")
    rest = {joint: _rotation(joint) for joint in joints}
    rest_position = _position(joints[3])
    cmds.setAttr(_ctl("mid01") + ".ty", 0.2)
    # the joints move but keep their orientation
    assert _position(joints[3])[1] > rest_position[1] + 0.05
    for joint in joints:
        assert _rotation(joint) == pytest.approx(rest[joint], abs=1e-4)
    # all of them in the brow frame, which turns with the rig
    cmds.setAttr("brow_L_root.rotateY", 20)
    turned = _rotation(joints[3])
    assert turned[0] == pytest.approx(rest[joints[3]][0] * 0.9397, abs=1e-3)


def test_follow_row_visibility(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import brow_schema

    settings = settings_schema.defaults(brow_schema.SCHEMA)
    assert brow_schema.row_visibility(settings)["upvOffset"]
    settings["jointsFollowCurve"] = False
    assert not brow_schema.row_visibility(settings)["upvOffset"]
