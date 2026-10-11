"""Tests for mgear.core.mirror_config."""

import json
import math

import pytest

CENTER = "spine_C0_fk0_ctl"
LEFT = "arm_L0_fk0_ctl"
RIGHT = "arm_R0_fk0_ctl"


@pytest.fixture
def mirror_config(setup_path):
    """The mgear.core.mirror_config module, in a new Y-up scene."""
    from maya import cmds

    from mgear.core import mirror_config

    cmds.file(new=True, force=True)
    cmds.upAxis(axis="y")
    yield mirror_config
    cmds.upAxis(axis="y")


def _left_matrix():
    """World matrix of the left control buffer, rotated and off center."""
    import maya.api.OpenMaya as om2

    euler = om2.MEulerRotation(*[math.radians(v) for v in (10.0, 20.0, 30.0)])
    matrix = om2.MTransformationMatrix(euler.asMatrix())
    matrix.setTranslation(om2.MVector(4.0, 5.0, 6.0), om2.MSpace.kWorld)
    return matrix.asMatrix()


def _mirrored(matrix, flips=(1, 1, 1)):
    """Mirror a world matrix about world X, then flip local axes.

    Args:
        matrix (MMatrix): World matrix.
        flips (tuple): Sign of each local axis after the mirror. An odd
            number of -1 gives a proper frame (no negative scale).

    Returns:
        MMatrix: The mirrored matrix.
    """
    import maya.api.OpenMaya as om2

    mirror = om2.MMatrix(((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    local = om2.MMatrix(
        (
            (flips[0], 0, 0, 0),
            (0, flips[1], 0, 0),
            (0, 0, flips[2], 0),
            (0, 0, 0, 1),
        )
    )
    return local * matrix * mirror


def _control(cmds, name, matrix=None, parent=None, joint=False):
    """Create a control with a buffer at a world matrix, with inv attrs."""
    from mgear.core import attribute

    npo = cmds.createNode("transform", name=name.replace("_ctl", "_npo"))
    if parent:
        npo = cmds.parent(npo, parent)[0]
    if matrix is not None:
        cmds.xform(npo, matrix=list(matrix), worldSpace=True)
    if joint:
        ctl = cmds.createNode("joint", name=name, parent=npo)
    else:
        ctl = cmds.createNode("transform", name=name, parent=npo)
    attribute.add_mirror_config_channels(ctl)
    return cmds.ls(ctl, long=True)[0]


def _pair(cmds, flips=(1, 1, 1), parent=None, left=LEFT, right=RIGHT):
    """Create a left and right control, the right one mirrored."""
    matrix = _left_matrix()
    left_ctl = _control(cmds, left, matrix, parent)
    right_ctl = _control(cmds, right, _mirrored(matrix, flips), parent)
    return left_ctl, right_ctl


def _rig(cmds, controls):
    """Make a rig root with a controllers set holding the controls."""
    root = cmds.createNode("transform", name="rig")
    cmds.addAttr(root, longName="is_rig", attributeType="bool")
    names = [c.split("|")[-1] for c in controls]
    tops = dict.fromkeys(cmds.ls(c, long=True)[0].split("|")[1] for c in controls)
    cmds.parent(list(tops), root)
    cmds.sets(names, name="rig_controllers_grp")
    return root


def _on(flags):
    """Names of the inv attributes that are on."""
    return sorted(a for a, v in flags.items() if v)


def _record(analysis, name):
    """Get the analysis record of a control by its short name."""
    for record in analysis["controls"]:
        if record["name"] == name:
            return record
    raise KeyError(name)


# =============================================================================
# flags
# =============================================================================


def test_negative_scale_parent(mirror_config):
    from maya import cmds

    left, right = _pair(cmds)
    npo_scale = cmds.getAttr(right.rsplit("|", 1)[0] + ".scale")[0]
    assert npo_scale[0] * npo_scale[1] * npo_scale[2] < 0
    analysis = mirror_config.analyze([left, right], mode="selection")
    for name in (LEFT, RIGHT):
        record = _record(analysis, name)
        assert record["error"] < 1e-3
        assert _on(record["proposed"]) == []


def test_x_axis_flipped(mirror_config):
    from maya import cmds

    left, right = _pair(cmds, flips=(-1, 1, 1))
    analysis = mirror_config.analyze([left, right], mode="selection")
    for name in (LEFT, RIGHT):
        assert _on(_record(analysis, name)["proposed"]) == ["invRy", "invRz", "invTx"]


def test_all_axes_flipped(mirror_config):
    from maya import cmds

    left, right = _pair(cmds, flips=(-1, -1, -1))
    analysis = mirror_config.analyze([left, right], mode="selection")
    for name in (LEFT, RIGHT):
        assert _on(_record(analysis, name)["proposed"]) == ["invTx", "invTy", "invTz"]


def test_center_control(mirror_config):
    from maya import cmds

    ctl = _control(cmds, CENTER)
    cmds.setAttr(ctl.rsplit("|", 1)[0] + ".ty", 10)
    analysis = mirror_config.analyze([ctl], mode="selection")
    record = _record(analysis, CENTER)
    assert record["target"] == ctl
    assert _on(record["proposed"]) == ["invRy", "invRz", "invTx"]


def test_rotate_order_does_not_change_flags(mirror_config):
    from maya import cmds

    left, right = _pair(cmds, flips=(-1, 1, 1))
    expected = mirror_config.analyze([left], mode="selection")
    for ctl in (left, right):
        cmds.setAttr(ctl + ".rotateOrder", 2)  # zxy
    analysis = mirror_config.analyze([left], mode="selection")
    assert _record(analysis, LEFT)["proposed"] == _record(expected, LEFT)["proposed"]
    mirror_config.apply_config(mirror_config.config_from_analysis(analysis))
    mirror_config.apply_config(
        mirror_config.config_from_analysis(
            mirror_config.analyze([right], mode="selection")
        )
    )
    result = mirror_config.verify([left], mode="selection")[left]
    assert result["rotation_error"] < 0.01
    assert result["translation_error"] < 0.001


def test_joint_mirrored_with_behaviour(mirror_config):
    from maya import cmds

    from mgear.core import attribute

    # mirrorJoint mirrors about the parent's YZ plane, keep it on world X = 0
    group = cmds.createNode("transform", name="arm_L0_npo")
    cmds.xform(group, translation=(0, 4, 1), worldSpace=True)
    joint = cmds.createNode("joint", name=LEFT, parent=group)
    cmds.setAttr(joint + ".jointOrient", 15, -25, 40)
    cmds.setAttr(joint + ".translate", 2, 1, 0.5)
    cmds.mirrorJoint(
        joint, mirrorYZ=True, mirrorBehavior=True, searchReplace=("_L0_", "_R0_")
    )
    left = cmds.ls(LEFT, long=True)[0]
    right = cmds.ls(RIGHT, long=True)[0]
    for ctl in (left, right):
        attribute.add_mirror_config_channels(ctl)
    analysis = mirror_config.analyze([left, right], mode="selection")
    assert _record(analysis, LEFT)["status"] == mirror_config.STATUS_CHANGED
    mirror_config.apply_config(mirror_config.config_from_analysis(analysis))
    result = mirror_config.verify([left], mode="selection")[left]
    assert result["rotation_error"] < 0.01
    assert result["translation_error"] < 0.001


def test_scale_flags_never_proposed(mirror_config):
    from maya import cmds

    left, right = _pair(cmds)
    cmds.setAttr(left + ".invSx", True)
    analysis = mirror_config.analyze([left], mode="selection")
    record = _record(analysis, LEFT)
    assert record["proposed"]["invSx"] is False
    assert record["status"] == mirror_config.STATUS_CHANGED


# =============================================================================
# status
# =============================================================================


def test_swapped_axes_not_mirrorable(mirror_config):
    import maya.api.OpenMaya as om2
    from maya import cmds

    matrix = _left_matrix()
    swap = om2.MMatrix(((0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    left = _control(cmds, LEFT, matrix)
    right = _control(cmds, RIGHT, swap * _mirrored(matrix))
    analysis = mirror_config.analyze([left, right], mode="selection")
    for name in (LEFT, RIGHT):
        record = _record(analysis, name)
        assert record["status"] == mirror_config.STATUS_NOT_MIRRORABLE
        assert record["error"] > mirror_config.DEFAULT_TOLERANCE
        assert record["proposed"] is None


def test_missing_partner(mirror_config):
    from maya import cmds

    ctl = _control(cmds, "leg_L0_fk0_ctl", _left_matrix())
    record = _record(mirror_config.analyze([ctl], mode="selection"), "leg_L0_fk0_ctl")
    assert record["status"] == mirror_config.STATUS_NO_PAIR
    assert record["target"] is None


def test_matching_flags_ok(mirror_config):
    from maya import cmds

    left, right = _pair(cmds, flips=(-1, 1, 1))
    analysis = mirror_config.analyze([left, right], mode="selection")
    mirror_config.apply_config(mirror_config.config_from_analysis(analysis))
    analysis = mirror_config.analyze([left, right], mode="selection")
    assert {r["status"] for r in analysis["controls"]} == {mirror_config.STATUS_OK}


# =============================================================================
# default pose and up axis
# =============================================================================


def _posed_rig(cmds):
    """A rig with a center parent control and a left/right pair below it."""
    spine = _control(cmds, CENTER)
    left, right = _pair(cmds, flips=(-1, 1, 1), parent=spine)
    _rig(cmds, [spine, left, right])
    return [cmds.ls(n, long=True)[0] for n in (CENTER, LEFT, RIGHT)]


def test_default_pose(mirror_config):
    from maya import cmds

    spine, left, right = _posed_rig(cmds)
    expected = mirror_config.analyze([spine])
    cmds.setAttr(spine + ".ry", 40)
    cmds.setAttr(spine + ".tx", 3)
    cmds.setAttr(left + ".rz", 25)
    undo_before = cmds.undoInfo(query=True, undoName=True)
    analysis = mirror_config.analyze([spine])
    for name in (CENTER, LEFT, RIGHT):
        assert (
            _record(analysis, name)["proposed"] == _record(expected, name)["proposed"]
        )
    assert cmds.getAttr(spine + ".ry") == pytest.approx(40)
    assert cmds.getAttr(spine + ".tx") == pytest.approx(3)
    assert cmds.getAttr(left + ".rz") == pytest.approx(25)
    assert cmds.undoInfo(query=True, undoName=True) == undo_before


def test_z_up(mirror_config):
    from maya import cmds

    spine, left, right = _posed_rig(cmds)
    expected = mirror_config.analyze([spine])
    cmds.upAxis(axis="z")
    analysis = mirror_config.analyze([spine])
    assert analysis["up_axis"] == "z"
    for name in (CENTER, LEFT, RIGHT):
        assert (
            _record(analysis, name)["proposed"] == _record(expected, name)["proposed"]
        )


# =============================================================================
# controls, missing attributes
# =============================================================================


def test_rig_mode_includes_inv_attr_nodes(mirror_config):
    from maya import cmds

    from mgear.core import attribute

    spine, left, right = _posed_rig(cmds)
    extra = cmds.createNode("transform", name="eye_L0_over_ctl", parent=spine)
    attribute.add_mirror_config_channels(extra)
    controls = mirror_config.get_controls([spine])
    assert cmds.ls(extra, long=True)[0] in controls
    assert set((spine, left, right)) <= set(controls)


def test_find_and_create_missing(mirror_config):
    from maya import cmds

    spine, left, right = _posed_rig(cmds)
    bare = cmds.createNode("transform", name="leg_L0_ik_ctl", parent=spine)
    cmds.sets(bare, addElement="rig_controllers_grp")
    bare = cmds.ls(bare, long=True)[0]
    assert mirror_config.find_missing([spine]) == [bare]
    assert (
        _record(mirror_config.analyze([spine]), "leg_L0_ik_ctl")["status"]
        == mirror_config.STATUS_NO_PAIR
    )

    cmds.addAttr(bare, longName="invTx", attributeType="bool")
    cmds.setAttr(bare + ".invTx", True)
    assert mirror_config.create_missing([bare]) == [bare]
    for attr in mirror_config.INV_ATTRS:
        assert cmds.attributeQuery(attr, node=bare, exists=True)
    assert cmds.getAttr(bare + ".invTx") is True
    assert cmds.attributeQuery("invTy", node=bare, niceName=True) == (
        "Invert Mirror TY"
    )
    assert mirror_config.find_missing([spine]) == []


def test_missing_status_with_proposal(mirror_config):
    from maya import cmds

    left = _control(cmds, LEFT, _left_matrix())
    right_npo = cmds.createNode("transform", name="arm_R0_fk0_npo")
    cmds.xform(right_npo, matrix=list(_mirrored(_left_matrix())), worldSpace=True)
    cmds.createNode("transform", name=RIGHT, parent=right_npo)
    record = _record(mirror_config.analyze([left, RIGHT], mode="selection"), RIGHT)
    assert record["status"] == mirror_config.STATUS_MISSING
    assert record["proposed"] is not None
    assert set(record["current"].values()) == {None}


# =============================================================================
# apply and files
# =============================================================================


def _flags(**on):
    """Nine inv flags, all off except the given ones."""
    from mgear.core import attribute

    return {a: int(on.get(a, 0)) for a in attribute.MIRROR_CONFIG_CHANNELS}


def test_apply_with_namespace(mirror_config):
    from maya import cmds

    cmds.namespace(add="char01")
    cmds.namespace(set="char01")
    _control(cmds, LEFT)
    cmds.namespace(set=":")
    config = mirror_config.build_config({LEFT: _flags(invTx=1, invRz=1)})
    result = mirror_config.apply_config(config, namespace="char01")
    assert len(result["applied"]) == 1
    assert cmds.getAttr("char01:{}.invTx".format(LEFT)) is True
    assert cmds.getAttr("char01:{}.invRz".format(LEFT)) is True
    assert cmds.getAttr("char01:{}.invTy".format(LEFT)) is False


def test_apply_unknown_and_locked(mirror_config):
    from maya import cmds

    left = _control(cmds, LEFT)
    right = _control(cmds, RIGHT)
    cmds.setAttr(right + ".invTx", lock=True)
    config = mirror_config.build_config(
        {
            LEFT: _flags(invTx=1),
            RIGHT: _flags(invTx=1, invRy=1),
            "ghost_C0_ctl": _flags(),
        }
    )
    result = mirror_config.apply_config(config)
    assert result["not_found"] == ["ghost_C0_ctl"]
    assert result["applied"] == [left]
    assert result["skipped"] == [right]
    assert cmds.getAttr(left + ".invTx") is True
    assert cmds.getAttr(right + ".invTx") is False
    assert cmds.getAttr(right + ".invRy") is True


def test_apply_creates_missing(mirror_config):
    from maya import cmds

    bare = cmds.createNode("transform", name=LEFT)
    config = mirror_config.build_config({LEFT: _flags(invTz=1)})
    mirror_config.apply_config(config, create_missing=False)
    assert not cmds.attributeQuery("invTz", node=bare, exists=True)
    mirror_config.apply_config(config)
    assert cmds.getAttr(bare + ".invTz") is True


def test_apply_one_undo(mirror_config):
    from maya import cmds

    left = _control(cmds, LEFT)
    right = _control(cmds, RIGHT)
    cmds.undoInfo(state=True, infinity=True)
    cmds.flushUndo()
    config = mirror_config.build_config(
        {LEFT: _flags(invTx=1, invRy=1), RIGHT: _flags(invTz=1)}
    )
    mirror_config.apply_config(config)
    cmds.undo()
    for ctl in (left, right):
        assert not any(
            cmds.getAttr("{}.{}".format(ctl, a)) for a in mirror_config.INV_ATTRS
        )


def test_round_trip(mirror_config, tmp_path):
    from maya import cmds

    left, right = _pair(cmds, flips=(-1, 1, 1))
    analysis = mirror_config.analyze([left, right], mode="selection")
    mirror_config.apply_config(mirror_config.config_from_analysis(analysis))
    path = mirror_config.export_config(
        str(tmp_path / "hero"), mirror_config.get_config([left, right], "selection")
    )
    assert path.endswith("hero.smc")
    for ctl in (left, right):
        for attr in mirror_config.INV_ATTRS:
            cmds.setAttr("{}.{}".format(ctl, attr), True)
    mirror_config.import_config(path)
    for ctl in (left, right):
        assert _on(mirror_config.current_flags(ctl)) == ["invRy", "invRz", "invTx"]

    with open(path) as f:
        data = json.load(f)
    assert data["type"] == "mirror_config"
    assert data["schema_version"] == 1
    assert data["up_axis"] == "y"
    assert set(data["controls"]) == {LEFT, RIGHT}


def test_load_rejects_foreign_file(mirror_config, tmp_path):
    path = tmp_path / "cloth.shw"
    path.write_text(json.dumps({"type": "shrinkwrap_config"}))
    with pytest.raises(ValueError):
        mirror_config.load_config(str(path))
    bad = tmp_path / "bad.smc"
    bad.write_text("not json")
    with pytest.raises(ValueError):
        mirror_config.load_config(str(bad))


def test_user_attribute_flags_not_exported(mirror_config):
    from maya import cmds

    ctl = _control(cmds, CENTER)
    cmds.addAttr(ctl, longName="invRoll", attributeType="bool")
    cmds.setAttr(ctl + ".invRoll", True)
    config = mirror_config.get_config([ctl], "selection")
    assert "invRoll" not in config["controls"][CENTER]
    assert set(config["controls"][CENTER]) == set(mirror_config.INV_ATTRS)


# =============================================================================
# verify
# =============================================================================


def test_verify(mirror_config):
    from maya import cmds

    spine, left, right = _posed_rig(cmds)
    cmds.setAttr(left + ".ry", 12)
    mirror_config.apply_config(
        mirror_config.config_from_analysis(mirror_config.analyze([spine]))
    )
    results = mirror_config.verify([spine])
    assert set(results) == {spine, left}
    for result in results.values():
        assert result["rotation_error"] < 0.01
        assert result["translation_error"] < 0.001
    assert cmds.getAttr(left + ".ry") == pytest.approx(12)
    assert cmds.getAttr(right + ".ry") == pytest.approx(0)

    cmds.setAttr(spine + ".invRy", False)
    assert mirror_config.verify([spine])[spine]["rotation_error"] > 1.0


def test_biped_end_to_end(setup_path, biped_rig):
    from mgear.core import mirror_config

    cmds = biped_rig
    analysis = mirror_config.analyze(["global_C0_ctl"])
    assert _record(analysis, "world_ctl")["status"] == mirror_config.STATUS_MISSING
    assert _record(analysis, "arm_L0_ikcns_ctl")["status"] == (
        mirror_config.STATUS_CHANGED
    )
    mirror_config.apply_config(mirror_config.config_from_analysis(analysis))
    results = mirror_config.verify(["global_C0_ctl"])
    assert len(results) > 50
    for source, result in results.items():
        assert result["rotation_error"] < 0.01, source
        assert result["translation_error"] < 0.001, source
    statuses = {
        r["status"] for r in mirror_config.analyze(["global_C0_ctl"])["controls"]
    }
    assert statuses == {mirror_config.STATUS_OK}
    assert cmds.getAttr("world_ctl.invTx") is True


# =============================================================================
# custom step, menu
# =============================================================================


def test_custom_step_template(mirror_config, tmp_path):
    from maya import cmds

    from mgear.shifter import custom_step_templates

    names = dict(custom_step_templates.get_template_names())
    assert names["import_mirror_config"] == "Import Mirror Config"
    code = custom_step_templates.get_template_content(
        "import_mirror_config", "mirror_step"
    )
    namespace = {}
    exec(compile(code, "mirror_step.py", "exec"), namespace)
    step = namespace["CustomShifterStep"]({})
    step.setup()
    assert step.name == "mirror_step"
    assert step.namespace is None
    assert step.create_missing is True

    bare = cmds.createNode("transform", name=LEFT)
    path = mirror_config.export_config(
        str(tmp_path / "step"),
        mirror_config.build_config({LEFT: _flags(invTx=1, invRy=1)}),
    )
    step.config_path = path
    step.run()
    assert _on(mirror_config.current_flags(bare)) == ["invRy", "invTx"]


def test_menu_entry_with_icon(setup_path, monkeypatch):
    import os

    import mgear
    from mgear.core import pyqt
    from mgear.shifter import menu

    calls = []
    monkeypatch.setattr(
        mgear.menu, "install", lambda *args, **kwargs: calls.append(args)
    )
    menu.install()
    entries = {c[0]: c for c in calls[0][1] if c[0]}
    entry = entries["Mirror Config"]
    assert entry[2] == "mgear_mirror_config.svg"
    assert "mirror_config_ui.show()" in entry[1]
    assert os.path.isfile(pyqt.get_icon_path("mgear_mirror_config.svg"))


def test_ui_row_helpers(setup_path):
    from mgear.shifter import mirror_config_ui

    flags = {"invTx": True, "invTy": False}
    record = {"proposed": flags, "current": {"invTx": None, "invTy": True}}
    assert mirror_config_ui.row_flags(record) == flags
    assert mirror_config_ui.row_flags(record) is not flags
    record["proposed"] = None
    assert mirror_config_ui.row_flags(record) == {"invTx": False, "invTy": True}
    text = mirror_config_ui.format_verify(
        {"rotation_error": 1.234, "translation_error": 0.01}
    )
    assert text == "1.23° / 0.010"


def test_apply_to_rig_nodes(mirror_config):
    from maya import cmds

    spine, left, right = _posed_rig(cmds)
    other = _control(cmds, LEFT.replace("arm", "leg"))
    config = mirror_config.build_config({LEFT: _flags(invTz=1)})
    result = mirror_config.apply_config(config, nodes=[spine])
    assert result["applied"] == [left]
    assert cmds.getAttr(left + ".invTz") is True
    assert cmds.getAttr(other + ".invTz") is False


def test_add_mirror_config_channels_partial(setup_path):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.core import attribute

    cmds.file(new=True, force=True)
    ctl = cmds.createNode("transform", name="ctl")
    cmds.addAttr(ctl, longName="invRy", attributeType="bool")
    cmds.setAttr(ctl + ".invRy", True)
    created = attribute.add_mirror_config_channels(
        pm.PyNode(ctl), [1, 0, 0, 0, 0, 0, 0, 0, 0]
    )
    assert "invRy" not in created
    assert len(created) == 8
    assert cmds.getAttr(ctl + ".invRy") is True
    assert cmds.getAttr(ctl + ".invTx") is True
    assert attribute.add_mirror_config_channels(ctl) == []


def test_default_pose_restores_changed_channels(setup_path):
    from maya import cmds

    from mgear.core import anim_utils

    cmds.file(new=True, force=True)
    ctl = cmds.createNode("transform", name="ctl")
    cmds.setAttr(ctl + ".tx", 2)
    cmds.setAttr(ctl + ".sy", 3)
    with anim_utils.default_pose([ctl]):
        assert cmds.getAttr(ctl + ".tx") == 0
        assert cmds.getAttr(ctl + ".sy") == 1
    assert cmds.getAttr(ctl + ".tx") == 2
    assert cmds.getAttr(ctl + ".sy") == 3


def test_config_io(setup_path, tmp_path):
    from mgear.core import config_io
    from mgear.core import deformer_io

    assert config_io.file_path("C:/tmp/a", ".smc") == "C:/tmp/a.smc"
    path = str(tmp_path / "data.json")
    data = config_io.write_file(path, "t", 1, "items", [1], extra={"up_axis": "z"})
    assert data["up_axis"] == "z"
    assert config_io.load_file(path, "t")["items"] == [1]
    with pytest.raises(ValueError):
        config_io.load_file(path, "other")
    # kept in deformer_io for backward compatibility
    assert deformer_io.write_file is config_io.write_file
    assert deformer_io.load_file is config_io.load_file
    assert deformer_io.file_path is config_io.file_path


def test_ui_row_status(setup_path):
    from mgear.core import mirror_config
    from mgear.shifter import mirror_config_ui

    proposed = {a: False for a in mirror_config.INV_ATTRS}
    current = dict(proposed, invTx=True)
    record = {
        "proposed": proposed,
        "current": current,
        "status": mirror_config.STATUS_CHANGED,
        "flags": dict(proposed),
    }
    assert mirror_config_ui.row_status(record) == mirror_config.STATUS_CHANGED
    record["flags"]["invRz"] = True
    assert mirror_config_ui.row_status(record) == mirror_config_ui.STATUS_MANUAL
    record["proposed"] = None
    record["status"] = mirror_config.STATUS_NO_PAIR
    record["flags"] = mirror_config_ui.row_flags(record)
    assert mirror_config_ui.row_status(record) == mirror_config.STATUS_NO_PAIR
    assert mirror_config_ui.is_verify_error(
        {"rotation_error": 0.0, "translation_error": 0.1}, 1.0
    )
