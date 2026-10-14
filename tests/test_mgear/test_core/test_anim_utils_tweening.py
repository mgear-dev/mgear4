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


def test_keyable_nodes_alias(anim_utils):
    """keyable_nodes lives in core.attribute; anim_utils keeps the name."""
    from mgear.core import attribute

    assert anim_utils.keyable_nodes is attribute.keyable_nodes


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


# blend caches -------------------------------------------------------------


@pytest.fixture
def new_scene(anim_utils):
    from maya import cmds

    cmds.file(new=True, force=True)
    return cmds


def test_default_cache(anim_utils, new_scene):
    cmds = new_scene
    loc = cmds.spaceLocator(name="loc")[0]
    cmds.setAttr(loc + ".translateX", 4)
    cache = anim_utils.get_default_cache([loc])
    assert cache == [("loc.translateX", 4.0, 0.0, False)]


def test_default_cache_angle_units(anim_utils, new_scene):
    cmds = new_scene
    loc = cmds.spaceLocator(name="loc")[0]
    cmds.addAttr(
        loc, longName="ang", attributeType="doubleAngle", defaultValue=0.5, keyable=True
    )
    cmds.setAttr(loc + ".ang", 10)
    (entry,) = anim_utils.get_default_cache([loc])
    assert entry[0] == "loc.ang"
    assert entry[1] == pytest.approx(10.0)
    # 0.5 radians, in degrees like getAttr and setAttr
    assert entry[2] == pytest.approx(28.6478897)


def test_mirror_cache(anim_utils, new_scene):
    cmds = new_scene
    left = cmds.createNode("transform", name="arm_L0_fk0_ctl")
    right = cmds.createNode("transform", name="arm_R0_fk0_ctl")
    cmds.setAttr(left + ".rotateZ", 10)
    cmds.setAttr(right + ".rotateZ", 30)
    (entry,) = anim_utils.get_mirror_cache([left])
    # mirror channels use short attribute names
    assert entry[0] == "|arm_L0_fk0_ctl.rz"
    assert entry[1:3] == pytest.approx((10.0, 30.0))
    assert entry[3] is False


def test_mirror_cache_animated_plugs(anim_utils, new_scene):
    """Animated plugs are blended (keyed), not skipped."""
    cmds = new_scene
    left = cmds.createNode("transform", name="arm_L0_fk0_ctl")
    right = cmds.createNode("transform", name="arm_R0_fk0_ctl")
    cmds.setKeyframe(left, attribute="rotateZ", time=1, value=10)
    cmds.setAttr(right + ".rotateZ", 30)
    cmds.currentTime(1)
    cache = anim_utils.get_mirror_cache([left])
    assert len(cache) == 1
    assert cache[0][0] == "|arm_L0_fk0_ctl.rz"
    assert cache[0][3] is True
    anim_utils.apply_blend(cache, 1.0)
    assert cmds.getAttr(left + ".rotateZ") == pytest.approx(30.0)
    assert cmds.getAttr(right + ".rotateZ") == pytest.approx(30.0)


def test_buffer_cache_skips_missing(anim_utils, new_scene):
    cmds = new_scene
    cmds.spaceLocator(name="ctl")
    cache = anim_utils.get_buffer_cache(
        {"ctl": {"translateX": 6, "missingAttr": 1}, "missing_node": {"tx": 0}}
    )
    assert cache == [("ctl.translateX", 0.0, 6.0, False)]


def test_push_cache(anim_utils, keyed_ctl):
    from maya import cmds

    cmds.setKeyframe(keyed_ctl, attribute="translateX", time=6, value=8)
    cache = anim_utils.get_push_cache([keyed_ctl], time=6)
    assert cache == [("ctl.translateX", 5.0, 8.0, True)]


def test_blend_caches_skip_locked_and_driven(anim_utils, new_scene):
    cmds = new_scene
    ctl = cmds.spaceLocator(name="ctl")[0]
    driver = cmds.spaceLocator(name="driver")[0]
    cmds.setAttr(ctl + ".translateX", 3)
    cmds.setAttr(ctl + ".translateX", lock=True)
    cmds.setAttr(driver + ".rotateY", 20)
    cmds.connectAttr(driver + ".rotateY", ctl + ".rotateY")
    plugs = [entry[0] for entry in anim_utils.get_default_cache([ctl])]
    assert "ctl.translateX" not in plugs
    assert "ctl.rotateY" not in plugs
    cache = anim_utils.get_buffer_cache({ctl: {"translateX": 0, "rotateY": 0}})
    assert cache == []


def test_apply_blend_exaggerate(anim_utils, new_scene):
    cmds = new_scene
    cmds.spaceLocator(name="ctl")
    cmds.setAttr("ctl.translateX", 4)
    anim_utils.apply_blend([("ctl.translateX", 4.0, 0.0, False)], -1.0)
    assert cmds.getAttr("ctl.translateX") == pytest.approx(8.0)
    assert not cmds.keyframe("ctl.translateX", query=True)


@pytest.mark.parametrize("mode", ["off", "parallel"])
def test_apply_blend_keyed_and_visible(anim_utils, keyed_ctl, mode):
    from maya import cmds

    cmds.evaluationManager(mode=mode)
    try:
        cmds.currentTime(5)
        anim_utils.apply_blend([("ctl.translateX", 4.0, 0.0, True)], 0.5)
        assert cmds.keyframe(
            "ctl.translateX", query=True, time=(5, 5), valueChange=True
        ) == [2.0]
        assert cmds.getAttr("ctl.translateX") == pytest.approx(2.0)
    finally:
        cmds.evaluationManager(mode="off")


def test_get_pose_values(anim_utils, new_scene):
    cmds = new_scene
    ctl = cmds.spaceLocator(name="ctl")[0]
    cmds.setAttr(ctl + ".translateX", 6)
    cmds.setAttr(ctl + ".translateY", lock=True)
    pose = anim_utils.get_pose_values([ctl])
    assert pose[ctl]["translateX"] == 6
    assert "translateY" not in pose[ctl]
    assert set(pose[ctl]) == set(anim_utils.blend_attributes(ctl))
