"""Tests for the HumanIK Mapper core and batch bake."""

import json

import pytest

# (bone, parent, position) of a minimal HumanIK body
BODY = (
    ("Reference", None, (0, 0, 0)),
    ("Hips", "Reference", (0, 100, 0)),
    ("Spine", "Hips", (0, 110, 0)),
    ("Neck", "Spine", (0, 150, 0)),
    ("Head", "Neck", (0, 160, 0)),
    ("LeftUpLeg", "Hips", (10, 95, 0)),
    ("LeftLeg", "LeftUpLeg", (10, 50, 0)),
    ("LeftFoot", "LeftLeg", (10, 5, 0)),
    ("RightUpLeg", "Hips", (-10, 95, 0)),
    ("RightLeg", "RightUpLeg", (-10, 50, 0)),
    ("RightFoot", "RightLeg", (-10, 5, 0)),
    ("LeftArm", "Spine", (20, 145, 0)),
    ("LeftForeArm", "LeftArm", (45, 145, 0)),
    ("LeftHand", "LeftForeArm", (70, 145, 0)),
    ("RightArm", "Spine", (-20, 145, 0)),
    ("RightForeArm", "RightArm", (-45, 145, 0)),
    ("RightHand", "RightForeArm", (-70, 145, 0)),
)

# mGear style control names of the BODY bones
CONTROLS = {
    "Reference": "world_ctl",
    "Hips": "body_C0_ctl",
    "Spine": "spine_C0_ctl",
    "Neck": "neck_C0_ctl",
    "Head": "head_C0_ctl",
    "LeftUpLeg": "leg_L0_fk0_ctl",
    "LeftLeg": "leg_L0_fk1_ctl",
    "LeftFoot": "leg_L0_fk2_ctl",
    "RightUpLeg": "leg_R0_fk0_ctl",
    "RightLeg": "leg_R0_fk1_ctl",
    "RightFoot": "leg_R0_fk2_ctl",
    "LeftArm": "arm_L0_fk0_ctl",
    "LeftForeArm": "arm_L0_fk1_ctl",
    "LeftHand": "arm_L0_fk2_ctl",
    "RightArm": "arm_R0_fk0_ctl",
    "RightForeArm": "arm_R0_fk1_ctl",
    "RightHand": "arm_R0_fk2_ctl",
}


@pytest.fixture
def hik(scene):
    """New scene with the HumanIK plug-in, skipped without it."""
    from mgear.core import utils
    from mgear.animbits.human_ik_mapper import core

    if not utils.is_plugin_available(core.HIK_PLUGIN):
        pytest.skip("mayaHIK plug-in not available")
    core.ensure_hik()
    return scene


def build_controls(cmds, namespace=""):
    """Create a control hierarchy with the BODY layout.

    Returns:
        dict: ``{bone: control}``.
    """
    nodes = {}
    for bone, parent, position in BODY:
        name = namespace + CONTROLS[bone]
        node = cmds.createNode("transform", name=name)
        cmds.xform(node, worldSpace=True, translation=position)
        if parent:
            cmds.parent(node, nodes[parent])
        nodes[bone] = cmds.ls(node)[0]
    return nodes


def build_source(cmds, name="SRC", prefix="src_"):
    """Create a keyed source skeleton with a locked HumanIK character.

    Hips move from 0 to 50 in X between frames 1 and 10.

    Returns:
        tuple: ``(character, {bone: joint})``.
    """
    from mgear.animbits.human_ik_mapper import core

    joints = {}
    for bone, parent, position in BODY:
        cmds.select(clear=True)
        joints[bone] = cmds.joint(name=prefix + bone, position=position)
        if parent:
            cmds.parent(joints[bone], joints[parent])
            joints[bone] = cmds.ls(prefix + bone)[0]
    character = core.utils.mel_call("hikCreateCharacter", name)
    for bone, joint in joints.items():
        node_id = cmds.hikGetNodeIdFromName(bone)
        core.utils.mel_call("setCharacterObject", joint, character, node_id, 0)
    core.lock(character)
    cmds.setKeyframe(joints["Hips"], attribute="translateX", time=1, value=0)
    cmds.setKeyframe(joints["Hips"], attribute="translateX", time=10, value=50)
    return character, joints


def map_rig(controls):
    from mgear.animbits.human_ik_mapper import core

    character = core.initialize_character(controls["Reference"])
    core.map_bones(
        character,
        [(bone, ctl) for bone, ctl in controls.items() if bone != "Reference"],
    )
    return character


def test_initialize_reuses_character(hik):
    from mgear.animbits.human_ik_mapper import core

    controls = build_controls(hik)
    first = core.initialize_character(controls["Reference"])
    second = core.initialize_character(controls["Reference"])
    assert first == second == "MGearIKHuman"
    assert hik.ls(type="HIKCharacterNode") == ["MGearIKHuman"]
    assert core.get_bone_target(first, "Reference") == "world_ctl"


def test_character_tag_and_namespace(hik):
    from mgear.animbits.human_ik_mapper import core

    hik.namespace(add="chr")
    controls = build_controls(hik, namespace="chr:")
    character = core.initialize_character(controls["Reference"])
    hik.rename(character, "chr:MGearIKHuman")
    assert core.get_character() == "chr:MGearIKHuman"
    other = core.utils.mel_call("hikCreateCharacter", "Other")
    assert core.get_character() == "chr:MGearIKHuman"
    assert core.list_sources("chr:MGearIKHuman") == [other]


def test_locked_channels(hik):
    from mgear.animbits.human_ik_mapper import core

    controls = build_controls(hik)
    character = core.initialize_character(controls["Reference"])
    hik.setAttr(controls["Hips"] + ".translateX", lock=True)
    with pytest.raises(core.LockedChannelsError) as error:
        core.map_bones(character, [("Hips", controls["Hips"])])
    assert error.value.controls == [controls["Hips"]]
    assert "Hips" not in core.get_mapping(character)
    core.map_bones(character, [("Hips", controls["Hips"])], unlock_channels=True)
    assert core.get_mapping(character)["Hips"]["target"] == controls["Hips"]
    assert not hik.getAttr(controls["Hips"] + ".translateX", lock=True)


def test_pair_selection_mismatch_and_mirror(hik):
    from mgear.animbits.human_ik_mapper import constants
    from mgear.animbits.human_ik_mapper import core

    build_controls(hik)
    arm = ["arm_L0_fk0_ctl", "arm_L0_fk1_ctl", "arm_L0_fk2_ctl"]
    pairs, report = core.pair_selection(list(constants.LEFT_ARM), arm)
    assert len(pairs) == 3
    assert report["unpaired_bones"] == ["LeftHand"]

    hik.delete("arm_R0_fk2_ctl")
    pairs, report = core.pair_selection(
        ["LeftArm", "LeftForeArm", "LeftHand"], arm, mirror=True
    )
    assert ("RightArm", "arm_R0_fk0_ctl") in pairs
    assert report["missing_mirror"] == ["RightHand"]
    assert all(control for _, control in pairs)


def test_map_bones_one_undo(hik):
    from mgear.animbits.human_ik_mapper import constants
    from mgear.animbits.human_ik_mapper import core

    controls = build_controls(hik)
    character = core.initialize_character(controls["Reference"])
    hik.undoInfo(state=True)
    hik.flushUndo()
    core.map_bones(
        character, [(bone, controls[bone]) for bone in constants.LEFT_LEG[:2]]
    )
    mapping = core.get_mapping(character)
    assert mapping["LeftUpLeg"]["target"] == "leg_L0_fk0_ctl"
    assert (
        core.body_part_status(mapping, constants.LEFT_LEG) == constants.STATUS_PARTIAL
    )
    hik.undo()
    assert "LeftUpLeg" not in core.get_mapping(character)


def test_body_part_status(hik):
    from mgear.animbits.human_ik_mapper import constants
    from mgear.animbits.human_ik_mapper import core

    mapping = {bone: {} for bone in ("Hips", "Spine")}
    assert core.body_part_status(mapping, constants.SPINE) == constants.STATUS_COMPLETE
    assert core.body_part_status(mapping, constants.HEAD) == constants.STATUS_EMPTY
    mapping = {"LeftArm": {}, "LeftForeArm": {}, "LeftHand": {}}
    assert (
        core.body_part_status(mapping, constants.LEFT_ARM) == constants.STATUS_COMPLETE
    )
    mapping = {"LeftHandIndex1": {}}
    assert (
        core.body_part_status(mapping, constants.LEFT_HAND) == constants.STATUS_COMPLETE
    )


def test_incomplete_parts(hik):
    from mgear.animbits.human_ik_mapper import core

    controls = build_controls(hik)
    character = map_rig(controls)
    assert core.incomplete_parts(core.get_mapping(character)) == []
    core.unmap_bones(character, ["LeftHand"])
    assert core.incomplete_parts(core.get_mapping(character)) == ["left_arm"]


def test_sub_ik_set_and_clear(hik):
    from mgear.animbits.human_ik_mapper import core

    controls = build_controls(hik)
    character = map_rig(controls)
    extra = hik.createNode("transform", name="spine_C0_ik_ctl")
    core.set_sub_ik(controls["Spine"], [extra])
    assert core.get_mapping(character)["Spine"]["sub_ik"] == [extra]
    constraints, plugs = core.bind_sub_iks(core.get_mapping(character))
    assert len(constraints) == 1
    assert len(plugs) == 6
    assert core.clear_sub_ik(controls["Spine"]) == [extra]
    assert core.get_mapping(character)["Spine"]["sub_ik"] == []
    assert not hik.ls(constraints)


def test_export_import_into_namespace(hik, tmp_path):
    from mgear.animbits.human_ik_mapper import core

    controls = build_controls(hik)
    character = map_rig(controls)
    extra = hik.createNode("transform", name="spine_C0_ik_ctl")
    core.set_sub_ik(controls["Spine"], [extra])
    path = str(tmp_path / "rig.hikm")
    core.export_mapping(path, character)
    with open(path) as stream:
        data = json.load(stream)
    assert data["version"] == 2
    assert data["mapping"]["Hips"]["target"] == "body_C0_ctl"

    hik.file(new=True, force=True)
    core.ensure_hik()
    hik.namespace(add="chr")
    build_controls(hik, namespace="chr:")
    hik.createNode("transform", name="chr:spine_C0_ik_ctl")
    hik.delete("chr:head_C0_ctl")
    character, report = core.import_mapping(path, namespace="chr")
    mapping = core.get_mapping(character)
    assert mapping["Hips"]["target"] == "chr:body_C0_ctl"
    assert mapping["Spine"]["sub_ik"] == ["chr:spine_C0_ik_ctl"]
    assert report["missing"] == ["head_C0_ctl"]
    assert "Head" not in mapping


def test_import_version_1(hik, tmp_path):
    from mgear.animbits.human_ik_mapper import core

    build_controls(hik)
    path = str(tmp_path / "old.hikm")
    with open(path, "w") as stream:
        json.dump(
            {
                "Reference": {"target": "world_ctl", "sub_ik": []},
                "Hips": {"target": "body_C0_ctl", "sub_ik": []},
            },
            stream,
        )
    character, report = core.import_mapping(path)
    assert core.get_mapping(character)["Hips"]["target"] == "body_C0_ctl"
    assert not report["missing"]


def test_set_source_drives_controls(hik):
    from mgear.animbits.human_ik_mapper import core

    source, _ = build_source(hik)
    controls = build_controls(hik)
    character = map_rig(controls)
    assert core.list_sources(character) == [source]
    core.set_source(character, source)
    assert core.get_source(character) == source
    hik.currentTime(10)
    assert hik.xform(controls["Hips"], query=True, worldSpace=True, translation=True)[
        0
    ] == pytest.approx(50, abs=0.1)
    core.set_source(character, None)
    assert core.get_source(character) is None


@pytest.mark.parametrize("layer", [None, "take01"])
def test_bake_with_sub_ik(hik, layer):
    from mgear.animbits.human_ik_mapper import core

    source, _ = build_source(hik)
    controls = build_controls(hik)
    character = map_rig(controls)
    extra = hik.createNode("transform", name="hips_C0_ik_ctl")
    hik.parent(extra, controls["Hips"])
    core.set_sub_ik(controls["Hips"], [extra])
    hik.parent(extra, world=True)
    core.set_source(character, source)
    result = core.bake(character, 1, 10, layer=layer)
    assert not hik.ls(type="parentConstraint")
    if layer:
        assert result == "take01"
        assert hik.animLayer("take01", query=True, attribute=True)
        hik.animLayer("take01", edit=True, weight=1)
    hik.currentTime(10)
    assert hik.getAttr(controls["Hips"] + ".translateX") == pytest.approx(50, abs=0.1)
    assert hik.getAttr(extra + ".translateX") == pytest.approx(50, abs=0.1)


def test_bake_pre_roll(hik):
    from mgear.animbits.human_ik_mapper import core

    source, _ = build_source(hik)
    controls = build_controls(hik)
    character = map_rig(controls)
    core.set_source(character, source)
    core.bake(character, 5, 10, pre_roll=3)
    times = hik.keyframe(controls["Hips"] + ".translateX", query=True)
    assert min(times) == 5
    assert max(times) == 10


def _save_source_file(cmds, path, end):
    cmds.file(new=True, force=True)
    _, joints = build_source(cmds)
    cmds.setKeyframe(joints["Hips"], attribute="translateX", time=end, value=80)
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii", force=True)


def test_batch_bake_layers(hik, tmp_path):
    from mgear.animbits.human_ik_mapper import batch
    from mgear.animbits.human_ik_mapper import core

    first = str(tmp_path / "walk.ma")
    second = str(tmp_path / "run.ma")
    _save_source_file(hik, first, 50)
    _save_source_file(hik, second, 80)
    empty = str(tmp_path / "empty.ma")
    hik.file(new=True, force=True)
    hik.createNode("transform")
    hik.file(rename=empty)
    hik.file(save=True, type="mayaAscii", force=True)

    hik.file(new=True, force=True)
    core.ensure_hik()
    map_rig(build_controls(hik))
    reports = batch.batch_bake([first, empty, second], remove_references=True)
    assert [r["status"] for r in reports] == ["baked", "skipped", "baked"]
    assert reports[0]["range"] == (1, 50)
    assert reports[2]["range"] == (1, 80)
    assert sorted(hik.ls(type="animLayer")) == ["BaseAnimation", "run", "walk"]
    assert not hik.ls(references=True)


def test_batch_bake_timeline(hik, tmp_path):
    from mgear.animbits.human_ik_mapper import batch
    from mgear.animbits.human_ik_mapper import core

    first = str(tmp_path / "walk.ma")
    second = str(tmp_path / "run.ma")
    _save_source_file(hik, first, 50)
    _save_source_file(hik, second, 80)
    hik.file(new=True, force=True)
    core.ensure_hik()
    hik.playbackOptions(minTime=1, maxTime=30)
    map_rig(build_controls(hik))
    reports = batch.batch_bake([first, second], mode=batch.MODE_TIMELINE)
    assert [r["status"] for r in reports] == ["baked", "baked"]
    starts = [
        hik.timeEditorClip(r["clip"], query=True, startTime=True) for r in reports
    ]
    assert starts == [1, 51]
    assert hik.playbackOptions(query=True, maxTime=True) == 130
