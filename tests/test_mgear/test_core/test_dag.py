"""mgear.core.dag tests"""

import pytest


def scan_child(root, name):
    """Find a child the way findChild did before the name lookup.

    Lists every transform under the root and returns the long name of the
    first one with a matching short name.

    Args:
        root (str): The root node name.
        name (str): The short name to search.

    Returns:
        str: Long name of the child, or None if not found.
    """
    from maya import cmds

    children = cmds.listRelatives(
        root, allDescendents=True, type="transform", fullPath=True
    )
    for item in children or []:
        if item.split("|")[-1] == name:
            return item
    return None


@pytest.fixture
def scene(setup_path):
    """Two guide-like hierarchies sharing child names, in a new scene.

    ::

        guide|root_C0|arm_L0_root|arm_L0_elbow
                     |clash|dup
                     |dup
                     |jnt (joint)
        other|root_C0|arm_L0_root|arm_L0_elbow

    Returns:
        module: maya.cmds.
    """
    from maya import cmds

    cmds.file(new=True, force=True)
    for top in ("guide", "other"):
        cmds.group(name=top, empty=True, world=True)
        cmds.group(name="root_C0", empty=True, parent=top)
        cmds.group(name="arm_L0_root", empty=True, parent=top + "|root_C0")
        cmds.group(name="arm_L0_elbow", empty=True, parent=top + "|root_C0|arm_L0_root")
    cmds.group(name="clash", empty=True, parent="guide|root_C0")
    cmds.group(name="dup", empty=True, parent="guide|root_C0|clash")
    cmds.group(name="dup", empty=True, parent="guide|root_C0")
    cmds.select(clear=True)
    joint = cmds.joint(name="jnt")
    cmds.parent(joint, "guide|root_C0")
    cmds.group(name="leaf", empty=True, world=True)
    return cmds


def long_name(node):
    """Long name of a findChild result (node or string)."""
    from maya import cmds

    return cmds.ls(str(node), long=True)[0]


@pytest.mark.parametrize(
    "root, name",
    [
        ("guide", "arm_L0_elbow"),
        ("other", "arm_L0_elbow"),
        ("guide|root_C0", "arm_L0_root"),
    ],
)
def test_find_child_unique(scene, root, name):
    import mgear.pymaya as pm
    from mgear.core import dag

    found = dag.findChild(pm.PyNode(root), name)

    assert not isinstance(found, str)
    assert long_name(found) == scan_child(root, name)


def test_find_child_joint(scene):
    import mgear.pymaya as pm
    from mgear.core import dag

    found = dag.findChild(pm.PyNode("guide"), "jnt")

    assert scene.nodeType(found.longName()) == "joint"


def test_find_child_not_under_root(scene):
    import mgear.pymaya as pm
    from mgear.core import dag

    # exists in the scene, but not under "other"
    assert dag.findChild(pm.PyNode("other"), "clash") is False
    assert dag.findChild(pm.PyNode("guide"), "missing") is False


def test_find_child_clash_under_root(scene):
    import mgear.pymaya as pm
    from mgear.core import dag

    found = dag.findChild(pm.PyNode("guide"), "dup")

    assert long_name(found) == scan_child("guide", "dup")


@pytest.mark.parametrize("name", ["arm_L0_*", "arm_L0_elbo?", "root_C0|arm_L0_root"])
def test_find_child_pattern_names_match_exactly(scene, name):
    import mgear.pymaya as pm
    from mgear.core import dag

    # Names are compared literally, never as patterns or paths.
    assert dag.findChild(pm.PyNode("guide"), name) is False


def test_find_child_without_descendants(scene):
    import mgear.pymaya as pm
    from mgear.core import dag

    assert dag.findChild(pm.PyNode("leaf"), "arm_L0_elbow") is False


def test_find_child_unique_name_does_not_scan(scene, count_calls):
    import mgear.pymaya as pm
    from mgear.core import dag

    root = pm.PyNode("guide")
    calls = count_calls(dag.cmds, "listRelatives")

    assert dag.findChild(root, "arm_L0_elbow")
    assert calls == []
