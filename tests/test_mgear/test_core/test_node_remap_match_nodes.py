"""Tests for node_remap.match_nodes, the stored names to selection matcher."""

import pytest


@pytest.fixture
def node_remap(setup_path):
    from maya import cmds
    from mgear.core import node_remap

    cmds.file(new=True, force=True)
    return node_remap


def test_nothing_selected_uses_buffer_names(node_remap):
    from maya import cmds

    cmds.namespace(add="chrA")
    cmds.createNode("transform", name="chrA:hand_ctl")
    result = node_remap.match_nodes(["chrA:hand_ctl", "chrA:gone_ctl"], [])
    assert result == {"chrA:hand_ctl": "chrA:hand_ctl"}


def test_same_name(node_remap):
    result = node_remap.match_nodes(
        ["chrA:hand_ctl", "chrA:arm_ctl"], ["|rig|chrA:arm_ctl"]
    )
    assert result == {"chrA:arm_ctl": "|rig|chrA:arm_ctl"}


def test_other_namespace(node_remap):
    result = node_remap.match_nodes(["chrA:hand_ctl"], ["chrB:hand_ctl"])
    assert result == {"chrA:hand_ctl": "chrB:hand_ctl"}


def test_exact_name_wins_over_short_name(node_remap):
    result = node_remap.match_nodes(
        ["chrA:hand_ctl", "chrB:hand_ctl"], ["chrB:hand_ctl"]
    )
    assert result == {"chrB:hand_ctl": "chrB:hand_ctl"}


def test_partial_match_leaves_rest_unmatched(node_remap):
    result = node_remap.match_nodes(
        ["chrA:hand_ctl"], ["chrB:hand_ctl", "chrB:foot_ctl"]
    )
    assert result == {"chrA:hand_ctl": "chrB:hand_ctl"}


def test_index_pairing_first_n(node_remap):
    result = node_remap.match_nodes(["a", "b", "c"], ["x", "y", "z", "w", "v"])
    assert result == {"a": "x", "b": "y", "c": "z"}


def test_index_pairing_fewer_targets(node_remap):
    result = node_remap.match_nodes(["a", "b", "c"], ["x"])
    assert result == {"a": "x"}


def test_ambiguous_short_name_takes_first(node_remap):
    result = node_remap.match_nodes(
        ["chrA:hand_ctl", "chrB:hand_ctl"], ["chrC:hand_ctl"]
    )
    assert result == {"chrA:hand_ctl": "chrC:hand_ctl"}


def test_split_component(node_remap):
    assert node_remap.split_component("|grp|ns:body.f[0:10]") == ("ns:body", ".f[0:10]")
    assert node_remap.split_component("a:b:arm_ctl") == ("a:b:arm_ctl", "")


def test_swap_namespace(node_remap):
    assert node_remap.swap_namespace("chrA:body.f[0:10]", "chrB") == "chrB:body.f[0:10]"
    assert node_remap.swap_namespace("a:b:arm_ctl", "c") == "c:arm_ctl"
    assert node_remap.swap_namespace("chrA:arm_ctl", "") == "arm_ctl"
    assert node_remap.swap_namespace("arm_ctl", "chrA:") == "chrA:arm_ctl"
