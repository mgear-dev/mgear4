import math
from maya.api import OpenMaya


EulerRotation = OpenMaya.MEulerRotation
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


class Matrix(OpenMaya.MMatrix):
    def __init__(self, *args, **kwargs):
        super(Matrix, self).__init__(*args, **kwargs)

    def get(self):
        return ((self[0], self[1], self[2], self[3]),
                (self[4], self[5], self[6], self[7]),
                (self[8], self[9], self[10], self[11]),
                (self[12], self[13], self[14], self[15]))


class TransformationMatrix(OpenMaya.MTransformationMatrix):
    def __init__(self, *args, **kwargs):
        super(TransformationMatrix, self).__init__(*args, **kwargs)

    def asMatrix(self):
        return Matrix(super(TransformationMatrix, self).asMatrix())

    def get(self):
        return self.asMatrix().get()


__all__ = ["Vector", "EulerRotation", "Matrix", "TransformationMatrix", "Quaternion", "degrees", "Point"]
