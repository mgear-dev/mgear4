import math
from maya.api import OpenMaya


Vector = OpenMaya.MVector
EulerRotation = OpenMaya.MEulerRotation
Matrix = OpenMaya.MMatrix
TransformationMatrix = OpenMaya.MTransformationMatrix
Quaternion = OpenMaya.MQuaternion
degrees = math.degrees
Point = OpenMaya.MPoint


__all__ = ["Vector", "EulerRotation", "Matrix", "TransformationMatrix", "Quaternion", "degrees", "Point"]
