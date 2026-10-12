"""Tests for mgear.core.temp_pivot."""

import pytest


@pytest.fixture
def temp_pivot(setup_path, monkeypatch):
    """The temp pivot module, in a new scene with frames 1 to 20."""
    from maya import cmds
    from mgear.core import anim_utils
    from mgear.core import temp_pivot

    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=1, maxTime=20)
    monkeypatch.setattr(anim_utils, "get_timeline_range", lambda: None)
    return temp_pivot


def _keyed_ctl(cmds, name="ctl", values=((1, 0), (10, 4))):
    ctl = cmds.spaceLocator(name=name)[0]
    for frame, value in values:
        cmds.setKeyframe(ctl, attribute="translateX", time=frame, value=value)
        cmds.setKeyframe(ctl, attribute="rotateY", time=frame, value=value * 10)
    return cmds.ls(ctl, long=True)[0]


def _matrix(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, matrix=True)


def _matrices_on(cmds, node, frames):
    result = {}
    for frame in frames:
        cmds.currentTime(frame)
        result[frame] = _matrix(node)
    return result


def _no_temp_nodes(cmds, *controls):
    assert not cmds.ls(type="pairBlend")
    assert not cmds.ls("*mgear_temp_pivot*")
    for control in controls:
        assert not cmds.listAttr(control, string="blendParent*")
        assert not cmds.listConnections(control, type="constraint")


def test_create_default_position_and_frames(temp_pivot):
    from maya import cmds

    a = _keyed_ctl(cmds, "a")
    b = cmds.spaceLocator(name="b")[0]
    cmds.setAttr(b + ".translateX", 2)
    cmds.setKeyframe(b, attribute="translateZ", time=1, value=0)
    cmds.setKeyframe(b, attribute="translateZ", time=10, value=0)
    cmds.currentTime(5)
    cmds.setAttr(a + ".translateX", 0)
    pivot = temp_pivot.create([a, b])
    assert cmds.xform(pivot, query=True, worldSpace=True, translation=True)[
        0
    ] == pytest.approx(1.0, abs=0.3)
    assert temp_pivot.info(pivot)["frames"] == [1, 5, 10]
    assert temp_pivot.state(pivot) == "place"
    assert temp_pivot.find() == pivot


def test_create_one_at_a_time(temp_pivot):
    from maya import cmds

    a = _keyed_ctl(cmds, "a")
    temp_pivot.create([a])
    with pytest.raises(RuntimeError):
        temp_pivot.create([a])
    assert len(cmds.ls("mgear_temp_pivot_grp")) == 1


def test_activate_changes_nothing(temp_pivot):
    from maya import cmds

    ctl = _keyed_ctl(cmds)
    cmds.currentTime(5)
    before = _matrices_on(cmds, ctl, (1, 5, 10))
    cmds.currentTime(5)
    pivot = temp_pivot.create([ctl], position=(2, 0, 0))
    assert temp_pivot.activate(pivot) == []
    assert temp_pivot.state(pivot) == "active"
    after = _matrices_on(cmds, ctl, (1, 5, 10))
    for frame in (1, 5, 10):
        assert after[frame] == pytest.approx(before[frame], abs=1e-4)


def test_activate_two_controls_keep_their_animation(temp_pivot):
    from maya import cmds

    a = _keyed_ctl(cmds, "a", ((1, 0), (10, 4)))
    b = _keyed_ctl(cmds, "b", ((1, 3), (10, -2)))
    cmds.currentTime(5)
    before = {n: _matrices_on(cmds, n, (1, 10)) for n in (a, b)}
    cmds.currentTime(5)
    pivot = temp_pivot.create([a, b])
    temp_pivot.activate(pivot)
    for node in (a, b):
        after = _matrices_on(cmds, node, (1, 10))
        for frame in (1, 10):
            assert after[frame] == pytest.approx(before[node][frame], abs=1e-4)


def test_rotate_around_pivot(temp_pivot):
    from maya import cmds

    ctl = cmds.spaceLocator(name="ctl")[0]
    cmds.setKeyframe(ctl, attribute="translateX", time=1, value=0)
    cmds.currentTime(1)
    pivot = temp_pivot.create([ctl], position=(2, 0, 0))
    temp_pivot.activate(pivot)
    cmds.setAttr(pivot + ".rotateY", 90)
    position = cmds.xform(ctl, query=True, worldSpace=True, translation=True)
    # (0, 0, 0) turned 90 degrees around Y about (2, 0, 0)
    assert position == pytest.approx([2, 0, 2], abs=1e-4)


def test_locked_translate_skipped(temp_pivot):
    from maya import cmds

    a = _keyed_ctl(cmds, "a")
    b = _keyed_ctl(cmds, "b")
    for axis in "XYZ":
        cmds.setAttr("{}.translate{}".format(b, axis), lock=True)
    pivot = temp_pivot.create([a, b])
    skipped = temp_pivot.activate(pivot)
    assert skipped == [b]
    assert temp_pivot.info(pivot)["skipped"] == [b]
    assert cmds.listConnections(a, type="constraint")
    assert not cmds.listConnections(b, type="constraint")


def test_all_locked_stays_in_place(temp_pivot):
    from maya import cmds

    a = cmds.spaceLocator(name="a")[0]
    for axis in "XYZ":
        cmds.setAttr("{}.translate{}".format(a, axis), lock=True)
    pivot = temp_pivot.create([a])
    assert temp_pivot.activate(pivot) == [cmds.ls(a, long=True)[0]]
    assert temp_pivot.state(pivot) == "place"


def test_bake_keeps_driven_pose(temp_pivot):
    from maya import cmds

    ctl = _keyed_ctl(cmds)
    cmds.currentTime(5)
    pivot = temp_pivot.create([ctl], position=(2, 0, 0))
    temp_pivot.activate(pivot)
    cmds.setAttr(pivot + ".rotateY", 45)
    cmds.setKeyframe(pivot, attribute="rotateY", time=5)
    driven = _matrices_on(cmds, ctl, (1, 5, 10))
    baked = temp_pivot.bake(pivot)
    assert baked == [ctl]
    _no_temp_nodes(cmds, ctl)
    times = cmds.keyframe(ctl + ".translateX", query=True, timeChange=True)
    assert set([1.0, 5.0, 10.0]) <= set(times)
    after = _matrices_on(cmds, ctl, (1, 5, 10))
    for frame in (1, 5, 10):
        assert after[frame] == pytest.approx(driven[frame], abs=1e-4)


def test_cancel_restores_animation(temp_pivot):
    from maya import cmds

    ctl = _keyed_ctl(cmds)
    curve = cmds.listConnections(ctl + ".translateX", source=True, destination=False)
    before = _matrices_on(cmds, ctl, (1, 5, 10))
    cmds.currentTime(5)
    pivot = temp_pivot.create([ctl], position=(2, 0, 0))
    temp_pivot.activate(pivot)
    cmds.setAttr(pivot + ".rotateY", 90)
    temp_pivot.cancel(pivot)
    _no_temp_nodes(cmds, ctl)
    assert (
        cmds.listConnections(ctl + ".translateX", source=True, destination=False)
        == curve
    )
    assert cmds.keyframe(ctl + ".translateX", query=True, timeChange=True) == [
        1.0,
        10.0,
    ]
    after = _matrices_on(cmds, ctl, (1, 5, 10))
    for frame in (1, 5, 10):
        assert after[frame] == pytest.approx(before[frame], abs=1e-4)


def test_cancel_unkeyed_control(temp_pivot):
    from maya import cmds

    ctl = cmds.spaceLocator(name="ctl")[0]
    cmds.setAttr(ctl + ".translate", 1, 2, 3)
    pivot = temp_pivot.create([ctl], position=(4, 0, 0))
    temp_pivot.activate(pivot)
    cmds.setAttr(pivot + ".rotateY", 90)
    temp_pivot.cancel(pivot)
    _no_temp_nodes(cmds, ctl)
    assert not cmds.listConnections(ctl + ".translateX", source=True)
    assert cmds.getAttr(ctl + ".translate")[0] == pytest.approx((1, 2, 3))
    assert cmds.getAttr(ctl + ".rotateY") == pytest.approx(0)


def test_undo_steps(temp_pivot):
    from maya import cmds

    ctl = _keyed_ctl(cmds)
    pivot = temp_pivot.create([ctl])
    temp_pivot.activate(pivot)
    cmds.undo()
    assert temp_pivot.state(temp_pivot.find()) == "place"
    cmds.undo()
    assert temp_pivot.find() is None


def test_resume_after_save_and_reopen(temp_pivot, tmp_path):
    from maya import cmds

    ctl = _keyed_ctl(cmds)
    pivot = temp_pivot.create([ctl], position=(2, 0, 0), label="bookmark:Arms")
    temp_pivot.activate(pivot)
    path = str(tmp_path / "pivot.ma")
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii", force=True)
    cmds.file(new=True, force=True)
    cmds.file(path, open=True, force=True)
    pivot = temp_pivot.find()
    assert pivot
    assert temp_pivot.state(pivot) == "active"
    assert temp_pivot.info(pivot)["label"] == "bookmark:Arms"
    temp_pivot.bake(pivot)
    _no_temp_nodes(cmds, cmds.ls("ctl", long=True)[0])


def test_find_with_taken_name(temp_pivot):
    """The group is found when Maya had to rename it."""
    from maya import cmds

    cmds.createNode("transform", name="mgear_temp_pivot_grp")
    ctl = _keyed_ctl(cmds)
    pivot = temp_pivot.create([ctl])
    assert temp_pivot.find() == pivot
    temp_pivot.cancel(pivot)
    assert temp_pivot.find() is None
    assert cmds.objExists("mgear_temp_pivot_grp")
