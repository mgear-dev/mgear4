import pymel.core as pm


def is_deformer(node):
    """ check if the node is from a deformer type

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
