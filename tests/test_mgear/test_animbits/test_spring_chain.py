"""mgear.animbits.spring_manager.chain test (pure logic)"""

import pytest


@pytest.fixture
def chain(setup_path):
    from mgear.animbits.spring_manager import chain

    return chain


def _children(hierarchy):
    return lambda name: hierarchy.get(name, [])


def test_straight_chain(chain):
    tree = chain.build_tree("a", _children({"a": ["b"], "b": ["c"]}))
    joints, sections, drivers = chain.plan(tree)
    assert [j.key for j in joints] == [
        ("bone", "a"),
        ("bone", "b"),
        ("bone", "c"),
        ("tip", "c"),
    ]
    assert [(s.bone, s.end) for s in sections] == [
        (("bone", "a"), ("bone", "b")),
        (("bone", "b"), ("bone", "c")),
        (("bone", "c"), ("tip", "c")),
    ]
    assert [s.ratio for s in sections] == pytest.approx([0.0, 1 / 3.0, 2 / 3.0])
    assert [s.end_ratio for s in sections] == pytest.approx([1 / 3.0, 2 / 3.0, 1.0])
    assert drivers == {"a": [("bone", "a")], "b": [("bone", "b")], "c": [("bone", "c")]}
    assert joints[1].parent == ("bone", "a")
    assert joints[2].aim == "tip"


def test_branch_policies(chain):
    # skirt-like: root with two chains
    hierarchy = {"root": ["l0", "r0"], "l0": ["l1"], "r0": ["r1"]}
    tree = chain.build_tree("root", _children(hierarchy))
    joints, sections, drivers = chain.plan(tree)
    keys = [j.key for j in joints]
    assert keys[:2] == [("pivot", "root"), ("branch", "root", 0)]
    assert ("branch", "root", 1) in keys
    # each branch simulated on its own, from the pivot
    branch_sections = [s for s in sections if s.bone[0] == "branch"]
    assert [s.end for s in branch_sections] == [("bone", "l0"), ("bone", "r0")]
    parents = {j.key: j.parent for j in joints}
    assert parents[("branch", "root", 1)] == ("pivot", "root")
    assert parents[("bone", "r0")] == ("branch", "root", 1)
    assert drivers["root"] == [("pivot", "root")]

    _, _, average = chain.plan(tree, chain.AVERAGE)
    assert average["root"] == [("branch", "root", 0), ("branch", "root", 1)]
    _, _, primary = chain.plan(tree, chain.PRIMARY, primary=1)
    assert primary["root"] == [("branch", "root", 1)]
    with pytest.raises(ValueError):
        chain.plan(tree, "bad")


def test_mid_chain_branch_and_ratio(chain):
    hierarchy = {"a": ["b"], "b": ["c", "d"], "c": ["e"]}
    tree = chain.build_tree("a", _children(hierarchy))
    joints, sections, _ = chain.plan(tree)
    first = sections[0]
    # a's section ends at b's pivot
    assert first.end == ("pivot", "b")
    ratios = {s.bone: s.ratio for s in sections}
    assert ratios[("bone", "a")] == 0.0
    assert ratios[("bone", "c")] == pytest.approx(0.5)


def test_joint_ratios_continuous_on_unequal_branches(chain):
    # root with a three-control branch and a one-control branch
    hierarchy = {"r": ["l0", "s0"], "l0": ["l1"], "l1": ["l2"]}
    tree = chain.build_tree("r", _children(hierarchy))
    _, sections, _ = chain.plan(tree)
    by_bone = {s.bone: s for s in sections}
    # the short branch's joint has one ratio for both sections meeting there
    assert by_bone[("branch", "r", 1)].ratio == 0.0
    assert by_bone[("branch", "r", 1)].end_ratio == pytest.approx(0.5)
    assert by_bone[("bone", "s0")].ratio == pytest.approx(0.5)
    assert by_bone[("bone", "s0")].end_ratio == 1.0
    # every section ends at the ratio its child sections start
    for section in sections:
        for child in sections:
            if child.bone == section.end or (
                section.end[0] == "pivot" and child.bone[1] == section.end[1]
            ):
                assert child.ratio == pytest.approx(section.end_ratio)
    # the long branch is unchanged
    long_ratios = [by_bone[key].ratio for key in (("bone", "l0"), ("bone", "l1"))]
    assert long_ratios == pytest.approx([0.25, 0.5])


def test_split_and_data(chain):
    hierarchy = {"t0": ["t1"], "t1": ["a0", "b0"], "a0": ["a1"]}
    tree = chain.build_tree("t0", _children(hierarchy), exclude={"b0"})
    assert [n.name for n in tree.walk()] == ["t0", "t1", "a0", "a1"]

    tree = chain.build_tree("t0", _children(hierarchy))
    trees = chain.split_branches(tree)
    assert [[n.name for n in t.walk()] for t in trees] == [
        ["t0", "t1"],
        ["a0", "a1"],
        ["b0"],
    ]

    data = chain.tree_to_data(tree)
    rebuilt = chain.tree_from_data(data, rename=lambda name: "ns:" + name)
    assert [n.name for n in rebuilt.walk()] == [
        "ns:t0",
        "ns:t1",
        "ns:a0",
        "ns:a1",
        "ns:b0",
    ]
