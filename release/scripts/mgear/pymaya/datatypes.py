import math
from maya.api import OpenMaya


EulerRotation = OpenMaya.MEulerRotation
Quaternion = OpenMaya.MQuaternion
degrees = math.degrees


def _warp_dt(func):
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        if isinstance(res, OpenMaya.MVector):
            return Vector(res)
        elif isinstance(res, OpenMaya.MPoint):
            return Point(res)
        elif isinstance(res, OpenMaya.MMatrix):
            return Matrix(res)
        elif isinstance(res, OpenMaya.MTransformationMatrix):
            return TransformationMatrix(res)
        else:
            return res

    return wrapper


class Vector(OpenMaya.MVector):
    WRAP_FUNCS = []
    for fn in dir(OpenMaya.MVector):
        if not fn.startswith("_"):
            f = getattr(OpenMaya.MVector, fn)
            if callable(f):
                WRAP_FUNCS.append(fn)

    def __init__(self, *args, **kwargs):
        super(Vector, self).__init__(*args, **kwargs)
        for fn in Vector.WRAP_FUNCS:
            setattr(self, fn, _warp_dt(super(Vector, self).__getattribute__(fn)))

    def __getitem__(self, item):
        return [self.x, self.y, self.z][item]


class Point(OpenMaya.MPoint):
    WRAP_FUNCS = []
    for fn in dir(OpenMaya.MPoint):
        if not fn.startswith("_"):
            f = getattr(OpenMaya.MPoint, fn)
            if callable(f):
                WRAP_FUNCS.append(fn)

    def __init__(self, *args, **kwargs):
        super(Point, self).__init__(*args, **kwargs)
        for fn in Point.WRAP_FUNCS:
            setattr(self, fn, _warp_dt(super(Point, self).__getattribute__(fn)))

    def __getitem__(self, item):
        return [self.x, self.y, self.z, self.w][item]


class Matrix(OpenMaya.MMatrix):
    WRAP_FUNCS = []
    for fn in dir(OpenMaya.MMatrix):
        if not fn.startswith("_"):
            f = getattr(OpenMaya.MMatrix, fn)
            if callable(f):
                WRAP_FUNCS.append(fn)

    def __init__(self, *args, **kwargs):
        super(Matrix, self).__init__(*args, **kwargs)
        for fn in Matrix.WRAP_FUNCS:
            setattr(self, fn, _warp_dt(super(Matrix, self).__getattribute__(fn)))

    def get(self):
        return ((self[0], self[1], self[2], self[3]),
                (self[4], self[5], self[6], self[7]),
                (self[8], self[9], self[10], self[11]),
                (self[12], self[13], self[14], self[15]))


class TransformationMatrix(OpenMaya.MTransformationMatrix):
    WRAP_FUNCS = []
    for fn in dir(OpenMaya.MTransformationMatrix):
        if not fn.startswith("_"):
            f = getattr(OpenMaya.MTransformationMatrix, fn)
            if callable(f):
                WRAP_FUNCS.append(fn)

    def __init__(self, *args, **kwargs):
        super(TransformationMatrix, self).__init__(*args, **kwargs)
        for fn in TransformationMatrix.WRAP_FUNCS:
            setattr(self, fn, _warp_dt(super(TransformationMatrix, self).__getattribute__(fn)))

    def get(self):
        return self.asMatrix().get()


__all__ = ["Vector", "EulerRotation", "Matrix", "TransformationMatrix", "Quaternion", "degrees", "Point"]
