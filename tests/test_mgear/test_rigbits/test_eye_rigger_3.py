"""Eye Rigger 3.0 (mgear.rigbits.facial_rigger3.eye) build test"""

import json

import pytest


def _kwargs(face, side="L", loop_type="edge", **kwargs):
    data = {
        "eyeMesh": face[side]["eyeball"],
        "headJnt": face["head_jnt"],
        "doSkin": False,
    }
    if loop_type == "edge":
        data["edgeLoop"] = face[side]["edge_loop"]
    else:
        data["loopType"] = 1
        data["vertexLoop"] = face[side]["vertex_loop"]
    data.update(kwargs)
    return data


def _position(cmds, node):
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def _joints(cmds, pattern):
    return sorted(
        cmds.ls(pattern, type="joint"),
        key=lambda name: int("".join(c for c in name.split("_")[1] if c.isdigit())),
    )


def test_build_from_edge_loop(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    root = eye.rig(**_kwargs(eye_face, simplified=False))
    assert root.name() == "eye_L_root"
    for name in (
        "eye_L_aim_ctl",
        "eye_L_upBlink_ctl",
        "eye_L_lowBlink_ctl",
        "eye_L_inCorner_ctl",
        "eye_L_outCorner_ctl",
        "eye_L_upInMid_ctl",
        "eye_L_upMid_ctl",
        "eye_L_upOutMid_ctl",
        "eye_L_lowInMid_ctl",
        "eye_L_lowMid_ctl",
        "eye_L_lowOutMid_ctl",
        "eye_L_center_jnt",
    ):
        assert cmds.objExists(name), name
    upper = _joints(cmds, "eye_L*_upEyelid_jnt")
    lower = _joints(cmds, "eye_L*_lowEyelid_jnt")
    assert len(upper) == 11
    assert len(lower) == 9
    for joint in upper + lower:
        assert cmds.listRelatives(joint, parent=True) == ["head_jnt"]
    members = cmds.sets("rig_controllers_grp", query=True)
    assert "eye_L_upMid_ctl" in members
    assert cmds.getAttr("eye_L_upMid_ctl.isCtl") is False


def test_vertex_loop_matches_edge_loop(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, namePrefix="edge", simplified=False))
    eye.rig(**_kwargs(eye_face, loop_type="vertex", namePrefix="vtx", simplified=False))
    for edge_name in _joints(cmds, "edge_L*_upEyelid_jnt") + [
        "edge_L_upMid_ctl",
        "edge_L_outCorner_ctl",
    ]:
        vertex_name = edge_name.replace("edge_", "vtx_", 1)
        assert _position(cmds, vertex_name) == pytest.approx(
            _position(cmds, edge_name), abs=1e-5
        )


def test_rest_curve_on_loop(eye_face):
    import mgear.pymaya as pm
    from mgear.core.facial import eyelid_solver
    from mgear.rigbits.facial_rigger3 import eye

    settings = eye.get_settings(**_kwargs(eye_face))
    geometry = eyelid_solver.solve(settings)
    eye.rig(**settings)
    for name, points in (
        ("eye_L_upperEyelid", geometry.upper_points),
        ("eye_L_lowerEyelid", geometry.lower_points),
    ):
        cvs = pm.PyNode(name).getCVs(space="world")
        assert len(cvs) == len(points)
        for cv, point in zip(cvs, points):
            assert [cv[0], cv[1], cv[2]] == pytest.approx(list(point), abs=1e-3)


def test_full_blink_closes(eye_face):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face))
    rest = cmds.getAttr("eye_L_blink_drv.ty")
    assert rest < 0
    cmds.setAttr("eye_L_upBlink_ctl.ty", rest)
    up = pm.PyNode("eye_L_upDriver_crv").getCVs(space="world")
    low = pm.PyNode("eye_L_lowDriver_crv").getCVs(space="world")
    for a, b in zip(up, low):
        assert [a[0], a[1], a[2]] == pytest.approx([b[0], b[1], b[2]], abs=0.01)


def test_every_n_vertex_zero(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    assert eye.rig(**_kwargs(eye_face, everyNVertex=0)) is not None
    assert len(_joints(cmds, "eye_L*_upEyelid_jnt")) == 11


def test_fixed_joints_lower_lid(eye_face):
    from maya import cmds
    from mgear.core.facial import eyelid_solver
    from mgear.rigbits.facial_rigger3 import eye

    settings = eye.get_settings(
        **_kwargs(eye_face, fixedJoints=True, fixedJointsNumber=5)
    )
    geometry = eyelid_solver.solve(settings)
    eye.rig(**settings)
    upper = _joints(cmds, "eye_L*_upEyelid_jnt")
    lower = _joints(cmds, "eye_L*_lowEyelid_jnt")
    assert len(upper) == 5
    assert len(lower) == 3
    corners = [geometry.lower_points[0], geometry.lower_points[-1]]
    lower_positions = [_position(cmds, joint) for joint in lower]
    for position in lower_positions:
        assert any(
            position == pytest.approx(list(point), abs=1e-4)
            for point in geometry.lower_points[1:-1]
        )
        for corner in corners:
            assert position != pytest.approx(list(corner), abs=1e-4)
    # evenly spread: the middle lower joint sits on the middle point
    middle = geometry.lower_points[len(geometry.lower_points) // 2]
    assert lower_positions[1] == pytest.approx(list(middle), abs=1e-4)


def test_left_and_right_names(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, "L"))
    eye.rig(**_kwargs(eye_face, "R"))
    for side in "LR":
        for name in (
            "upBlink_blendShape",
            "closeTarget_blendShape",
            "upEyelid_wire",
            "vTrack_remap",
            "contact_div",
        ):
            assert cmds.objExists("eye_{}_{}".format(side, name))
    assert not cmds.ls("*blendShape1")


def test_mirrored_pose(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, "L"))
    eye.rig(**_kwargs(eye_face, "R"))
    for side in "LR":
        cmds.setAttr("eye_{}_upBlink_ctl.ty".format(side), -0.05)
        cmds.setAttr("eye_{}_outCorner_ctl.tx".format(side), 0.05)
    left = _joints(cmds, "eye_L*_upEyelid_jnt")
    right = _joints(cmds, "eye_R*_upEyelid_jnt")
    assert len(left) == len(right)
    for l_joint, r_joint in zip(left, right):
        x, y, z = _position(cmds, l_joint)
        assert _position(cmds, r_joint) == pytest.approx([-x, y, z], abs=1e-3)
    # outward on both sides
    assert _position(cmds, "eye_L_outCorner_ctl")[0] > 1.0
    assert _position(cmds, "eye_R_outCorner_ctl")[0] < -1.0


def test_autoskin(eye_face):
    from maya import cmds
    from mgear.core import skin
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, doSkin=True))
    skin_cluster = skin.getSkinCluster(eye_face["mesh"]).name()
    influences = cmds.skinCluster(skin_cluster, query=True, influence=True)
    for joint in _joints(cmds, "eye_L*_upEyelid_jnt"):
        assert joint in influences
    assert skin.getSkinCluster(eye_face["L"]["eyeball"]) is not None
    vertex = eye_face["L"]["vertices"][0]
    weights = cmds.skinPercent(
        skin_cluster,
        "{}.vtx[{}]".format(eye_face["mesh"], vertex),
        query=True,
        value=True,
    )
    assert max(weights) == pytest.approx(1.0)
    assert dict(zip(influences, weights))["head_jnt"] == pytest.approx(0.0)


def test_no_autoskin(eye_face):
    from mgear.core import skin
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, doSkin=False))
    assert skin.getSkinCluster(eye_face["mesh"]) is None


def test_existing_root_guard(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    assert eye.rig(**_kwargs(eye_face)) is not None
    count = len(cmds.ls())
    assert eye.rig(**_kwargs(eye_face)) is None
    assert len(cmds.ls()) == count


def test_aim_controller(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    aim = cmds.createNode("transform", name="eye_aim_ctl")
    cmds.setAttr(aim + ".translate", 1, 0, 0.75)
    eye.rig(**_kwargs(eye_face, aim_controller=aim))
    assert not cmds.objExists("eye_L_aim_ctl")
    assert cmds.objExists("eye_L_center_jnt")
    cmds.setAttr(aim + ".rotateX", -20)
    assert cmds.getAttr("eye_L_upMid_trk.ty") > 0


def test_settings_file_round_trip(eye_face, tmp_path):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    path = str(tmp_path / "left.eyes")
    settings = eye.get_settings(**_kwargs(eye_face, everyNVertex=2))
    eye.save_settings(path, settings)
    assert eye.load_settings(path) == settings
    eye.rig_from_file(path)
    assert len(_joints(cmds, "eye_L*_upEyelid_jnt")) == 6


def test_legacy_file(eye_face, tmp_path):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    data = _kwargs(eye_face)
    data.update({"blinkH": 20, "intCorner": None, "extCorner": None})
    path = str(tmp_path / "legacy.eyes")
    with open(path, "w") as f:
        json.dump(data, f)
    assert eye.rig_from_file(path) is not None
    assert cmds.objExists("eye_L_upBlink_ctl")


def test_2_1_entry_points_stay_on_2_1(eye_face, tmp_path, monkeypatch):
    from mgear.rigbits.facial_rigger2 import eye_rigger
    from mgear.rigbits.facial_rigger2 import eye_riggerUI
    from mgear.rigbits.facial_rigger3 import eye

    # old custom steps keep calling the Eye Rigger 2.1 rig, untouched
    assert eye_rigger.rig.__module__ == "mgear.rigbits.facial_rigger2.eye_rigger"
    assert eye_riggerUI.eye_rigger is eye_rigger
    calls = []
    monkeypatch.setattr(eye_rigger, "rig", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(eye, "rig", lambda **kwargs: calls.append("3.0"))
    data = dict(_kwargs(eye_face, "L"), blinkH=20)
    path = str(tmp_path / "left.eyes")
    with open(path, "w") as f:
        json.dump(data, f)
    eye_rigger.rig_from_file(path)
    assert calls == [data]


def test_2_1_file_in_3_0(eye_face, tmp_path, count_calls):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.rigbits.facial_rigger3 import eye

    warnings = count_calls(pm, "displayWarning", lambda args, kwargs: args[0])
    data = _kwargs(eye_face, "R")
    data["blinkH"] = 20
    path = str(tmp_path / "right.eyes")
    with open(path, "w") as f:
        json.dump(data, f)
    assert eye.rig_from_file(path) is not None
    assert cmds.objExists("eye_R_upBlink_blendShape")
    assert any("blinkH" in warning for warning in warnings)


def test_files_dispatch(eye_face, tmp_path):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye
    from mgear.rigbits.facial_rigger3 import files

    path = str(tmp_path / "eye.json")
    eye.save_settings(path, eye.get_settings(**_kwargs(eye_face, "L")))
    assert files.rigger_for_file(path) is eye
    assert files.rig_from_file(path) is not None
    legacy = str(tmp_path / "legacy.eyes")
    with open(legacy, "w") as f:
        json.dump(_kwargs(eye_face, "R"), f)
    assert files.rigger_for_file(legacy) is eye
    other = str(tmp_path / "other.json")
    with open(other, "w") as f:
        json.dump({"type": "lattice_io"}, f)
    with pytest.raises(ValueError):
        files.rigger_for_file(other)
    assert cmds.objExists("eye_L_root")


def test_custom_step_templates(setup_path):
    from mgear.shifter import custom_step_templates

    for key in ("import_eye_rigger_config", "import_facial_rigger3_config"):
        content = custom_step_templates.get_template_content(key, "facial")
        compile(content, key, "exec")
        assert 'self.name = "facial"' in content


def test_legacy_helpers_integer_slices(setup_path):
    from mgear.rigbits.facial_rigger import helpers as helpers_1
    from mgear.rigbits.facial_rigger2 import helpers as helpers_2

    controls = list("abcdefg")
    for helpers in (helpers_1, helpers_2):
        # the brow rigger passes float divisions from a double spin box
        left, right = helpers.excludeInbetweens(controls, 7.0)
        assert left == ["b", "c"]
        assert right == ["e", "f"]
        assert helpers.excludeParents(controls, 7.0) == ["a", "d", "g"]


def test_simplified_mode(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, simplified=True))
    for side in ("up", "low"):
        mid = "eye_L_{}Mid_lock".format(side)
        assert cmds.objExists(mid)
        assert not cmds.listRelatives(mid, shapes=True)
        assert not cmds.objExists("eye_L_{}Mid_ctl".format(side))
        blink = "eye_L_{}Blink_ctl".format(side)
        assert cmds.attributeQuery("hide_mid_ctl", node=blink, exists=True)
        cmds.setAttr(blink + ".verticalOffset", 0.1)
        assert cmds.getAttr(mid + ".ty") == pytest.approx(0.1)
    assert "eye_L_upMid_lock" not in cmds.sets("rig_controllers_grp", query=True)


def _driver_points(cmds):
    flat = []
    for name in ("eye_L_upDriver_crv", "eye_L_lowDriver_crv"):
        flat += cmds.xform(
            name + ".cv[*]", query=True, worldSpace=True, translation=True
        )
    return [flat[i : i + 3] for i in range(0, len(flat), 3)]


def test_contact_is_smooth(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face))
    rest = cmds.getAttr("eye_L_blink_drv.ty")
    previous = None
    largest = 0.0
    # close the upper lid down past contact in small steps. Eye Rigger 2.1
    # jumped about 0.09 at contact on this face.
    for step in range(81):
        cmds.setAttr("eye_L_upBlink_ctl.ty", rest * (0.8 + 0.4 * step / 80.0))
        points = _driver_points(cmds)
        if previous:
            largest = max(
                largest,
                max(
                    abs(a[i] - b[i]) for a, b in zip(points, previous) for i in range(3)
                ),
            )
        previous = points
    # no jump: steps stay in the order of the control step (0.4 * rest / 80)
    assert largest < abs(rest) * 0.02
    # touching, both lids are on the shared close shape
    up = points[: len(points) // 2]
    low = points[len(points) // 2 :]
    for a, b in zip(up, low):
        assert a == pytest.approx(b, abs=1e-3)


def test_aim_does_not_mirror(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face, "L"))
    eye.rig(**_kwargs(eye_face, "R"))
    left = cmds.xform("eye_L_aim_ctl", query=True, worldSpace=True, matrix=True)
    right = cmds.xform("eye_R_aim_ctl", query=True, worldSpace=True, matrix=True)
    assert right[:12] == pytest.approx(left[:12], abs=1e-5)
    for side in "LR":
        assert cmds.getAttr("eye_{}_aim_ctl.scale".format(side))[0] == (1, 1, 1)
        cmds.setAttr("eye_{}_aim_ctl.ry".format(side), 20)
    # the same rotation aims both eyes the same way: both lids move to +X
    for side in "LR":
        assert (
            cmds.getAttr("eye_{}_aimTrigger_ref.worldMatrix".format(side))[12]
            > _position(cmds, "eye_{}_aim_npo".format(side))[0]
        )


def test_legacy_order_from_center_dropped(eye_face, count_calls):
    from maya import cmds
    import mgear.pymaya as pm
    from mgear.rigbits.facial_rigger3 import eye

    warnings = count_calls(pm, "displayWarning", lambda args, kwargs: args[0])
    eye.rig(**_kwargs(eye_face, "R", orderFromCenter=True))
    assert any("orderFromCenter" in warning for warning in warnings)
    # numbered from the inner corner, like the left side
    first = _position(cmds, "eye_R0_upEyelid_jnt")
    last = _position(cmds, "eye_R10_upEyelid_jnt")
    assert first[0] > last[0]


def test_legacy_menu_entries(setup_path):
    from mgear.rigbits import menu

    assert "facial_rigger2.eye_riggerUI.show()" in menu.str_eye_rigger_21
    assert "facial_rigger.show()" in menu.str_facial_rigger
    assert "facial_rigger3.show()" in menu.str_facial_rigger3


def test_aim_mirror_flags(eye_face):
    from maya import cmds
    from mgear.rigbits.facial_rigger3 import eye

    eye.rig(**_kwargs(eye_face))
    assert cmds.getAttr("eye_L_aim_ctl.invRy")
    assert cmds.getAttr("eye_L_aim_ctl.invRz")
    assert not cmds.getAttr("eye_L_aim_ctl.invRx")
    assert not cmds.getAttr("eye_L_upBlink_ctl.invTy")
