import maya.cmds as cmds
import maya.api.OpenMaya as om

def animation_layer_exists(layer_name):
    """Checks ig animation layer exists.

    :param str layer_name: Name of the layer that will be checked.
    :return: True if the animation layer exists
    :rtype: bool
    """
    is_anim_layer = False

    if not layer_name:
        return False
    exists = cmds.objExists(layer_name)

    if exists:
        is_anim_layer = cmds.nodeType(layer_name) == "animLayer"

    return exists and is_anim_layer


def base_animation_layer_name():
    """Finds the name of the base animation layer, as this base layer might not 
    be named the default "BaseAnimation".

    :return: name of the base animation layer.
    :rtype: str
    """
    if animation_layer_exists("BaseAnimation"):
        return "BaseAnimation"

    # BaseAnimation Layer might have been renamed, perform dg lookup.
    nodes = find_anim_layer_base_nodes()

    # No nodes found
    if len(nodes) == 0:
        return ""
    return om.MFnDependencyNode(nodes[0]).name()


def find_anim_layer_base_nodes():
    """Finds the animation base layer, as this base layer might not 
    be named the default "BaseAnimation".

    :return: list of Maya Objects.
    :rtype: list[om.MObject]
    """
    anim_layer_nodes = []

    # Create an iterator to iterate through all nodes
    it = om.MItDependencyNodes(om.MFn.kAnimLayer)

    while not it.isDone():
        # Get the animation layer node
        m_obj = it.thisNode()

        layer_dg = om.MFnDependencyNode(m_obj)
        child_plug_obj = layer_dg.findPlug("childrenLayers", False)
        child_plug = om.MPlug(child_plug_obj)

        # Animation layer has connected children, then it is the
        # "BaseAnimation" layer.
        if child_plug.numConnectedElements() > 0:
            # Append the animation layer node to the list
            anim_layer_nodes.append(m_obj)

        # Move to the next node
        it.next()

    return anim_layer_nodes


def all_anim_layers_ordered(include_base_animation=True):
    """Recursive function that returns all available animation layers within current scene.

    :return: list of animation layers.
    :rtype: list[str]
    """

    def _add_node_recursive(layer_node):
        all_layers.append(layer_node)
        child_layers = (
            cmds.animLayer(layer_node, query=True, children=True) or list()
        )
        for child_layer in child_layers:
            _add_node_recursive(child_layer)

    all_layers = list()
    root_layer = cmds.animLayer(query=True, root=True)
    if not root_layer:
        return all_layers
    _add_node_recursive(root_layer)

    if not include_base_animation:
        if "BaseAnimation" in all_layers:
            all_layers.remove("BaseAnimation")

    return all_layers


def get_layer_weights():
    """
    Gets all the animation layer weights.

    :return: Dictionary with the name of the animation layer, followed by the weight.
    :rtype: dict
    """
    anim_layer_weights = {}
    anim_layers = all_anim_layers_ordered(include_base_animation=False)

    for anim_layer in anim_layers:
        anim_layer_weights[anim_layer] = cmds.animLayer(anim_layer, query=True, weight=True)

    return anim_layer_weights


def set_layer_weights(anim_layer_weights):
    """
    Sets the animation layer weights.

    :param dict anim_layer_weights: Dictionary containing all the animation layer names, and the weights to be set for each anim layer name.
    """
    for name, weight in anim_layer_weights.items():
        cmds.animLayer(name, edit=True, weight=weight)


def set_layer_weight(name, value=1.0, toggle_other_off=False, include_base=False):
    """
    Set a specific AnimationLayers weight.

    :param str name: Name of the animation layer to have its weight modified.
    :param float value: weight of the animation layer
    :param bool toggle_other_off: Turn all other layers off
    :param bool include_base: include the base animation layer when toggling off layers.
    """
    anim_layers = all_anim_layers_ordered(include_base_animation=include_base)

    if toggle_other_off:
        for layer_name in anim_layers:
            cmds.animLayer(layer_name, edit=True, weight=0.0)

    cmds.animLayer(name, edit=True, weight=value)
    