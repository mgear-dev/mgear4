import pymel.core as pm


def find_connected_proximity_pin_node(source_object):
    """
    Check if the worldMesh[0] output of an object is connected to the
    deformedGeometry of a proximityPin node. Return the proximityPin node as
    a PyNode if found.

    Args:
        source_object (pyNode or str): Name of the source object.

    Returns:
        pymel.core.general.PyNode: The connected proximityPin node as a PyNode
            if a connection exists, otherwise None.
    """
    # Get the source worldMesh[0] plug as PyNode
    if isinstance(source_object, str):
        source_object = pm.PyNode(source_object)
    source_plug = source_object.worldMesh[0]

    # Find all destination connections from this plug
    connections = source_plug.connections(d=True, s=False, p=True)

    # Check each connection to see if it is to a proximityPin node
    for connection in connections:
        # The node connected to
        node = connection.node()
        # Check if this node is of the type 'proximityPin'
        if node.type() == "proximityPin":
            # Check if the connected attribute is deformedGeometry
            if "deformedGeometry" in connection.name():
                return node

    return None
