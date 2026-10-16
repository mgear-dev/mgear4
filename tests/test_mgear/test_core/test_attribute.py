"""mgear.core.attribute tests"""

import pytest


@pytest.fixture
def node(setup_path):
    """A transform with a colour, an array and a plain attribute.

    Returns:
        str: The node name.
    """
    from maya import cmds

    cmds.file(new=True, force=True)
    name = cmds.createNode("transform", name="node")
    cmds.addAttr(
        name,
        longName="color",
        shortName="clr",
        usedAsColor=True,
        attributeType="float3",
    )
    for axis in "RGB":
        cmds.addAttr(
            name, longName="color" + axis, attributeType="float", parent="color"
        )
    cmds.addAttr(name, longName="items", attributeType="double", multi=True)
    cmds.addAttr(name, longName="plain", attributeType="double")
    return name


def test_connected_input_attributes_none(node):
    from mgear.core import attribute

    assert attribute.get_connected_input_attributes(node) == set()


def test_connected_input_attributes(node):
    from maya import cmds

    from mgear.core import attribute

    cmds.connectAttr("persp.translateX", node + ".colorG")
    cmds.connectAttr("persp.translateY", node + ".items[3]")
    cmds.connectAttr("persp.translateZ", node + ".translateX")
    # outgoing connections don't count
    cmds.connectAttr(node + ".plain", "persp.scaleX")

    found = attribute.get_connected_input_attributes(node)

    assert found == {"color", "clr", "items", "translate", "t"}


def test_connected_input_attributes_function_set(node):
    from maya import cmds

    from mgear.core import attribute
    from mgear.core import utils

    cmds.connectAttr("persp.translateX", node + ".plain")
    fn_node = utils.get_dependency_node(node)

    assert attribute.get_connected_input_attributes(fn_node) == {"plain"}
