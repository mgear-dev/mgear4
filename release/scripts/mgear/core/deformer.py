import pymel.core as pm


def is_deformer(node):
    """check if the node is from a deformer type

    Args:
        node (TYPE): node to check

    Returns:
        TYPE: bool
    """
    deformer_types = set(
        [
            "skinCluster",
            "blendShape",
            "nonLinear",
            "ffd",
            "cluster",
            "sculpt",
            "wire",
            "wrap",
            "jiggle",
            "deltaMush",
            "softMod",
            "morph",
        ]
    )
    node_type = pm.nodeType(node)
    return node_type in deformer_types


def filter_deformers(node_list):
    """Filter the list of nodes to only return the deformers

    Args:
        node_list (list): list of pyNode

    Returns:
        TYPE: filtered list of pyNode
    """
    deformer_list = []
    for node in node_list:
        if is_deformer(node):
            deformer_list.append(node)
    return deformer_list


def create_cluster_on_curve(curve, control_points=None):
    """
    Create a cluster deformer on a given curve at specified control points.

    Args:
        curve (str or PyNode): The name or PyNode of the curve to apply
            the cluster deformer.
        control_points (list of int, optional): List of control point
            indices to affect. Applies to all if None. Default is None.

    Returns:
        tuple: The name of the cluster and the name of the cluster handle.
    """
    # Check if curve is a PyNode, if not make it one
    if not isinstance(curve, pm.nt.Transform):
        curve = pm.PyNode(curve)

    # If control_points is None, apply cluster to the entire curve
    if control_points is None:
        cluster_node, cluster_handle = pm.cluster(curve)
    else:
        # Generate list representing the control points on the curve
        control_points_list = [
            "{}.cv[{}]".format(curve, i) for i in control_points
        ]

        # Convert list to PyNode objects
        control_points_pynodes = [pm.PyNode(cp) for cp in control_points_list]

        # Create the cluster deformer
        cluster_node, cluster_handle = pm.cluster(control_points_pynodes)

    return cluster_node, cluster_handle
