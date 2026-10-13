"""Shared helpers of the facial geometry solvers. Creates nothing."""

from maya import cmds

from mgear.core import meshNavigation


def world_up():
    """Get the scene up axis.

    Returns:
        tuple: (0, 1, 0), or (0, 0, 1) in a Z up scene.
    """
    if cmds.upAxis(query=True, axis=True) == "z":
        return (0.0, 0.0, 1.0)
    return (0.0, 1.0, 0.0)


def world_front():
    """Get the direction a character faces in the scene.

    Returns:
        tuple: (0, 0, 1), or (0, -1, 0) in a Z up scene.
    """
    if cmds.upAxis(query=True, axis=True) == "z":
        return (0.0, -1.0, 0.0)
    return (0.0, 0.0, 1.0)


def single_vertex(text, mesh, label, owner="eyelid"):
    """Get the index of a one vertex component string.

    Args:
        text (str): Component string, e.g. "head.vtx[12]".
        mesh (str): Mesh the vertex must be on.
        label (str): Readable name of the vertex, for the errors.
        owner (str, optional): Readable name of the rig part, for the errors.

    Returns:
        int: The vertex index.

    Raises:
        ValueError: If the string is not one vertex of the mesh.
    """
    vertex_mesh, kind, indices = meshNavigation.parse_component_string(text)
    if kind != "vertex" or len(indices) != 1:
        raise ValueError("Set the {} vertex".format(label))
    if vertex_mesh.split("|")[-1] != mesh.split("|")[-1]:
        raise ValueError(
            "The {} vertex is not on the {} mesh {}".format(label, owner, mesh)
        )
    return indices[0]
