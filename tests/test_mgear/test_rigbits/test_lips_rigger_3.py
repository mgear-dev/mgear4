"""Lips Rigger 3.0 tool test"""

import json

import pytest


def _kwargs(face, loop_type="vertex", **kwargs):
    data = {
        "loopType": loop_type,
        "vertexLoop": face["vertex_loop"],
        "edgeLoop": face["edge_loop"],
        "headJnt": face["head_jnt"],
        "jawJnt": face["jaw_jnt"],
        "doSkin": False,
    }
    data.update(kwargs)
    return data


def _joints(cmds, pattern):
    return cmds.ls(pattern, type="joint")


def _position(cmds, node):
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def test_build_from_vertex_loop(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    root = lips.rig(**_kwargs(lips_face))
    assert root.name() == "lips_C_root"
    assert len(cmds.ls("lips_C_*_ctl", type="transform")) == 12
    assert len(_joints(cmds, "lips_C*_upLip_jnt")) == 11
    assert len(_joints(cmds, "lips_C*_lowLip_jnt")) == 9
    for name in ("corner_L", "corner_R"):
        for attr in ("jawFollow", "zipper"):
            assert cmds.objExists("lips_C_{}_ctl.{}".format(name, attr))
    for attr in ("roll", "zipperHeight", "secondaryVis"):
        assert cmds.objExists("lips_C_upper_ctl." + attr)
    assert cmds.objExists("lips_C_lower_ctl.roll")


def test_edge_loop_matches_vertex_loop(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    lips.rig(**_kwargs(lips_face, "vertex"))
    vertex = [_position(cmds, j) for j in _joints(cmds, "lips_C*_upLip_jnt")]
    lips.rig(**_kwargs(lips_face, "edge", namePrefix="lipsB"))
    edge = [_position(cmds, j) for j in _joints(cmds, "lipsB_C*_upLip_jnt")]
    assert [v for p in edge for v in p] == pytest.approx(
        [v for p in vertex for v in p], abs=1e-6
    )


def test_existing_root_guard(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    assert lips.rig(**_kwargs(lips_face)) is not None
    count = len(cmds.ls())
    assert lips.rig(**_kwargs(lips_face)) is None
    assert len(cmds.ls()) == count


def test_invalid_settings(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    count = len(cmds.ls())
    assert lips.rig(**_kwargs(lips_face, vertexLoop="")) is None
    assert lips.rig(**_kwargs(lips_face, jawJnt="missing_jnt")) is None
    assert lips.rig(**_kwargs(lips_face, namePrefix="")) is None
    assert len(cmds.ls()) == count


def test_two_prefixes(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    lips.rig(**_kwargs(lips_face))
    first = set(cmds.ls(type=("transform", "joint")))
    assert lips.rig(**_kwargs(lips_face, namePrefix="lipsB")) is not None
    second = set(cmds.ls(type=("transform", "joint"))) - first
    assert len(second) == len([n for n in first if n.startswith("lips_")])
    assert all(name.split("|")[-1].startswith("lipsB_") for name in second)


def test_rotated_head(lips_face):
    from maya import cmds
    from mgear.core.facial import lips_solver
    from mgear.rigbits.facial_rigger3 import lips

    cmds.setAttr(lips_face["mesh"] + ".rotate", 30, 30, 0)
    lips.rig(**_kwargs(lips_face))
    geometry = lips_solver.solve(lips.get_settings(**_kwargs(lips_face)))
    for name, points in (("corner_R", 0), ("corner_L", -1)):
        corner = geometry.upper_curve_points[points]
        assert _position(cmds, "lips_C_{}_ctl".format(name)) == pytest.approx(
            list(corner), abs=1e-3
        )


def test_settings_file_round_trip(lips_face, tmp_path):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    path = str(tmp_path / "mouth.lips")
    settings = lips.get_settings(**_kwargs(lips_face, everyNVertex=2))
    lips.save_settings(path, settings)
    assert lips.load_settings(path) == settings
    assert lips.rig_from_file(path) is not None
    assert len(_joints(cmds, "lips_C*_upLip_jnt")) == 6


def test_1_0_file_in_3_0(lips_face, tmp_path, count_calls):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.rigbits.facial_rigger3 import lips

    warnings = count_calls(pm, "displayWarning", lambda args, kwargs: args[0])
    # a Lips Rigger 1.0 export
    data = {
        "edge_loop": lips_face["edge_loop"],
        "up_vertex": "mouth.vtx[1]",
        "low_vertex": "mouth.vtx[2]",
        "name_prefix": "mouth",
        "thickness": 0.03,
        "do_skin": False,
        "rigid_loops": 5,
        "falloff_loops": 8,
        "head_joint": lips_face["head_jnt"],
        "jaw_joint": lips_face["jaw_jnt"],
        "parent_node": None,
        "control_name": "ctl",
        "upper_lip_ctl": None,
        "lower_lip_ctl": None,
    }
    path = str(tmp_path / "old.lips")
    with open(path, "w") as f:
        json.dump(data, f)
    assert lips.rig_from_file(path) is not None
    assert cmds.objExists("mouth_C_corner_L_ctl")
    assert any("up_vertex" in warning for warning in warnings)


def test_files_dispatch(lips_face, tmp_path):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import files
    from mgear.rigbits.facial_rigger3 import lips

    path = str(tmp_path / "lips.json")
    lips.save_settings(path, lips.get_settings(**_kwargs(lips_face)))
    assert files.rigger_for_file(path) is lips
    assert files.rig_from_file(path) is not None
    legacy = str(tmp_path / "legacy.lips")
    with open(legacy, "w") as f:
        json.dump({"edge_loop": lips_face["edge_loop"]}, f)
    assert files.rigger_for_file(legacy) is lips
    assert cmds.objExists("lips_C_root")
    assert ".lips" in files.FILE_FILTER


def test_check_detection(lips_face):
    from maya import cmds
    from mgear.core import meshNavigation
    from mgear.core.facial import lips_solver
    from mgear.rigbits.facial_rigger3 import lips

    count = len(cmds.ls())
    for invert in (False, True):
        geometry = lips.check_detection(**_kwargs(lips_face, invertLips=invert))
        _, _, selected = meshNavigation.parse_component_string(
            meshNavigation.components_from_selection("vertex")
        )
        assert sorted(selected) == sorted(geometry.upper)
    assert len(cmds.ls()) == count
    rest = lips_solver.solve(lips.get_settings(**_kwargs(lips_face)))
    assert sorted(selected) == sorted(rest.lower)


def test_invert_lips_build(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    lips.rig(**_kwargs(lips_face, invertLips=True))
    # the upper lip controls sit on the lower lip
    assert _position(cmds, "lips_C_upper_ctl")[1] < 0
    assert _position(cmds, "lips_C_lower_ctl")[1] > 0


def test_1_0_tool_unchanged(setup_path):
    from mgear.rigbits import menu
    from mgear.rigbits.facial_rigger import lips_rigger

    assert lips_rigger.rig.__module__ == "mgear.rigbits.facial_rigger.lips_rigger"
    assert "facial_rigger.show()" in menu.str_facial_rigger


def test_mouth_front_node(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import lips

    cmds.setAttr(lips_face["mesh"] + ".rotateY", 40)
    front = cmds.spaceLocator(name="mouth_front")[0]
    cmds.setAttr(front + ".translate", 5 * 0.6428, 0, 5 * 0.766)
    lips.rig(**_kwargs(lips_face, frontNode=front))
    m = cmds.xform("lips_C_upper_ctl", query=True, worldSpace=True, matrix=True)
    assert m[8:11] == pytest.approx([0.6428, 0, 0.766], abs=0.01)
    assert lips.rig(**_kwargs(lips_face, namePrefix="b", frontNode="missing")) is None
