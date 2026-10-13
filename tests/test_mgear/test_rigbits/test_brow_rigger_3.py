"""Brow Rigger 3.0 tool test"""

import json
import math

import pytest


def _kwargs(face, brow="L", **kwargs):
    data = {
        "vertexLoop": face[brow]["vertex_loop"],
        "edgeLoop": face[brow]["edge_loop"],
        "headJnt": face["head_jnt"],
        "doSkin": False,
    }
    data.update(kwargs)
    return data


def _position(cmds, node):
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


@pytest.mark.parametrize("brow", ["L", "R", "C"])
def test_build_one_brow(brow_face, brow):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    root = brow_rigger.rig(**_kwargs(brow_face, brow))
    assert root.name() == "brow_{}_root".format(brow)
    controls = cmds.ls("brow_{}_*_ctl".format(brow), type="transform")
    # whole brow, 3 main, 2 tangents and 5 secondary controls
    assert len(controls) == 11
    joints = cmds.ls("brow_{}*_brow_jnt".format(brow), type="joint")
    assert len(joints) == len(brow_face[brow]["vertices"])
    assert root.getParent() is None


def test_closed_loop(lips_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    count = len(cmds.ls())
    assert brow_rigger.rig(vertexLoop=lips_face["vertex_loop"]) is None
    assert len(cmds.ls()) == count


def test_existing_root_and_missing_nodes(brow_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    assert brow_rigger.rig(**_kwargs(brow_face)) is not None
    count = len(cmds.ls())
    assert brow_rigger.rig(**_kwargs(brow_face)) is None
    assert brow_rigger.rig(**_kwargs(brow_face, namePrefix="b", hookLeft="no")) is None
    assert (
        brow_rigger.rig(**_kwargs(brow_face, namePrefix="b", slideSurface="no")) is None
    )
    assert len(cmds.ls()) == count


def test_rotated_head_with_brow_front(brow_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    world = cmds.group(empty=True, name="head_space")
    cmds.parent(brow_face["mesh"], world)
    cmds.setAttr(world + ".rotateY", 30)
    angle = math.radians(30)
    front = cmds.spaceLocator(name="brow_front")[0]
    cmds.setAttr(front + ".translate", 5 * math.sin(angle), 0.3, 5 * math.cos(angle))
    brow_rigger.rig(**_kwargs(brow_face, frontNode=front))
    m = cmds.xform("brow_L_brow_ctl", query=True, worldSpace=True, matrix=True)
    # the brow faces the locator from the brow path center
    points = [
        cmds.pointPosition("{}.vtx[{}]".format(brow_face["mesh"], v), world=True)
        for v in brow_face["L"]["vertices"]
    ]
    center = [sum(p[i] for p in points) / len(points) for i in range(3)]
    direction = [v - c for v, c in zip(_position(cmds, front), center)]
    length = math.sqrt(sum(v * v for v in direction))
    assert m[8:11] == pytest.approx([v / length for v in direction], abs=1e-3)
    # the inner end is still the inner vertex
    inner = cmds.pointPosition(
        "{}.vtx[{}]".format(brow_face["mesh"], brow_face["L"]["vertices"][0]),
        world=True,
    )
    assert _position(cmds, "brow_L0_brow_jnt") == pytest.approx(list(inner), abs=1e-3)


def test_1_0_file(brow_face, tmp_path, count_calls):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    warnings = count_calls(pm, "displayWarning", lambda args, kwargs: args[0])
    data = {
        "edge_loop": brow_face["L"]["edge_loop"],
        "name_prefix": "oldBrow",
        "thickness": 0.0,
        "main_div": 4,
        "sec_div": 5,
        "do_skin": False,
        "secondary_ctl_check": True,
        "symmetry_mode": 0,
        "side": 1,
        "rigid_loops": 1,
        "falloff_loops": 2,
        "brow_jnt_C": brow_face["head_jnt"],
        "brow_jnt_L": "",
        "brow_jnt_R": "",
        "ctl_parent_C": "",
        "ctl_parent_L": "",
        "ctl_parent_R": "",
        "parent_node": None,
        "ctl_name": "ctl",
    }
    path = str(tmp_path / "old.brows")
    with open(path, "w") as f:
        json.dump(data, f)
    assert brow_rigger.rig_from_file(path) is not None
    assert cmds.objExists("oldBrow_L_mid02_ctl")
    assert any("symmetry_mode" in warning for warning in warnings)


def test_files_dispatch(brow_face, tmp_path):
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger
    from mgear.rigbits.facial_rigger3 import files

    path = str(tmp_path / "brow.json")
    brow_rigger.save_settings(path, brow_rigger.get_settings(**_kwargs(brow_face)))
    assert files.rigger_for_file(path) is brow_rigger
    assert files.rig_from_file(path) is not None
    legacy = str(tmp_path / "legacy.brows")
    with open(legacy, "w") as f:
        json.dump({"edge_loop": brow_face["R"]["edge_loop"]}, f)
    assert files.rigger_for_file(legacy) is brow_rigger
    assert ".brows" in files.FILE_FILTER


def test_check_detection(brow_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import brow as brow_rigger

    count = len(cmds.ls())
    geometry = brow_rigger.check_detection(**_kwargs(brow_face, "R"))
    assert geometry.side == "R"
    assert cmds.ls(selection=True, flatten=True) == [
        "{}.vtx[{}]".format(brow_face["mesh"], brow_face["R"]["vertices"][0])
    ]
    assert len(cmds.ls()) == count


def test_1_0_tool_unchanged(setup_path):
    from mgear.rigbits import menu
    from mgear.rigbits.facial_rigger import brow_rigger

    assert brow_rigger.rig.__module__ == "mgear.rigbits.facial_rigger.brow_rigger"
    assert "facial_rigger.show()" in menu.str_facial_rigger
