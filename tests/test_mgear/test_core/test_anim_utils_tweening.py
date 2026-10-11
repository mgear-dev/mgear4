"""Tests for the tweening helpers of mgear.core.anim_utils."""

import pytest


@pytest.fixture
def keyed_ctl(anim_utils):
    """Locator with translateX keyed 0 at frame 1 and 10 at frame 11."""
    from maya import cmds

    cmds.file(new=True, force=True)
    ctl = cmds.spaceLocator(name="ctl")[0]
    cmds.setKeyframe(ctl, attribute="translateX", time=1, value=0)
    cmds.setKeyframe(ctl, attribute="translateX", time=11, value=10)
    return ctl


def test_keyable_nodes_mixed_items(anim_utils, keyed_ctl):
    from maya import cmds

    mesh = cmds.polyCube(name="body")[0]
    items = [keyed_ctl, mesh + ".f[0:2]", keyed_ctl, "missing_node"]
    assert anim_utils.keyable_nodes(items) == [keyed_ctl]


def test_keyable_nodes_without_keyable_attrs(anim_utils, keyed_ctl):
    from maya import cmds

    locked = cmds.spaceLocator(name="locked")[0]
    for attr in cmds.listAttr(locked, keyable=True):
        cmds.setAttr("{}.{}".format(locked, attr), keyable=False)
    assert anim_utils.keyable_nodes([locked, keyed_ctl]) == [keyed_ctl]


def test_keyable_nodes_empty(anim_utils):
    assert anim_utils.keyable_nodes([]) == []
    assert anim_utils.keyable_nodes(None) == []


def test_tween_cache_between_keys(anim_utils, keyed_ctl):
    cache = anim_utils.get_tween_cache([keyed_ctl], time=5)
    assert cache == [("ctl.translateX", 0.0, 10.0)]


def test_tween_cache_on_existing_key(anim_utils, keyed_ctl):
    from maya import cmds

    cmds.setKeyframe(keyed_ctl, attribute="translateX", time=6, value=5)
    cache = anim_utils.get_tween_cache([keyed_ctl], time=6)
    assert cache == [("ctl.translateX", 0.0, 10.0)]


def test_tween_cache_skips_static_and_edge_attrs(anim_utils, keyed_ctl):
    from maya import cmds

    # translateZ only has keys at and after the tween frame
    cmds.setKeyframe(keyed_ctl, attribute="translateZ", time=5, value=1)
    cmds.setKeyframe(keyed_ctl, attribute="translateZ", time=9, value=2)
    plugs = [entry[0] for entry in anim_utils.get_tween_cache([keyed_ctl], 5)]
    assert plugs == ["ctl.translateX"]


def test_tween_cache_current_time(anim_utils, keyed_ctl):
    from maya import cmds

    cmds.currentTime(3)
    assert anim_utils.get_tween_cache([keyed_ctl]) == [("ctl.translateX", 0.0, 10.0)]


def test_apply_tween_halfway(anim_utils, keyed_ctl):
    from maya import cmds

    cache = anim_utils.get_tween_cache([keyed_ctl], time=5)
    anim_utils.apply_tween(cache, 0.5, time=5)
    assert cmds.keyframe(
        "ctl.translateX", query=True, time=(5, 5), valueChange=True
    ) == [5.0]


def test_apply_tween_clamped(anim_utils, keyed_ctl):
    from maya import cmds

    cache = anim_utils.get_tween_cache([keyed_ctl], time=5)
    anim_utils.apply_tween(cache, 1.4, time=5)
    assert cmds.keyframe(
        "ctl.translateX", query=True, time=(5, 5), valueChange=True
    ) == [10.0]
    anim_utils.apply_tween(cache, -0.5, time=5)
    assert cmds.keyframe(
        "ctl.translateX", query=True, time=(5, 5), valueChange=True
    ) == [0.0]


def test_apply_tween_rotation_units(anim_utils):
    """Rotation values round-trip in the UI unit (degrees)."""
    from maya import cmds

    cmds.file(new=True, force=True)
    ctl = cmds.spaceLocator(name="rot_ctl")[0]
    cmds.setKeyframe(ctl, attribute="rotateY", time=1, value=0)
    cmds.setKeyframe(ctl, attribute="rotateY", time=11, value=90)
    cache = anim_utils.get_tween_cache([ctl], time=5)
    anim_utils.apply_tween(cache, 0.5, time=5)
    values = cmds.keyframe("rot_ctl.rotateY", query=True, time=(5, 5), valueChange=True)
    assert values[0] == pytest.approx(45.0)


@pytest.mark.parametrize("mode", ["off", "parallel"])
def test_apply_tween_updates_evaluated_value(anim_utils, keyed_ctl, mode):
    """The pose changes at once, not only the key (regression)."""
    from maya import cmds

    cmds.evaluationManager(mode=mode)
    try:
        cmds.currentTime(5)
        cache = anim_utils.get_tween_cache([keyed_ctl])
        anim_utils.apply_tween(cache, 0.9)
        assert cmds.getAttr("ctl.translateX") == pytest.approx(9.0)
    finally:
        cmds.evaluationManager(mode="off")
