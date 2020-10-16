"""Vectors functions"""

# Stdlib imports
import math

# Maya imports
from maya import OpenMaya
import pymel.core as pm


def get_distance(input1, input2):
    """Returns distance between two vectors

    Args:
        input1: MVector or PyNode.Transform or list
        input2: MVector or PyNode.Transform or list

    Returns:
        float: Distance value
    """

    # Return value
    distance = None

    # Handles MVector case
    if type(input1) and type(input2) == OpenMaya.MVector:
        distance = input2 - input1
    # Handles PyNode case
    if type(input1) and type(input2) == pm.nodetypes.Transform:
        vector_1 = input1.getTranslation(space="world")
        vector_2 = input2.getTranslation(space="world")
        distance = vector_2 - vector_1
    # Handles list case
    if type(input1) and type(input2) == list:
        distance = math.sqrt(sum([(vec_a - vec_b) ** 2
                                  for vec_a, vec_b in zip(input1, input2)]))

    return distance
