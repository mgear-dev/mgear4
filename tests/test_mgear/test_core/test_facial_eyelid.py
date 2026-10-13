"""mgear.core.facial eyelid schema, solver and builder test"""

import math

import pytest


def _settings(face, side="L", loop_type="edge", **kwargs):
    from mgear.core import settings_schema
    from mgear.core.facial import eyelid_schema

    data = settings_schema.defaults(eyelid_schema.SCHEMA)
    data["eyeMesh"] = face[side]["eyeball"]
    data["loopType"] = eyelid_schema.LOOP_TYPES.index(loop_type)
    data["edgeLoop"] = face[side]["edge_loop"]
    data["vertexLoop"] = face[side]["vertex_loop"]
    data.update(kwargs)
    return settings_schema.coerce(data, eyelid_schema.SCHEMA)


def test_schema_scopes(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import eyelid_schema

    defaults = settings_schema.defaults(eyelid_schema.SCHEMA)
    shared = settings_schema.filter_scope(defaults, eyelid_schema.SCHEMA, "shared")
    for key in ("edgeLoop", "vertexLoop", "intCorner", "upperVTrack", "doSkin"):
        assert key in shared
    for key in ("namePrefix", "ctlSet", "headJnt", "aim_controller"):
        assert key not in shared
    assert defaults["mirrorBehavior"] is True
    assert defaults["simplified"] is True
    assert eyelid_schema.LOOP_TYPES[defaults["loopType"]] == "vertex"
    for param in eyelid_schema.SCHEMA:
        assert param.tooltip, param.key


def test_legacy_loop_type(setup_path):
    from mgear.core.facial import eyelid_schema

    edge = eyelid_schema.LOOP_TYPES.index("edge")
    legacy = eyelid_schema.legacy_loop_type({"edgeLoop": "m.e[1]"})
    assert legacy["loopType"] == edge
    # 2.1 settings keep the full controls, 3.0 ones default to simplified
    assert legacy["simplified"] is False
    assert "simplified" not in eyelid_schema.legacy_loop_type(
        {"vertexLoop": "m.vtx[1]"}
    )
    assert eyelid_schema.legacy_loop_type({"edgeLoop": "m.e[1]", "simplified": True})[
        "simplified"
    ]
    # explicit or vertex settings are left alone
    assert "loopType" not in eyelid_schema.legacy_loop_type({"vertexLoop": "m.vtx[1]"})
    assert (
        eyelid_schema.legacy_loop_type({"edgeLoop": "m.e[1]", "loopType": 1})[
            "loopType"
        ]
        == 1
    )


def test_select_joint_indices(setup_path):
    from mgear.core.facial._eyelid_build import select_joint_indices

    assert select_joint_indices(5) == [(i, i) for i in range(5)]
    assert select_joint_indices(7, every_n=3) == [(0, 0), (3, 3), (6, 6)]
    assert select_joint_indices(7, every_n=0) == [(i, i) for i in range(7)]
    assert select_joint_indices(9, fixed=True, fixed_number=5) == [
        (0, 0),
        (2, 1),
        (4, 2),
        (6, 3),
        (8, 4),
    ]
    # the lower lid never gets the corner points
    lower = select_joint_indices(9, fixed=True, fixed_number=5, skip_ends=True)
    assert lower == [(2, 0), (4, 1), (6, 2)]
    assert select_joint_indices(5, skip_ends=True) == [(1, 1), (2, 2), (3, 3)]
    assert len(select_joint_indices(4, fixed=True, fixed_number=10)) == 4


def test_edge_and_vertex_input_agree(eye_face):
    from mgear.core.facial import eyelid_solver

    edge = eyelid_solver.solve(_settings(eye_face, "L", "edge"))
    vertex = eyelid_solver.solve(_settings(eye_face, "L", "vertex"))
    assert edge.in_vertex == vertex.in_vertex
    assert edge.out_vertex == vertex.out_vertex
    assert edge.upper == vertex.upper
    assert edge.lower == vertex.lower
    assert edge.side == "L"
    # inner corner is the medial one, both lids run inner to outer
    assert edge.upper_points[0][0] < edge.upper_points[-1][0]
    assert edge.upper[0] == edge.lower[0] == edge.in_vertex
    assert edge.upper[-1] == edge.lower[-1] == edge.out_vertex
    assert sum(p[1] for p in edge.upper_points) > sum(p[1] for p in edge.lower_points)
    assert len(edge.upper) + len(edge.lower) - 2 == len(edge.loop)


def test_left_right_mirror(eye_face):
    from mgear.core import meshNavigation
    from mgear.core.facial import eyelid_solver

    left = eyelid_solver.solve(_settings(eye_face, "L"))
    right = eyelid_solver.solve(_settings(eye_face, "R"))
    assert right.side == "R"
    assert right.mirrored and not left.mirrored
    mirror = meshNavigation.get_mirror_vertex_indices(eye_face["mesh"], left.upper)
    assert right.upper == mirror
    mirror = meshNavigation.get_mirror_vertex_indices(eye_face["mesh"], left.lower)
    assert right.lower == mirror
    # mirrored control space: X runs inner to outer on both sides
    assert left.control_matrix[0] == pytest.approx(1.0, abs=1e-6)
    assert right.control_matrix[0] == pytest.approx(-1.0, abs=1e-6)
    assert right.rig_matrix[0] == pytest.approx(1.0, abs=1e-6)
    unmirrored = eyelid_solver.solve(_settings(eye_face, "R", mirrorBehavior=False))
    assert unmirrored.control_matrix[0] == pytest.approx(1.0, abs=1e-6)


def test_side_facing_eye(eye_face):
    from maya import cmds
    from mgear.core.facial import eyelid_solver

    reference = eyelid_solver.solve(_settings(eye_face, "L"))
    group = cmds.group(eye_face["mesh"], eye_face["L"]["eyeball"])
    cmds.setAttr(group + ".rotateY", 60)
    rotated = eyelid_solver.solve(_settings(eye_face, "L"))
    assert rotated.upper == reference.upper
    assert rotated.lower == reference.lower


def test_custom_corners(eye_face):
    from mgear.core import meshNavigation
    from mgear.core.facial import eyelid_solver

    loop = eyelid_solver.solve(_settings(eye_face, "L")).loop
    in_vertex, out_vertex = loop[2], loop[12]
    geometry = eyelid_solver.solve(
        _settings(
            eye_face,
            "L",
            customCorner=True,
            intCorner="{}.vtx[{}]".format(eye_face["mesh"], in_vertex),
            extCorner="{}.vtx[{}]".format(eye_face["mesh"], out_vertex),
        )
    )
    assert geometry.in_vertex == in_vertex
    assert geometry.out_vertex == out_vertex
    assert geometry.upper[0] == geometry.lower[0] == in_vertex
    with pytest.raises(ValueError):
        eyelid_solver.solve(
            _settings(
                eye_face,
                "L",
                customCorner=True,
                intCorner="{}.vtx[0]".format(eye_face["mesh"]),
                extCorner="{}.vtx[{}]".format(eye_face["mesh"], out_vertex),
            )
        )


def test_solver_errors(eye_face):
    from mgear.core.facial import eyelid_solver

    with pytest.raises(ValueError):
        eyelid_solver.solve(_settings(eye_face, "L", edgeLoop=""))
    with pytest.raises(ValueError):
        eyelid_solver.solve(_settings(eye_face, "L", eyeMesh="missing"))
    open_path = _settings(eye_face, "L", "vertex")
    vertices = eye_face["L"]["vertices"]
    from mgear.core import meshNavigation

    ordered, _ = meshNavigation.get_ordered_loop(eye_face["mesh"], vertices, "vertex")
    open_path["vertexLoop"] = meshNavigation.format_component_string(
        eye_face["mesh"], "vertex", ordered[:10]
    )
    with pytest.raises(ValueError):
        eyelid_solver.solve(open_path)


def test_solver_changes_nothing(eye_face):
    from maya import cmds
    from mgear.core.facial import eyelid_solver

    before = sorted(cmds.ls())
    eyelid_solver.solve(_settings(eye_face, "R", "vertex"))
    assert sorted(cmds.ls()) == before


def test_base_backend_is_abstract(setup_path):
    from mgear.core.facial.backend import BaseBackend

    backend = BaseBackend()
    with pytest.raises(NotImplementedError):
        backend.name("x")
    with pytest.raises(NotImplementedError):
        backend.add_deform_joint(None, "jnt")
    with pytest.raises(NotImplementedError):
        backend.root


def test_builder_uses_backend(eye_face):
    from mgear.core.facial import eyelid_solver
    from mgear.core.facial._eyelid_build import EyelidBuilder
    from mgear.rigbits.facial_rigger3.tool_backend import ToolBackend

    class RecordingBackend(ToolBackend):
        def __init__(self, *args, **kwargs):
            super(RecordingBackend, self).__init__(*args, **kwargs)
            self.ctls = []
            self.joints = []

        def add_ctl(self, parent, name, *args, **kwargs):
            self.ctls.append(name)
            return super(RecordingBackend, self).add_ctl(parent, name, *args, **kwargs)

        def add_deform_joint(self, driver, name, idx=None):
            self.joints.append((name, idx))
            return super(RecordingBackend, self).add_deform_joint(driver, name, idx)

    settings = _settings(eye_face, "L", simplified=False)
    geometry = eyelid_solver.solve(settings)
    backend = RecordingBackend("eye", geometry.side)
    builder = EyelidBuilder(settings, geometry, backend)
    builder.build_objects()
    builder.build_attributes()
    builder.build_operators()
    builder.connect_tracking(builder.aim_ctl)
    assert sorted(backend.ctls) == sorted(
        [
            "aim",
            "upBlink",
            "lowBlink",
            "inCorner",
            "outCorner",
            "upInMid",
            "upMid",
            "upOutMid",
            "lowInMid",
            "lowMid",
            "lowOutMid",
        ]
    )
    upper = [idx for name, idx in backend.joints if name == "upEyelid_jnt"]
    lower = [idx for name, idx in backend.joints if name == "lowEyelid_jnt"]
    assert len(upper) == len(geometry.upper)
    assert len(lower) == len(geometry.lower) - 2
    assert ("center_jnt", None) in backend.joints


def test_external_tracking(eye_face):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.core.facial import eyelid_solver
    from mgear.core.facial._eyelid_build import EyelidBuilder
    from mgear.rigbits.facial_rigger3.tool_backend import ToolBackend

    settings = _settings(eye_face, "L", trackingSource=1)
    geometry = eyelid_solver.solve(settings)
    backend = ToolBackend("eye", geometry.side)
    builder = EyelidBuilder(settings, geometry, backend)
    builder.build_objects()
    builder.build_attributes()
    builder.build_operators()
    assert builder.aim_ctl is None
    aim = pm.PyNode(cmds.createNode("transform", name="eye_aim"))
    cmds.xform("eye_aim", worldSpace=True, translation=geometry.eye_center)
    builder.connect_tracking(aim, add_center_joint=False)
    assert builder.center_joint is None
    level = builder.track_levels[0]
    assert level.attr("ty").get() == pytest.approx(0.0, abs=1e-6)
    # look up: Z turns toward +Y
    cmds.setAttr("eye_aim.rotateX", -20)
    assert level.attr("ty").get() > 0.0


def test_solver_aim_override(eye_face):
    from mgear.core.facial import eyelid_solver

    settings = _settings(eye_face, "L", mirrorBehavior=True)
    reference = eyelid_solver.solve(settings)
    center = (1.0, 0.0, 0.75)
    # aim 0.3 in front of the loop center along +Z
    loop_center = reference.frame["center"]
    aim = (1.0, 0.0, loop_center[2] + 0.3)
    geometry = eyelid_solver.solve(settings, eye_center=center, aim=aim)
    assert geometry.frame["normal"] == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)
    assert geometry.offset == pytest.approx(0.3, abs=1e-6)
    assert geometry.aim_distance == pytest.approx(math.dist(center, aim))
    assert geometry.upper == reference.upper
    # no eyeball mesh needed with the guide center
    settings_no_mesh = dict(settings, eyeMesh="")
    assert eyelid_solver.solve(settings_no_mesh, eye_center=center, aim=aim).upper
    # aim behind the lid: no negative offset
    behind = eyelid_solver.solve(settings, eye_center=center, aim=(1.0, 0.0, 0.8))
    assert behind.offset == 0.0


def test_solver_side_facing_aim(eye_face):
    from maya import cmds
    from mgear.core.facial import eyelid_solver

    reference = eyelid_solver.solve(_settings(eye_face, "L"))
    group = cmds.group(eye_face["mesh"], eye_face["L"]["eyeball"])
    cmds.setAttr(group + ".rotateY", 60)
    center = cmds.xform(
        eye_face["L"]["eyeball"], query=True, worldSpace=True, translation=True
    )
    aim_locator = cmds.spaceLocator()[0]
    cmds.parent(aim_locator, group)
    cmds.setAttr(aim_locator + ".translate", 1, 0, 2)
    aim = cmds.xform(aim_locator, query=True, worldSpace=True, translation=True)
    geometry = eyelid_solver.solve(_settings(eye_face, "L"), eye_center=center, aim=aim)
    assert geometry.upper == reference.upper
    assert geometry.lower == reference.lower


def test_solver_side_override(eye_face):
    from mgear.core.facial import eyelid_solver

    geometry = eyelid_solver.solve(_settings(eye_face, "L"), side="R")
    assert geometry.side == "R"
    assert geometry.mirrored


def test_solver_without_overrides_unchanged(eye_face):
    from mgear.core.facial import eyelid_solver

    settings = _settings(eye_face, "L", offset=0.07)
    geometry = eyelid_solver.solve(settings)
    assert geometry.offset == pytest.approx(0.07)
    assert geometry.aim_distance == pytest.approx(geometry.eye_size / 1.7)


def test_row_visibility(setup_path):
    from mgear.core import settings_schema
    from mgear.core.facial import eyelid_schema

    settings = settings_schema.defaults(eyelid_schema.SCHEMA)
    settings["doSkin"] = False
    rows = eyelid_schema.row_visibility(settings)
    assert rows["vertexLoop"] and not rows["edgeLoop"]
    assert not rows["rigidLoops"] and not rows["falloffLoops"]
    assert not rows["intCorner"]
    assert rows["everyNVertex"] and not rows["fixedJointsNumber"]
    settings.update(loopType=0, customCorner=True, fixedJoints=True)
    rows = eyelid_schema.row_visibility(settings)
    assert rows["edgeLoop"] and rows["intCorner"] and rows["fixedJointsNumber"]
