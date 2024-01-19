import math
from maya.api import OpenMaya


EulerRotation = OpenMaya.MEulerRotation
Matrix = OpenMaya.MMatrix
TransformationMatrix = OpenMaya.MTransformationMatrix
Quaternion = OpenMaya.MQuaternion
degrees = math.degrees


class Vector(OpenMaya.MVector):
    def __init__(self, *args, **kwargs):
        super(Vector, self).__init__(*args, **kwargs)

    def __getitem__(self, item):
        return [self.x, self.y, self.z][item]


class Point(OpenMaya.MPoint):
    def __init__(self, *args, **kwargs):
        super(Point, self).__init__(*args, **kwargs)

    def __getitem__(self, item):
        return [self.x, self.y, self.z, self.w][item]


__all__ = ["Vector", "EulerRotation", "Matrix", "TransformationMatrix", "Quaternion", "degrees", "Point"]
