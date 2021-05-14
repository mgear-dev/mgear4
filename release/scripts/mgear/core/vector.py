"""Functions to work with vectors"""

import math

import maya.OpenMaya as OpenMaya

from pymel.core import datatypes


#############################################
# VECTOR OPERATIONS
#############################################
def getDistance(v0, v1):
    """Get the distance between 2 vectors

    Arguments:
        v0 (vector): vector A.
        v1 (vector): vector B.

    Returns:
        float: Distance length.

    """
    v = v1 - v0

    return v.length()


def getDistance2(obj0, obj1):
    """Get the distance between 2 objects.

    Arguments:
        obj0 (dagNode): Object A
        obj1 (dagNode): Object B

    Returns:
        float: Distance length

    """
    v0 = obj0.getTranslation(space="world")
    v1 = obj1.getTranslation(space="world")

    v = v1 - v0

    return v.length()


def linearlyInterpolate(v0, v1, blend=.5):
    """Get the vector interpolated between 2 vectors.

    Arguments:
        v0 (vector): vector A.
        v1 (vector): vector B.
        blend (float): Blending value.

    Returns:
        vector: The interpolated vector.

    """
    vector = v1 - v0
    vector *= blend
    vector += v0

    return vector


def getPlaneNormal(v0, v1, v2):
    """Get the normal vector of a plane (Defined by 3 positions).

    Arguments:
        v0 (vector): First position on the plane.
        v1 (vector): Second position on the plane.
        v2 (vector): Third position on the plane.

    Returns:
        vector: The normal.

    """
    vector0 = v1 - v0
    vector1 = v2 - v0
    vector0.normalize()
    vector1.normalize()

    normal = vector1 ^ vector0
    normal.normalize()

    return normal


def getPlaneBiNormal(v0, v1, v2):
    """Get the binormal vector of a plane (Defined by 3 positions).

    Arguments:
        v0 (vector): First position on the plane.
        v1 (vector): Second position on the plane.
        v2 (vector): Third position on the plane.

    Returns:
        vector: The binormal.

    """
    normal = getPlaneNormal(v0, v1, v2)

    vector0 = v1 - v0

    binormal = normal ^ vector0
    binormal.normalize()

    return binormal


def getTransposedVector(v, position0, position1, inverse=False):
    """Get the transposed vector.

    Arguments:
        v (vector): Input Vector.
        position0 (vector): Position A.
        position1 (vector): Position B.
        inverse (bool): Invert the rotation.

    Returns:
        vector: The transposed vector.

    >>> normal = vec.getTransposedVector(self.normal,
                                         [self.guide.apos[0],
                                          self.guide.apos[1]],
                                         [self.guide.apos[-2],
                                          self.guide.apos[-1]])

    """
    v0 = position0[1] - position0[0]
    v0.normalize()

    v1 = position1[1] - position1[0]
    v1.normalize()

    ra = v0.angle(v1)

    if inverse:
        ra = -ra

    axis = v0 ^ v1

    vector = rotateAlongAxis(v, axis, ra)

    # Check if the rotation has been set in the right order
    # ra2 = (math.pi *.5 ) - v1.angle(vector)
    # vector = rotateAlongAxis(v, axis, -ra2)

    return vector


def rotateAlongAxis(v, axis, a):
    """Rotate a vector around a given axis defined by other vector.

    Arguments:
        v (vector): The vector to rotate.
        axis (vector): The axis to rotate around.
        a (float): The rotation angle in radians.

    """
    sa = math.sin(a / 2.0)
    ca = math.cos(a / 2.0)

    q1 = OpenMaya.MQuaternion(v.x, v.y, v.z, 0)
    q2 = OpenMaya.MQuaternion(axis.x * sa, axis.y * sa, axis.z * sa, ca)
    q2n = OpenMaya.MQuaternion(-axis.x * sa, -axis.y * sa, -axis.z * sa, ca)
    q = q2 * q1
    q *= q2n

    out = OpenMaya.MVector(q.x, q.y, q.z)

    return out


##########################################################
# CLASS
##########################################################
class Blade(object):
    """The Blade object for shifter guides"""

    def __init__(self, t=datatypes.Matrix()):

        self.transform = t

        d = [t.data[j][i]
             for j in range(len(t.data))
             for i in range(len(t.data[0]))]

        m = OpenMaya.MMatrix()
        OpenMaya.MScriptUtil.createMatrixFromList(d, m)
        m = OpenMaya.MTransformationMatrix(m)

        x = OpenMaya.MVector(1, 0, 0).rotateBy(m.rotation())
        y = OpenMaya.MVector(0, 1, 0).rotateBy(m.rotation())
        z = OpenMaya.MVector(0, 0, 1).rotateBy(m.rotation())

        self.x = datatypes.Vector(x.x, x.y, x.z)
        self.y = datatypes.Vector(y.x, y.y, y.z)
        self.z = datatypes.Vector(z.x, z.y, z.z)
