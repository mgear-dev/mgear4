"""Functions to create mesh topology"""

#############################################
# GLOBAL
#############################################

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import pymel.core as pm


def create_square_polygon(
    side_length=1.0, alignment="Y", name=None, position=(0, 0, 0)
):
    """
    Creates a square polygon face with its normal aligned along a specified
    world axis and positions it at a given 3D location.

    Args:
        side_length (float, optional): The length of each side of the square.
            Defaults to 1.0.
        alignment (str, optional): The world axis ('X', 'Y', 'Z') along which
            the square's normal will be aligned. Defaults to 'Y'.
        name (str, optional): The name of the new polygon object. If None,
            Maya will assign a default name.
        position (tuple, optional): The 3D position (x, y, z) where the square
            will be placed. Defaults to (0, 0, 0).

    Returns:
        str: The full name of the newly created polygon object.
    """
    half_length = side_length * 0.5
    points = om2.MPointArray()

    # Adjust vertex definitions based on alignment to ensure correct normal direction
    if alignment.upper() == "X":
        # Normal along X-axis
        base_points = [
            om2.MPoint(0, half_length, half_length),
            om2.MPoint(0, -half_length, half_length),
            om2.MPoint(0, -half_length, -half_length),
            om2.MPoint(0, half_length, -half_length),
        ]
    elif alignment.upper() == "Y":
        # Normal along Y-axis
        base_points = [
            om2.MPoint(-half_length, 0, half_length),
            om2.MPoint(half_length, 0, half_length),
            om2.MPoint(half_length, 0, -half_length),
            om2.MPoint(-half_length, 0, -half_length),
        ]
    else:  # Z alignment
        # Normal along Z-axis
        base_points = [
            om2.MPoint(-half_length, half_length, 0),
            om2.MPoint(half_length, half_length, 0),
            om2.MPoint(half_length, -half_length, 0),
            om2.MPoint(-half_length, -half_length, 0),
        ]

    # Apply position offset and append to MPointArray
    for pt in base_points:
        pt.x += position[0]
        pt.y += position[1]
        pt.z += position[2]
        points.append(pt)

    # Create mesh
    mesh_fn = om2.MFnMesh()
    new_mesh = mesh_fn.create(points, [4], [0, 1, 2, 3])

    # Get the transform node of the created mesh
    new_mesh_name = mesh_fn.fullPathName()
    transform_node = cmds.listRelatives(new_mesh_name, parent=True)[0]

    # Rename if name is provided
    if name:
        transform_node = cmds.rename(transform_node, name)

    # Apply default shader (lambert1) to the new object
    # Directly use the initialShadingGroup which is the default for lambert1
    shading_group = "initialShadingGroup"
    cmds.sets(transform_node, edit=True, forceElement=shading_group)

    transform_node = pm.PyNode(transform_node)
    return transform_node


if __name__ == "__main__":

    create_square_polygon(
        side_length=0.5, alignment="Y", name=None, position=(0, 5, 0)
    )
