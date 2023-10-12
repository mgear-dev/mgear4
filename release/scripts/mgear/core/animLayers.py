import maya.cmds as cmds
import maya.api.OpenMaya as om

def animation_layer_exists(layer_name):
    is_anim_layer = False

    if not layer_name:
        return False
    exists = cmds.objExists(layer_name)

    if exists:
        is_anim_layer = cmds.nodeType(layer_name) == "animLayer"

    return exists and is_anim_layer


def base_animation_layer_name():
    if animation_layer_exists("BaseAnimation"):
        return "BaseAnimation"

    # BaseAnimation Layer might have been renamed, perform dg lookup.
    nodes = find_anim_layer_base_nodes()

    # No nodes found
    if len(nodes) == 0:
        return ""
    return om.MFnDependencyNode(nodes[0]).name()


def find_anim_layer_base_nodes():
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

    Returns:
            list[str]: list of animation layers.
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