"""Vectors functions"""

# Stdlib imports
import math

# Maya imports
from maya import OpenMaya
import pymel.core as pm


def get_distance(input1, input2):
    """Returns distance between two vectors

    Args:
        input1(MVector or PyNode.Transform or list): 3D Vector input A
        input2(MVector or PyNode.Transform or list): 3D Vector input B

    Returns:
        float: Distance value
    """

    # Return value
    distance = None
    _vector = None

    # Handles MVector case
    if (isinstance(input1, OpenMaya.MVector)
            and isinstance(input2, OpenMaya.MVector)):
        _vector = input2 - input1
    # Handles PyNodes case
    elif (isinstance(input1, pm.nodetypes.Transform)
          and isinstance(input2, pm.nodetypes.Transform)):
        vector_1 = input1.getTranslation(space="world")
        vector_2 = input2.getTranslation(space="world")
        _vector = vector_2 - vector_1
    # Handles list case
    elif isinstance(input1, list) and isinstance(input2, list):
        # Calculates distance
        return math.sqrt(sum([(vec_a - vec_b) ** 2
                              for vec_a, vec_b in zip(input1, input2)]))

    distance = _vector.length()
    return distance


def linear_interpolate(input1, input2, blend=0.5):
    """Returns 3D vector linearly interpolated between 2 vector inputs

    Args:
        input1(MVector or PyNode.Transform or list): 3D Vector input A
        input2(MVector or PyNode.Transform or list): 3D Vector input B
        blend: Ouput vector blend position.

    Returns:
        maya.OpenMaya.MVector: 3D vector interpolated position
    """

    # Return value
    vector = None

    # Handles PyNodes case
    if (isinstance(input1, pm.nodetypes.Transform)
            and isinstance(input2, pm.nodetypes.Transform)):
        input1 = input1.getTranslation()
        input2 = input2.getTranslation()
    # Handles list case
    elif isinstance(input1, list) and isinstance(input2, list):
        input1 = OpenMaya.MVector(input1[0], input1[1], input1[2])
        input2 = OpenMaya.MVector(input2[0], input2[1], input2[2])

    # Calculates interpolated vector
    vector = input2 - input1
    vector *= blend
    vector += input1

    return OpenMaya.MVector(vector[0], vector[1], vector[2])


def get_plane_normal(input1, input2, input3):
    """Returns the normal vector of a triangle (Defined by 3 positions).

    Args:
        input1(MVector or PyNode.Transform or list): 3D Vector input A
        input2(MVector or PyNode.Transform or list): 3D Vector input B
        input3(MVector or PyNode.Transform or list): 3D Vector input C

    Returns:
        maya.OpenMaya.MVector: 3D vector interpolated position
    """

    # Handles PyNodes case
    if (isinstance(input1, pm.nodetypes.Transform)
            and isinstance(input2, pm.nodetypes.Transform)
            and isinstance(input3, pm.nodetypes.Transform)):
        input1 = input1.getTranslation()
        input2 = input2.getTranslation()
        input3 = input3.getTranslation()
    # Handles list case
    elif (isinstance(input1, list) and isinstance(input2, list)
          and isinstance(input3, list)):
        input1 = OpenMaya.MVector(input1[0], input1[1], input1[2])
        input2 = OpenMaya.MVector(input2[0], input2[1], input2[2])
        input3 = OpenMaya.MVector(input3[0], input3[1], input3[2])

    # Calculates normal vector
    vector_a = input2 - input1
    vector_b = input3 - input1
    vector_a.normalize()
    vector_b.normalize()
    normal = vector_b ^ vector_a
    normal.normalize()

    return normal
