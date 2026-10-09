"""Tests for Space Recorder, Smart Reset and the Shifter spring bake tools."""

import pytest


def _animated(cmds, name, values, parent=None):
    """Create a transform keyed in translateX, ``{frame: value}``."""
    node = cmds.createNode("transform", name=name, parent=parent)
    for frame, value in values.items():
        cmds.setKeyframe(node, attribute="translateX", time=frame, value=value)
    return cmds.ls(node, long=True)[0]


def _world_x(cmds, node, frame):
    cmds.currentTime(frame)
    return cmds.xform(node, query=True, worldSpace=True, translation=True)[0]


# Space Recorder -------------------------------------------------------


def test_record_keeps_frame_numbers(scene):
    from mgear.animbits import space_recorder

    a = _animated(scene, "a", {10: 0, 20: 10})
    b = _animated(scene, "b", {10: 5, 20: 5})
    scene.currentTime(3)
    recording = space_recorder.record([a, b], 10, 20)
    assert sorted(recording.frames) == list(range(10, 21))
    assert len(recording.frames[15]) == 2
    assert recording.frame_range == (10, 20)
    assert scene.currentTime(query=True) == 3


def test_apply_longer_range_skips_frames(scene):
    from mgear.animbits import space_recorder

    a = _animated(scene, "a", {1: 0, 10: 9})
    recording = space_recorder.record([a], 1, 10)
    scene.cutKey(a)
    report = space_recorder.apply(recording, start=1, end=20)
    assert report["applied_frames"] == list(range(1, 11))
    assert report["skipped_frames"] == list(range(11, 21))
    assert _world_x(scene, a, 10) == pytest.approx(9)


def test_apply_to_more_targets_than_recorded(scene):
    from mgear.animbits import space_recorder

    a = _animated(scene, "a", {1: 0, 5: 4})
    recording = space_recorder.record([a], 1, 5)
    targets = [scene.createNode("transform", name=n) for n in ("x", "y", "z")]
    report = space_recorder.apply(recording, targets, 1, 5)
    assert len(report["unused_targets"]) == 2
    assert _world_x(scene, "x", 5) == pytest.approx(4)
    assert not scene.keyframe("y", query=True)


def test_apply_keys_transforms_only_in_one_undo(scene):
    from mgear.animbits import space_recorder

    a = _animated(scene, "a", {1: 0, 5: 4})
    scene.addAttr(a, longName="blend", keyable=True)
    scene.setAttr(a + ".rotateZ", lock=True)
    recording = space_recorder.record([a], 1, 5)
    scene.cutKey(a)
    scene.undoInfo(state=True)
    scene.flushUndo()
    space_recorder.apply(recording, start=1, end=5)
    assert scene.keyframe(a + ".translateX", query=True)
    assert not scene.keyframe(a + ".blend", query=True)
    assert not scene.keyframe(a + ".rotateZ", query=True)
    scene.undo()
    assert not scene.keyframe(a, query=True)


def test_apply_parent_before_child(scene):
    from mgear.animbits import space_recorder

    parent = _animated(scene, "parent", {1: 0, 10: 10})
    child = _animated(scene, "child", {1: 2, 10: 2}, parent=parent)
    expected = {
        frame: (_world_x(scene, parent, frame), _world_x(scene, child, frame))
        for frame in (1, 5, 10)
    }
    # child first: apply must still set the parent first
    recording = space_recorder.record([child, parent], 1, 10)
    scene.cutKey(parent)
    scene.setAttr(parent + ".translateX", 100)
    space_recorder.apply(recording, start=1, end=10)
    for frame, (parent_x, child_x) in expected.items():
        assert _world_x(scene, parent, frame) == pytest.approx(parent_x, abs=1e-3)
        assert _world_x(scene, child, frame) == pytest.approx(child_x, abs=1e-3)


def test_buffers_survive_window(scene):
    from mgear.animbits import space_recorder

    a = _animated(scene, "a", {1: 0, 5: 4})
    space_recorder.BUFFERS["A"] = space_recorder.record([a], 1, 5)
    reloaded = space_recorder.BUFFERS.get("A")
    assert reloaded.describe() == "1 object, frames 1-5"
    space_recorder.BUFFERS.clear()


# Smart Reset ----------------------------------------------------------


def test_reset_srt_one_undo(scene):
    from mgear.core import attribute

    nodes = [scene.createNode("transform", name=n) for n in ("a", "b", "c")]
    for node in nodes:
        scene.setAttr(node + ".translate", 1, 2, 3)
        scene.setAttr(node + ".scaleX", 4)
    scene.undoInfo(state=True)
    scene.flushUndo()
    attribute.reset_SRT(nodes)
    assert all(scene.getAttr(n + ".translateY") == 0 for n in nodes)
    assert all(scene.getAttr(n + ".scaleX") == 1 for n in nodes)
    scene.undo()
    assert all(scene.getAttr(n + ".translateY") == 2 for n in nodes)
    assert all(scene.getAttr(n + ".scaleX") == 4 for n in nodes)


def test_reset_srt_custom_channels(scene):
    from mgear.core import attribute

    node = scene.createNode("transform", name="a")
    scene.setAttr(node + ".translate", 1, 2, 3)
    attribute.reset_SRT([node], ["tx"])
    assert scene.getAttr(node + ".translate")[0] == (0, 2, 3)
    assert isinstance(attribute.SRT_CHANNELS, tuple)


# Spring bake ----------------------------------------------------------


def _spring_rig(cmds, with_set=True):
    """Rig with a baked spring node (pairBlend) and a node never baked."""
    rig = cmds.createNode("transform", name="rig")
    cmds.addAttr(rig, longName="is_rig", attributeType="bool")
    driver = cmds.createNode("transform", name="driver", parent=rig)
    cmds.setKeyframe(driver, attribute="rotateZ", time=1, value=0)
    cmds.setKeyframe(driver, attribute="rotateZ", time=10, value=45)
    baked = cmds.createNode("transform", name="spring_baked", parent=rig)
    cmds.orientConstraint(driver, baked)
    cmds.setKeyframe(baked, attribute="rotate", insertBlend=True)
    plain = cmds.createNode("transform", name="spring_plain", parent=rig)
    if with_set:
        cmds.sets([baked, plain], name="rig_PLOT_grp")
    return rig, baked, plain


def _baked_curves(cmds, node):
    blends = cmds.listConnections(node, type="pairBlend") or []
    return cmds.listConnections(blends, type="animCurveTA") or []


def test_clear_springs_skips_nodes_without_pairblend(scene):
    import mgear.pymaya as pm
    from mgear.core import anim_utils

    rig, baked, _ = _spring_rig(scene)
    assert _baked_curves(scene, baked)
    anim_utils.clearSprings(pm.PyNode(rig))
    assert not _baked_curves(scene, baked)


def test_bake_springs_keys_rotation(scene):
    import mgear.pymaya as pm
    from mgear.core import anim_utils

    rig, baked, _ = _spring_rig(scene)
    scene.playbackOptions(minTime=1, maxTime=10)
    anim_utils.bakeSprings(pm.PyNode(rig))
    curves = _baked_curves(scene, baked)
    assert curves
    values = scene.keyframe(curves[0], query=True, valueChange=True)
    assert len(values) == 10


def test_springs_without_spring_set(scene):
    import mgear.pymaya as pm
    from mgear.core import anim_utils

    rig, _, _ = _spring_rig(scene, with_set=False)
    assert anim_utils.getControlers(rig, anim_utils.PLOT_GRP_SUFFIX) is None
    anim_utils.clearSprings(pm.PyNode(rig))
    anim_utils.bakeSprings(pm.PyNode(rig))


# Core helpers ---------------------------------------------------------


def test_unlocked_channels_settable(scene):
    from mgear.core import attribute

    node = scene.createNode("transform", name="a")
    driver = scene.createNode("transform", name="driver")
    scene.setAttr(node + ".translateX", lock=True)
    scene.connectAttr(driver + ".rotateY", node + ".rotateY")
    unlocked = attribute.get_unlocked_channels(node)
    settable = attribute.get_unlocked_channels(node, settable=True)
    assert "translateX" not in unlocked and "rotateY" in unlocked
    assert "translateX" not in settable and "rotateY" not in settable
    assert "scaleZ" in settable


def test_time_and_range_helpers(scene):
    from mgear.core import anim_utils
    from mgear.core import utils

    scene.playbackOptions(minTime=3, maxTime=12)
    assert anim_utils.get_playback_range() == (3, 12)
    assert anim_utils.get_playback_range(5) == (5, 12)
    scene.currentTime(7)
    with utils.current_time_kept():
        scene.currentTime(11)
    assert scene.currentTime(query=True) == 7


def test_world_matrices_round_trip(scene):
    from mgear.core import anim_utils

    a = _animated(scene, "a", {1: 0, 5: 4})
    frames = anim_utils.record_world_matrices([a], 1, 5)
    assert sorted(frames) == [1, 2, 3, 4, 5]
    assert len(frames[3][0]) == 16
    target = scene.createNode("transform", name="b")
    assert anim_utils.key_world_matrices([target], frames) == [1, 2, 3, 4, 5]
    assert _world_x(scene, target, 5) == pytest.approx(4)


def test_bake_springs_keeps_current_time(scene):
    import mgear.pymaya as pm
    from mgear.core import anim_utils

    rig, _, _ = _spring_rig(scene)
    scene.playbackOptions(minTime=1, maxTime=10)
    scene.currentTime(4)
    anim_utils.bakeSprings(pm.PyNode(rig))
    assert scene.currentTime(query=True) == 4
