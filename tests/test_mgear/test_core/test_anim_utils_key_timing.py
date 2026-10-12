"""Tests for the key timing helpers of mgear.core.anim_utils."""

import pytest


@pytest.fixture
def ctl(anim_utils):
    """Locator with translateX keyed at frames 1, 5 and 10."""
    from maya import cmds

    cmds.file(new=True, force=True)
    node = cmds.spaceLocator(name="ctl")[0]
    for frame in (1, 5, 10):
        cmds.setKeyframe(node, attribute="translateX", time=frame, value=frame)
    return node


def _times(plug="ctl.translateX"):
    from maya import cmds

    return cmds.keyframe(plug, query=True, timeChange=True)


def _values(plug="ctl.translateX"):
    from maya import cmds

    return cmds.keyframe(plug, query=True, valueChange=True)


def test_timeline_range_batch(anim_utils):
    assert anim_utils.get_timeline_range() is None


def test_has_selected_keys(anim_utils, ctl):
    from maya import cmds

    cmds.selectKey(clear=True)
    assert anim_utils.has_selected_keys() is False
    cmds.selectKey("ctl.translateX", time=(5, 5))
    assert anim_utils.has_selected_keys() is True
    cmds.selectKey(clear=True)
    assert anim_utils.has_selected_keys() is False


def test_nudge_current_frame_key(anim_utils, ctl):
    assert anim_utils.nudge_keys([ctl], 5, 5, 2) == 1
    assert _times() == [1.0, 7.0, 10.0]
    assert _values() == [1.0, 5.0, 10.0]


def test_nudge_blocked_by_neighbor(anim_utils, ctl):
    with pytest.raises(ValueError):
        anim_utils.nudge_keys([ctl], 5, 5, 5)
    assert _times() == [1.0, 5.0, 10.0]


def test_nudge_blocked_passing_neighbor(anim_utils, ctl):
    with pytest.raises(ValueError):
        anim_utils.nudge_keys([ctl], 5, 5, 7)
    assert _times() == [1.0, 5.0, 10.0]


def test_nudge_ripple(anim_utils, ctl):
    assert anim_utils.nudge_keys([ctl], 5, 5, 5, ripple=True) == 2
    assert _times() == [1.0, 10.0, 15.0]


def test_nudge_ripple_backward_blocked(anim_utils, ctl):
    with pytest.raises(ValueError):
        anim_utils.nudge_keys([ctl], 5, 5, -4, ripple=True)
    assert _times() == [1.0, 5.0, 10.0]


def test_nudge_range(anim_utils, ctl):
    assert anim_utils.nudge_keys([ctl], 4, 11, 2) == 2
    assert _times() == [1.0, 7.0, 12.0]


def test_nudge_attribute_filter(anim_utils, ctl):
    from maya import cmds

    cmds.setKeyframe(ctl, attribute="translateY", time=5, value=1)
    anim_utils.nudge_keys([ctl], 5, 5, 1, attributes=["translateY"])
    assert _times("ctl.translateY") == [6.0]
    assert _times() == [1.0, 5.0, 10.0]


def test_nudge_blocked_moves_nothing_on_other_curves(anim_utils, ctl):
    """One blocked curve blocks the whole nudge."""
    from maya import cmds

    cmds.setKeyframe(ctl, attribute="translateY", time=5, value=1)
    cmds.setKeyframe(ctl, attribute="translateY", time=6, value=2)
    with pytest.raises(ValueError):
        anim_utils.nudge_keys([ctl], 5, 5, 1)
    assert _times() == [1.0, 5.0, 10.0]
    assert _times("ctl.translateY") == [5.0, 6.0]


def test_nudge_selected_keys(anim_utils, ctl):
    from maya import cmds

    cmds.selectKey("ctl.translateX", time=(5, 5))
    assert anim_utils.nudge_selected_keys(2) == 1
    assert _times() == [1.0, 7.0, 10.0]
    assert cmds.keyframe("ctl.translateX", query=True, selected=True) == [7.0]


def test_nudge_selected_keys_ripple(anim_utils, ctl):
    from maya import cmds

    cmds.selectKey("ctl.translateX", time=(5, 5))
    assert anim_utils.nudge_selected_keys(3, ripple=True) == 2
    assert _times() == [1.0, 8.0, 13.0]
    assert cmds.keyframe("ctl.translateX", query=True, selected=True) == [8.0]


def test_nudge_selected_keys_blocked(anim_utils, ctl):
    from maya import cmds

    cmds.selectKey("ctl.translateX", time=(5, 5))
    with pytest.raises(ValueError):
        anim_utils.nudge_selected_keys(5)
    assert _times() == [1.0, 5.0, 10.0]


def test_nudge_undo(anim_utils, ctl):
    from maya import cmds
    from mgear.core import utils

    with utils.undo_chunk("nudge"):
        anim_utils.nudge_keys([ctl], 5, 5, 2)
    cmds.undo()
    assert _times() == [1.0, 5.0, 10.0]


def test_world_matrices(anim_utils):
    from maya import cmds

    cmds.file(new=True, force=True)
    loc = cmds.spaceLocator()[0]
    cmds.setAttr(loc + ".translate", 1, 2, 3)
    (matrix,) = anim_utils.get_world_matrices([loc])
    assert len(matrix) == 16
    assert matrix[12:] == pytest.approx([1, 2, 3, 1])
