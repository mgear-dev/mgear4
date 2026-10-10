"""Tests for the rig queries of mgear.core.anim_utils used by the dag menu."""

import inspect

import pytest


def test_find_rig_root(anim_utils, shifter_rig):
    assert anim_utils.find_rig_root("arm_C0_fk0_ctl") == "rig"
    assert anim_utils.find_rig_root("rig") == "rig"


def test_find_rig_root_under_group(anim_utils, shifter_rig):
    cmds = shifter_rig
    cmds.group("rig", name="ref_grp")
    assert anim_utils.find_rig_root("arm_C0_fk0_ctl") == "rig"


def test_find_rig_root_outside_rig(anim_utils, shifter_rig):
    cmds = shifter_rig
    loc = cmds.spaceLocator(name="lonely_loc")[0]
    assert anim_utils.find_rig_root(loc) is None
    assert anim_utils.find_rig_root("does_not_exist") is None


def test_find_rig_root_namespace(anim_utils, namespaced_rig):
    assert anim_utils.find_rig_root("char:arm_C0_fk0_ctl") == "char:rig"


def test_space_switch_targets_arm_ik(anim_utils, shifter_rig):
    targets = anim_utils.get_space_switch_targets("global_C0_ctl", "arm_ikref")
    assert targets == ["arm_C0_ik_ctl"]


def test_space_switch_targets_namespace(anim_utils, namespaced_rig):
    targets = anim_utils.get_space_switch_targets("char:global_C0_ctl", "arm_ikref")
    assert targets == ["arm_C0_ik_ctl"]


def test_space_switch_targets_no_role_match(anim_utils, shifter_rig):
    # control_01 has no "ik" role, so all the controls of the components
    # linked by control_id*_ctl_cnx are used
    targets = anim_utils.get_space_switch_targets("global_C0_ctl", "control_ikref")
    assert targets == ["control_C0_ctl", "control_C1_ctl"]


def test_space_switch_targets_fallback_role(anim_utils, shifter_rig):
    cmds = shifter_rig
    cmds.setAttr("control_C1_ctl.ctl_role", "other", type="string")
    targets = anim_utils.get_space_switch_targets(
        "global_C0_ctl", "control_ikref", fallback_role="ctl"
    )
    assert targets == ["control_C0_ctl"]


def test_space_switch_targets_control_map(anim_utils, shifter_rig):
    targets = anim_utils.get_space_switch_targets("global_C0_ctl", "arm_elbowref")
    assert targets == ["arm_C0_mid_ctl"]


def test_space_switch_targets_follow_own_control(anim_utils, shifter_rig):
    cmds = shifter_rig
    cmds.addAttr(
        "control_C1_ctl",
        longName="follow",
        attributeType="enum",
        enumName="a:b",
        keyable=True,
    )
    targets = anim_utils.get_space_switch_targets("control_C1_ctl", "follow")
    assert targets == ["control_C1_ctl"]


def test_space_control_map_is_shared(anim_utils):
    assert anim_utils.SPACE_CONTROL_MAP["rot"] == ("orbit", "fk0")
    assert anim_utils.SPACE_CONTROL_MAP["elbow"] == ("mid",)


def test_ikfk_components_arm(anim_utils, shifter_rig):
    fk_list, ik_dict, components = anim_utils.get_ikfk_components(
        "global_C0_ctl", "arm_blend"
    )
    assert fk_list == ["arm_C0_fk0_ctl", "arm_C0_fk1_ctl", "arm_C0_fk2_ctl"]
    assert ik_dict["ik_control"] == "arm_C0_ik_ctl"
    assert ik_dict["pole_vector"] == "arm_C0_upv_ctl"
    assert len(components) == 1
    assert components[0][1] == fk_list


def test_ikfk_components_no_match(anim_utils, shifter_rig):
    assert anim_utils.get_ikfk_components("global_C0_ctl", "leg_blend") == (
        [],
        {},
        [],
    )


def test_toggle_ctl_xray(anim_utils, shifter_rig):
    cmds = shifter_rig
    cmds.setAttr("rig.ctl_x_ray", False)
    assert anim_utils.toggle_ctl_xray("arm_C0_fk0_ctl") is True
    assert cmds.getAttr("rig.ctl_x_ray") is True
    assert anim_utils.toggle_ctl_xray("arm_C0_fk0_ctl") is False
    assert cmds.getAttr("rig.ctl_x_ray") is False


def test_toggle_ctl_xray_without_tag(anim_utils, shifter_rig):
    cmds = shifter_rig
    cmds.setAttr("rig.ctl_x_ray", False)
    tags = cmds.listConnections("arm_C0_fk0_ctl.message", type="controller")
    cmds.delete(tags)
    assert anim_utils.toggle_ctl_xray("arm_C0_fk0_ctl") is True


def test_toggle_ctl_xray_no_attr(anim_utils, shifter_rig):
    cmds = shifter_rig
    cmds.deleteAttr("rig.ctl_x_ray")
    assert anim_utils.toggle_ctl_xray("arm_C0_fk0_ctl") is None
    loc = cmds.spaceLocator(name="lonely_loc")[0]
    assert anim_utils.toggle_ctl_xray(loc) is None


@pytest.mark.parametrize(
    "name, params",
    (
        ("changeSpace", ["model", "uiHost", "combo_attr", "cnsIndex", "ctl_names"]),
        ("get_ik_fk_controls_by_role", ["uiHost", "attr_ctl_cnx"]),
    ),
)
def test_existing_signatures_unchanged(anim_utils, name, params):
    signature = inspect.signature(getattr(anim_utils, name))
    assert list(signature.parameters) == params
