import pymel.core as pm
import math

from mgear.core import attribute
from mgear.core import transform
from mgear.core import primitive
from mgear.core import applyop


SPRING_ATTRS = [
    "springTotalIntensity",
    "springTranslationalIntensity",
    "springTranslationalDamping",
    "springTranslationalStiffness",
    "springRotationalIntensity",
    "springRotationalDamping",
    "springRotationalStiffness",
    "springSetupMembers",
]


def create_settings_attr(node):
    """Add specified spring attributes from a given Maya node.

    Args:
        node (str or PyNode): The name or PyNode of the node from which
                              to add attributes.
    """
    if isinstance(node, str):
        node = pm.PyNode(node)
    attribute.addAttribute(
        node,
        "springTotalIntensity",
        "float",
        1,
        minValue=0,
        maxValue=1,
    )
    attribute.addAttribute(
        node,
        "springTranslationalIntensity",
        "float",
        0,
        minValue=0,
        maxValue=1,
    )
    attribute.addAttribute(
        node,
        "springTranslationalDamping",
        "float",
        0.5,
        minValue=0,
        maxValue=1,
    )
    attribute.addAttribute(
        node,
        "springTranslationalStiffness",
        "float",
        0.5,
        minValue=0,
        maxValue=1,
    )
    attribute.addAttribute(
        node,
        "springRotationalIntensity",
        "float",
        1,
        minValue=0,
        maxValue=1,
    )
    attribute.addAttribute(
        node,
        "springRotationalDamping",
        "float",
        0.5,
        minValue=0,
        maxValue=1,
    )
    attribute.addAttribute(
        node,
        "springRotationalStiffness",
        "float",
        0.5,
        minValue=0,
        maxValue=1,
    )
    # add message attr to node
    node.addAttr("springSetupMembers", at="message", m=True)


def remove_settings_attr(node):
    """
    Remove specified spring attributes from a given Maya node.

    Args:
        node (str or PyNode): The name or PyNode of the node from which
                              to remove attributes.

    Returns:
        None
    """
    # Convert to PyNode if node is given as a string
    if isinstance(node, str):
        node = pm.PyNode(node)

    # Loop through each attribute and attempt to remove it if it exists
    for attr in SPRING_ATTRS:
        if pm.attributeQuery(attr, node=node, exists=True):
            pm.deleteAttr(node.attr(attr))
            print("Removed attribute " + attr + " from " + str(node))
        else:
            print("Attribute " + attr + " does not exist on " + str(node))


def get_settings_attr_val(node):
    """
    Get the values of the spring attributes on a given Maya node.

    Args:
        node (str or PyNode): The name or PyNode of the node from which
                              to get the attribute values.

    Returns:
        dict: A dictionary of the attribute values.
    """
    # Convert to PyNode if node is given as a string
    if isinstance(node, str):
        node = pm.PyNode(node)

    # Create a dictionary to store the attribute values
    attr_vals = {}

    # Loop through each attribute and attempt to get its value
    for attr in SPRING_ATTRS[:-1]:
        if pm.attributeQuery(attr, node=node, exists=True):
            attr_vals[attr] = node.attr(attr).get()
        else:
            print("Attribute " + attr + " does not exist on " + str(node))

    return attr_vals


def set_settings_attr_val(node, attr_vals):
    """
    Set the values of the spring attributes on a given Maya node.

    Args:
        node (str or PyNode): The name or PyNode of the node on which
                              to set the attribute values.
        attr_vals (dict): A dictionary of the attribute values.

    Returns:
        None
    """
    # Convert to PyNode if node is given as a string
    if isinstance(node, str):
        node = pm.PyNode(node)

    # Loop through each attribute and attempt to set its value
    for attr in SPRING_ATTRS[:-1]:
        if pm.attributeQuery(attr, node=node, exists=True):
            node.attr(attr).set(attr_vals[attr])
        else:
            print("Attribute " + attr + " does not exist on " + str(node))


# check if object has spring by checking if has attr springSetupMembers
def has_spring(node):
    if pm.attributeQuery("springSetupMembers", node=node, exists=True):
        return True
    else:
        return False


def get_name(node, name):
    """
    Return a name composed of the node name + name.
    """

    if isinstance(node, pm.PyNode):
        node_name = node.name()
    else:
        node_name = node
    return node_name + "_" + name


# TODO: Node is also in config as string, so not need to pass here
def create_spring(node, config):
    def get_name(name, node=node):
        """
        Return a name composed of the node name + name.
        """

        if isinstance(node, pm.PyNode):
            node_name = node.name()
        else:
            node_name = node
        return node_name + "_" + name

    # add settings attr
    create_settings_attr(node)

    # Get node transform
    t = transform.getTransform(node)

    parent = node.getParent()

    # create root
    root = primitive.addTransform(parent, get_name("sprg_root"), t)

    # translate spring
    trans_sprg = primitive.addTransform(root, get_name("sprg_trans"), t)

    # aim direction root
    aim_root = primitive.addTransform(trans_sprg, get_name("sprg_aim"), t)

    # aim direction goal
    aim_goal = primitive.addTransform(aim_root, get_name("sprg_goal"), t)

    directions = {
        "x": ["tx", 1],
        "y": ["ty", 1],
        "z": ["tz", 1],
        "-x": ["tx", -1],
        "-y": ["ty", -1],
        "-z": ["tz", -1],
    }
    try:
        direction = directions[config["direction"]]
    except KeyError:
        raise KeyError("Invalid direction specified in config.")
    aim_root.attr(direction[0]).set(direction[1])
    aim_goal.attr(direction[0]).set(direction[1])

    # spring driver
    driver = primitive.addTransform(trans_sprg, get_name("sprg_driver"), t)

    # connect metadata
    attribute.connect_message(
        [root, trans_sprg, aim_root, aim_goal, driver], node.springSetupMembers
    )

    # position spring
    sprg_pos_node = applyop.gear_spring_op(trans_sprg, root)

    # direction spring
    sprg_rot_node = applyop.gear_spring_op(aim_goal, aim_root)

    # aim direction

    return driver


def delete_spring(node):
    return


# init the configuration to create a spring
"""
config = {
    "node" : "node_name",
    "direction" : "x",
    "springTotalIntensity": 1,
    "springTranslationalIntensity": 0,
    "springTranslationalDamping": 0.5,
    "springTranslationalStiffness": 0.5,
    "springRotationalIntensity": 1,
    "springRotationalDamping": 0.5,
    "springRotationalStiffness": 0.5,

}
"""


def init_config(node, direction):
    # if node is pynode get node str name
    if isinstance(node, pm.PyNode):
        node = node.name()
    config = {
        "node": node,
        "direction": direction,
        "springTotalIntensity": 1,
        "springTranslationalIntensity": 0,
        "springTranslationalDamping": 0.5,
        "springTranslationalStiffness": 0.5,
        "springRotationalIntensity": 1,
        "springRotationalDamping": 0.5,
        "springRotationalStiffness": 0.5,
    }
    return config


def get_child_axis_direction(child_node):
    """
    Get the axis direction ('x', 'y', 'z', '-x', '-y', '-z') of a child node
    relative to its parent node.

    Args:
        child_node (str or PyNode): The child node name or PyNode object.

    Returns:
        str: The axis direction ('x', 'y', 'z', '-x', '-y', '-z')
             or 'ambiguous' if the direction is not clear.
    """

    # Convert to PyNode if the child node is given as a string
    if isinstance(child_node, str):
        child_node = pm.PyNode(child_node)

    # Get the parent node
    parent_node = pm.listRelatives(child_node, p=True)
    if not parent_node:
        return "No parent found"
    parent_node = parent_node[0]

    # Get local translation of the child relative to the parent
    local_translation = child_node.getTranslation(space="object")

    # Determine axis direction
    axis = None
    max_val = 0
    for ax, val in zip(
        ["x", "y", "z"],
        [local_translation.x, local_translation.y, local_translation.z],
    ):
        if math.fabs(val) > max_val:
            max_val = math.fabs(val)
            axis = ax

    if max_val == 0:
        return "ambiguous"

    # Check for the sign of the maximum value along the axis
    axis_value = getattr(local_translation, axis)
    if axis_value < 0:
        axis = "-" + axis

    return axis


def get_config(node):
    # get config dict from node attrs
    if isinstance(node, pm.PyNode):
        node_name = node.name()
    else:
        node_name = node
    # TODO: get child node name from the spring members
    child_node = pm.listRelatives(node, c=True)
    direction = get_child_axis_direction(child_node)
    config = {
        "node": node_name,
        "direction": direction,
    }
    attr_val = get_settings_attr_val(node)
    config.update(attr_val)
    return config


def get_preset(nodes):
    preset = {}
    return preset


# store preset configuration
def store_preset(nodes, filePath=None):
    preset = get_preset(nodes)
    return preset


# store preset configuration, from selected springs
def store_preset_from_selection(filePath=None):
    nodes = pm.selected()
    store_preset(nodes, filePath)


# apply spring from a  preset
def apply_preset(preset):
    return


def remove_preset(preset):
    return


# should process several nodes at the same time
def bake(nodes):
    return


def bake_all():
    return


def clear_bake(nodes):
    return


def clear_bake_all():
    return


def bake_preset(preset):
    return


def clear_bake_preset(preset):
    return


def move_animation_curves(source_node, target_node):
    """
    Move animation curves connected to one node to another node.

    Args:
        source_node (str): The name of the node with the animation curves.
        target_node (str): The name of the node to which animation curves
                           should be moved.

    Returns:
        None
    """

    attributes_to_check = ["translate", "rotate", "scale"]

    for attr in attributes_to_check:
        for axis in ["X", "Y", "Z"]:
            compound_attr = "{}{}".format(attr, axis)
            source_plug = "{}.{}".format(source_node, compound_attr)
            target_plug = "{}.{}".format(target_node, compound_attr)

            # Check if the attribute exists and is animated
            if pm.attributeQuery(compound_attr, node=source_node, exists=True):
                anim_curves = pm.listConnections(source_plug, type="animCurve")
                for curve in anim_curves:
                    # Disconnect curve from source node and connect to target node
                    pm.disconnectAttr(curve + ".output", source_plug)
                    pm.connectAttr(curve + ".output", target_plug)

        compound_attr = (
            attr  # for compound plugs like 'translate', 'rotate', 'scale'
        )
        source_plug = "{}.{}".format(source_node, compound_attr)
        target_plug = "{}.{}".format(target_node, compound_attr)

        # Check if the attribute exists and is animated
        if pm.attributeQuery(compound_attr, node=source_node, exists=True):
            anim_curves = pm.listConnections(source_plug, type="animCurve")
            for curve in anim_curves:
                # Disconnect curve from source node and connect to target node
                pm.disconnectAttr(curve + ".output", source_plug)
                pm.connectAttr(curve + ".output", target_plug)
