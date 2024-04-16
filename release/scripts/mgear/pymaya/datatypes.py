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
        if len(args) == 1:
            args = list(args)
            if isinstance(args[0], (list, tuple)) and len(args[0]) == 1:
                l = list(args[0])
                args[0] = l * 3
            elif isinstance(args[0], (int, float)):
                args[0] = [args[0]] * 3

        super(Vector, self).__init__(*args, **kwargs)
        for fn in Vector.WRAP_FUNCS:
            setattr(self, fn, _warp_dt(super(Vector, self).__getattribute__(fn)))

    def __getitem__(self, item):
        return [self.x, self.y, self.z][item]

    def rotateBy(self, *args):
        if args:
            if len(args) == 2 and isinstance(args[0], Vector):
                return Vector(super(Vector, self).rotateBy(Quaternion(float(args[1]), args[0])))
            elif len(args) == 1 and isinstance(args[0], Matrix):
                return Vector(super(Vector, self).rotateBy(TransformationMatrix(args[0]).rotation(True)))
            else:
                return Vector(super(Vector, self).rotateBy(EulerRotation(*args)))
        else:
            return self


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


class BoundingBox(OpenMaya.MBoundingBox):
    WRAP_FUNCS = []
    for fn in dir(OpenMaya.MBoundingBox):
        if not fn.startswith("_"):
            f = getattr(OpenMaya.MBoundingBox, fn)
            if callable(f):
                WRAP_FUNCS.append(fn)

    def __init__(self, *args, **kwargs):
        nargs = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                arg = Point(arg)
            nargs.append(arg)

        super(BoundingBox, self).__init__(*nargs, **kwargs)
        for fn in BoundingBox.WRAP_FUNCS:
            setattr(self, fn, _warp_dt(super(BoundingBox, self).__getattribute__(fn)))

    def __getitem__(self, index):
        if index == 0:
            return Point(self.min)
        elif index == 1:
            return Point(self.max)
        else:
            raise Exception("Index out of range")


__all__ = ["Vector", "EulerRotation", "Matrix", "TransformationMatrix", "Quaternion", "degrees", "Point", "BoundingBox"]
