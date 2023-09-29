"""Functions to work with matrix and transformations"""

import math

from pymel import util
import pymel.core as pm
from pymel.core import datatypes
from pymel.core import nodetypes

from mgear.core import vector

import maya.OpenMaya as om
import maya.OpenMayaUI as omui

#############################################
# TRANSFORM
#############################################


def getTranslation(node):
    """Return the position of the dagNode in worldSpace.

    Arguments:
        node (dagNode): The dagNode to get the translation

    Returns:
        matrix: The transformation matrix
    """
    return node.getTranslation(space="world")


def getTransform(node):
    """Return the transformation matrix of the dagNode in worldSpace.

    Arguments:
        node (dagNode): The dagNode to get the translation

    Returns:
        matrix: The transformation matrix
    """
    return node.getMatrix(worldSpace=True)


def getTransformLookingAt(pos, lookat, normal, axis="xy", negate=False):
    """Return a transformation mstrix using vector positions.

    Return the transformation matrix of the dagNode oriented looking to
    an specific point.

    Arguments:
        pos (vector): The position for the transformation
        lookat (vector): The aiming position to stablish the orientation
        normal (vector): The normal control the transformation roll.
        axis (str): The 2 axis used for lookat and normal. Default "xy"
        negate (bool): If true, invert the aiming direction.

    Returns:
        matrix: The transformation matrix

    >>>  t = tra.getTransformLookingAt(self.guide.pos["heel"],
                                       self.guide.apos[-4],
                                       self.normal,
                                       "xz",
                                       self.negate)

    """
    normal.normalize()

    if negate:
        a = pos - lookat
    else:
        a = lookat - pos

    a.normalize()
    c = util.cross(a, normal)
    c.normalize()
    b = util.cross(c, a)
    b.normalize()

    if axis == "xy":
        X = a
        Y = b
        Z = c
    elif axis == "xz":
        X = a
        Z = b
        Y = -c
    elif axis == "x-z":
        X = a
        Z = -b
        Y = c
    elif axis == "yx":
        Y = a
        X = b
        Z = -c
    elif axis == "-yx":
        Y = -a
        X = b
        Z = -c
    elif axis == "y-x":
        Y = a
        X = -b
        Z = -c
    elif axis == "yz":
        Y = a
        Z = b
        X = c
    elif axis == "-yz":
        Y = -a
        Z = b
        X = -c
    elif axis == "y-z":
        Y = a
        Z = -b
        X = c
    elif axis == "zx":
        Z = a
        X = b
        Y = c
    elif axis == "-zx":
        Z = -a
        X = b
        Y = -c
    elif axis == "z-x":
        Z = a
        X = -b
        Y = -c
    elif axis == "zy":
        Z = a
        Y = b
        X = -c
    elif axis == "-zy":
        Z = -a
        Y = b
        X = -c
    elif axis == "x-y":
        X = a
        Y = -b
        Z = -c
    elif axis == "-xz":
        X = -a
        Z = b
        Y = c
    elif axis == "-xy":
        X = -a
        Y = b
        Z = -c

    m = datatypes.Matrix()
    m[0] = [X[0], X[1], X[2], 0.0]
    m[1] = [Y[0], Y[1], Y[2], 0.0]
    m[2] = [Z[0], Z[1], Z[2], 0.0]
    m[3] = [pos[0], pos[1], pos[2], 1.0]

    return m


def getChainTransform(positions, normal, negate=False, axis="xz"):
    """Get a tranformation list from a positions list and normal.

    Arguments:
        positions(list of vector): List with the chain positions.
        normal (vector): Normal direction.
        negate (bool): If true invert the chain orientation.

    returns:
        list of matrix: The list containing the transformation matrix
            for the chain.

    >>> tra.getChainTransform(self.guide.apos, self.normal, self.negate)

    """
    # Draw
    transforms = []
    for i in range(len(positions) - 1):
        v0 = positions[i - 1]
        v1 = positions[i]
        v2 = positions[i + 1]

        # Normal Offset
        if i > 0:
            normal = vector.getTransposedVector(
                normal, [v0, v1], [v1, v2])

        t = getTransformLookingAt(v1, v2, normal, axis, negate)
        transforms.append(t)

    return transforms


def getChainTransform2(positions, normal, negate=False, axis="xz"):
    """Get a tranformation list from a positions list and normal.

    Note:
        getChainTransform2 is using the latest position on the chain

    Arguments:
        positions(list of vector): List with the chain positions.
        normal (vector): Normal direction.
        negate (bool): If true invert the chain orientation.

    returns:
        list of matrix: The list containing the transformation matrix
            for the chain.

    >>> tra.getChainTransform2(self.guide.apos,
                               self.normal,
                               self.negate)

    """
    # Draw
    transforms = []
    for i in range(len(positions)):
        if i == len(positions) - 1:
            v0 = positions[i - 1]
            v1 = positions[i]
            v2 = positions[i - 2]

        else:
            v0 = positions[i - 1]
            v1 = positions[i]
            v2 = positions[i + 1]

        # Normal Offset
        if i > 0 and i != len(positions) - 1:
            normal = vector.getTransposedVector(
                normal, [v0, v1], [v1, v2])

        if i == len(positions) - 1:
            t = getTransformLookingAt(v1, v0, normal, "-{}".format(axis), negate)
        else:
            t = getTransformLookingAt(v1, v2, normal, axis, negate)
        transforms.append(t)

    return transforms


def getTransformFromPos(pos):
    """Create a transformation Matrix from a given position.

    Arguments:
        pos (vector): Position for the transformation matrix

    Returns:
        matrix: The newly created transformation matrix

    >>>  t = tra.getTransformFromPos(self.guide.pos["root"])

    """
    m = datatypes.Matrix()
    m[0] = [1.0, 0, 0, 0.0]
    m[1] = [0, 1.0, 0, 0.0]
    m[2] = [0, 0, 1.0, 0.0]
    m[3] = [pos[0], pos[1], pos[2], 1.0]

    return m


def getOffsetPosition(node, offset=[0, 0, 0]):
    """Get an offset position from dagNode

    Arguments:
        node (dagNode): The dagNode with the original position.
        offset (list of float): Ofsset values for xyz.
            exp : [1.2, 4.6, 32.78]

    Returns:
        list of float: the new offset position.

    Example:
        .. code-block:: python

            self.root = self.addRoot()
            vTemp = tra.getOffsetPosition( self.root, [0,-3,0.1])
            self.knee = self.addLoc("knee", self.root, vTemp)

    """
    offsetVec = datatypes.Vector(offset[0], offset[1], offset[2])
    return offsetVec + node.getTranslation(space="world")


def getPositionFromMatrix(in_m):
    """Get the position values from matrix

    Arguments:
        in_m (matrix): The input Matrix.

    Returns:
        list of float: The position values for xyz.

    """
    pos = in_m[3][:3]

    return pos


def setMatrixPosition(in_m, pos):
    """Set the position for a given matrix

    Arguments:
        in_m (matrix): The input Matrix.
        pos (list of float): The position values for xyz

    Returns:
        matrix: The matrix with the new position

    >>> tnpo = tra.setMatrixPosition(tOld, tra.getPositionFromMatrix(t))

    >>> t = tra.setMatrixPosition(t, self.guide.apos[-1])

    """
    m = datatypes.Matrix()
    m[0] = in_m[0]
    m[1] = in_m[1]
    m[2] = in_m[2]
    m[3] = [pos[0], pos[1], pos[2], 1.0]

    return m


def setMatrixRotation(m, rot):
    """Set the rotation for a given matrix

    Arguments:
        in_m (matrix): The input Matrix.
        rot (list of float): The rotation values for xyz

    Returns:
        matrix: The matrix with the new rotation

    """
    X = rot[0]
    Y = rot[1]
    Z = rot[2]

    m[0] = [X[0], X[1], X[2], 0.0]
    m[1] = [Y[0], Y[1], Y[2], 0.0]
    m[2] = [Z[0], Z[1], Z[2], 0.0]

    return m


def setMatrixScale(m, scl=[1, 1, 1]):
    """Set the scale for a given matrix

    Arguments:
        in_m (matrix): The input Matrix.
        scl (list of float): The scale values for xyz

    Returns:
        matrix: The matrix with the new scale

    """
    tm = datatypes.TransformationMatrix(m)
    tm.setScale(scl, space="world")
    # Ensure that shear is not propagated
    # This can cause intermediated transform in the jnt structure
    tm.setShear([0, 0, 0], space="world")

    m = datatypes.Matrix(tm)

    return m


def getFilteredTransform(m,
                         translation=True,
                         rotation=True,
                         scaling=True):
    """Retrieve a transformation filtered.

    Arguments:
        m (matrix): the reference matrix
        translation (bool): If true the return matrix will match the
            translation.
        rotation (bool): If true the return matrix will match the
            rotation.
        scaling (bool): If true the return matrix will match the
            scaling.

    Returns:
        matrix : The filtered matrix

    """

    t = datatypes.Vector(m[3][0], m[3][1], m[3][2])
    x = datatypes.Vector(m[0][0], m[0][1], m[0][2])
    y = datatypes.Vector(m[1][0], m[1][1], m[1][2])
    z = datatypes.Vector(m[2][0], m[2][1], m[2][2])

    out = datatypes.Matrix()

    if translation:
        out = setMatrixPosition(out, t)

    if rotation and scaling:
        out = setMatrixRotation(out, [x, y, z])
    elif rotation and not scaling:
        out = setMatrixRotation(out, [x.normal(), y.normal(), z.normal()])
    elif not rotation and scaling:
        out = setMatrixRotation(out,
                                [datatypes.Vector(1, 0, 0)
                                 * x.length(), datatypes.Vector(0, 1, 0)
                                 * y.length(), datatypes.Vector(0, 0, 1)
                                 * z.length()])

    return out

##########################################################
# ROTATION
##########################################################


def getRotationFromAxis(in_a, in_b, axis="xy", negate=False):
    """Get the matrix rotation from a given axis.

    Arguments:
        in_a (vector): Axis A
        in_b (vector): Axis B
        axis (str): The axis to use for the orientation. Default: "xy"
        negate (bool): negates the axis orientation.

    Returns:
        matrix: The newly created matrix.

    Example:
        .. code-block:: python

            x = datatypes.Vector(0,-1,0)
            x = x * tra.getTransform(self.eff_loc)
            z = datatypes.Vector(self.normal.x,
                                 self.normal.y,
                                 self.normal.z)
            z = z * tra.getTransform(self.eff_loc)
            m = tra.getRotationFromAxis(x, z, "xz", self.negate)

    """
    a = datatypes.Vector(in_a.x, in_a.y, in_a.z)
    b = datatypes.Vector(in_b.x, in_b.y, in_b.z)
    c = datatypes.Vector()

    if negate:
        a *= -1

    a.normalize()
    c = a ^ b
    c.normalize()
    b = c ^ a
    b.normalize()

    if axis == "xy":
        x = a
        y = b
        z = c
    elif axis == "xz":
        x = a
        z = b
        y = -c
    elif axis == "yx":
        y = a
        x = b
        z = -c
    elif axis == "yz":
        y = a
        z = b
        x = c
    elif axis == "zx":
        z = a
        x = b
        y = c
    elif axis == "zy":
        z = a
        y = b
        x = -c

    m = datatypes.Matrix()
    setMatrixRotation(m, [x, y, z])

    return m


def getSymmetricalTransform(t, axis="yz", fNegScale=False):
    """Get the symmetrical tranformation

    Get the symmetrical tranformation matrix from a define 2 axis mirror
    plane. exp:"yz".

    Arguments:
        t (matrix): The transformation matrix to mirror.
        axis (str): The mirror plane.
        fNegScale(bool):  This function is not yet implemented.

    Returns:
        matrix: The symmetrical tranformation matrix.
    """

    if axis == "yz":
        mirror = datatypes.TransformationMatrix(-1, 0, 0, 0,
                                                0, 1, 0, 0,
                                                0, 0, 1, 0,
                                                0, 0, 0, 1)

    if axis == "xy":
        mirror = datatypes.TransformationMatrix(1, 0, 0, 0,
                                                0, 1, 0, 0,
                                                0, 0, -1, 0,
                                                0, 0, 0, 1)
    if axis == "zx":
        mirror = datatypes.TransformationMatrix(1, 0, 0, 0,
                                                0, -1, 0, 0,
                                                0, 0, 1, 0,
                                                0, 0, 0, 1)
    t *= mirror

    # TODO: add freeze negative scaling procedure.

    return t


def resetTransform(node, t=True, r=True, s=True):
    """Reset the scale, rotation and translation for a given dagNode.

    Arguments:
        node(dagNode): The object to reset the transforms.
        t (bool): If true translation will be reseted.
        r (bool): If true rotation will be reseted.
        s (bool): If true scale will be reseted.

    Returns:
        None

    """
    trsDic = {"tx": 0,
              "ty": 0,
              "tz": 0,
              "rx": 0,
              "ry": 0,
              "rz": 0,
              "sx": 1,
              "sy": 1,
              "sz": 1}

    tAxis = ["tx", "ty", "tz"]
    rAxis = ["rx", "ry", "rz"]
    sAxis = ["sx", "sy", "sz"]
    axis = []

    if t:
        axis = axis + tAxis
    if r:
        axis = axis + rAxis
    if s:
        axis = axis + sAxis

    for a in axis:
        try:
            node.attr(a).set(trsDic[a])
        except Exception:
            pass


def matchWorldTransform(source, target):
    """Match 2 dagNode transformations in world space.

    Arguments:
        source (dagNode): The source dagNode
        target (dagNode): The target dagNode

    Returns:
        None

    """
    sWM = source.getMatrix(worldSpace=True)
    target.setMatrix(sWM, worldSpace=True)


def quaternionDotProd(q1, q2):
    """Get the dot product of 2 quaternion.

    Arguments:
        q1 (quaternion): Input quaternion 1.
        q2 (quaternion): Input quaternion 2.

    Returns:
        quaternion: The dot proct quaternion.

    """
    dot = q1.x * q2.x + q1.y * q2.y + q1.z * q2.z + q1.w * q2.w
    return dot


def quaternionSlerp(q1, q2, blend):
    """Get an interpolate quaternion based in slerp function.

    Arguments:
        q1 (quaternion): Input quaternion 1.
        q2 (quaternion): Input quaternion 2.
        blend (float): Blending value.

    Returns:
        quaternion: The interpolated quaternion.

    Example:
        .. code-block:: python

            q = quaternionSlerp(datatypes.Quaternion(
                                t1.getRotationQuaternion()),
                                datatypes.Quaternion(
                                    t2.getRotationQuaternion()), blend)

    """
    dot = quaternionDotProd(q1, q2)
    if dot < 0.0:
        dot = quaternionDotProd(q1, q2.negateIt())

    arcos = math.acos(round(dot, 10))
    sin = math.sin(arcos)

    if sin > 0.001:
        w1 = math.sin((1.0 - blend) * arcos) / sin
        w2 = math.sin(blend * arcos) / sin
    else:
        w1 = 1.0 - blend
        w2 = blend

    result = (datatypes.Quaternion(q1).scaleIt(w1)
              + datatypes.Quaternion(q2).scaleIt(w2))

    return result


def convert2TransformMatrix(tm):
    """Convert a transformation Matrix

    Convert a transformation Matrix or a matrix to a transformation
    matrix in world space.

    Arguments:
        tm (matrix): The input matrix.

    Returns:
        matrix: The transformation matrix in worldSpace

    """
    if isinstance(tm, nodetypes.Transform):
        tm = datatypes.TransformationMatrix(tm.getMatrix(worldSpace=True))
    if isinstance(tm, datatypes.Matrix):
        tm = datatypes.TransformationMatrix(tm)

    return tm


def getInterpolateTransformMatrix(t1, t2, blend=.5):
    """Interpolate 2 matrix.

    Arguments:
        t1 (matrix): Input matrix 1.
        t2 (matrix): Input matrix 2.
        blend (float): The blending value. Default 0.5

    Returns:
        matrix: The newly interpolated transformation matrix.

    >>> t = tra.getInterpolateTransformMatrix(self.fk_ctl[0],
                                              self.tws1A_npo,
                                              .3333)

    """
    # check if the input transforms are transformMatrix
    t1 = convert2TransformMatrix(t1)
    t2 = convert2TransformMatrix(t2)

    if (blend == 1.0):
        return t2
    elif (blend == 0.0):
        return t1

    # translate
    pos = vector.linearlyInterpolate(t1.getTranslation(space="world"),
                                     t2.getTranslation(space="world"),
                                     blend)

    # scale
    scaleA = datatypes.Vector(*t1.getScale(space="world"))
    scaleB = datatypes.Vector(*t2.getScale(space="world"))

    vs = vector.linearlyInterpolate(scaleA, scaleB, blend)

    # rotate
    q = quaternionSlerp(datatypes.Quaternion(t1.getRotationQuaternion()),
                        datatypes.Quaternion(t2.getRotationQuaternion()),
                        blend)

    # out
    result = datatypes.TransformationMatrix()

    result.setTranslation(pos, space="world")
    result.setRotationQuaternion(q.x, q.y, q.z, q.w)
    result.setScale([vs.x, vs.y, vs.z], space="world")

    return result


def interpolate_rotation(obj, targets, blends):
    rot = [0, 0, 0]
    for t, b in zip(targets, blends):
        rot[0] += t.rx.get() * b
        rot[1] += t.ry.get() * b
        rot[2] += t.rz.get() * b

    obj.rotate.set(rot)


def interpolate_scale(obj, targets, blends):
    rot = [0, 0, 0]
    for t, b in zip(targets, blends):
        rot[0] += t.sx.get() * b
        rot[1] += t.sy.get() * b
        rot[2] += t.sz.get() * b

    obj.scale.set(rot)


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


# TODO: Maybe better just return a list of the closes ordered trasform?
def get_closes_transform(target_transform, source_transforms):
    """Summary

    Args:
        target_transform (dagNode): target transform
        source_transforms ([dagNode]): objects to check distance

    Returns:
        list: ordered transform list
    """
    distances = {}
    for t in source_transforms:
        dist = getDistance2(t, target_transform)
        distances[t.name()] = [t, dist]
    sorted_dist = sorted(distances.items(), key=lambda kv: kv[1][1])

    return sorted_dist


def getClosestPolygonFromTransform(geo, loc):
    """Get closest polygon from transform

    Arguments:
        geo (dagNode): Mesh object
        loc (matrix): location transform

    Returns:
        Closest Polygon

    """
    if isinstance(loc, pm.nodetypes.Transform):
        pos = loc.getTranslation(space='world')
    else:
        pos = datatypes.Vector(loc[0], loc[1], loc[2])

    nodeDagPath = om.MObject()
    try:
        selectionList = om.MSelectionList()
        selectionList.add(geo.name())
        nodeDagPath = om.MDagPath()
        selectionList.getDagPath(0, nodeDagPath)
    except Exception as e:
        raise RuntimeError("MDagPath failed "
                           "on {}. \n {}".format(geo.name(), e))

    mfnMesh = om.MFnMesh(nodeDagPath)

    pointA = om.MPoint(pos.x, pos.y, pos.z)
    pointB = om.MPoint()
    space = om.MSpace.kWorld

    util = om.MScriptUtil()
    util.createFromInt(0)
    idPointer = util.asIntPtr()

    mfnMesh.getClosestPoint(pointA, pointB, space, idPointer)
    idx = om.MScriptUtil(idPointer).asInt()

    return geo.f[idx], pos


def get_orientation_from_polygon(face):
    """Summary

    Args:
        face (TYPE): Description
        loc (TYPE): Description

    Returns:
        TYPE: Description
    """
    normal = face.getNormal()
    v = datatypes.Vector((1, 0, 0))
    q = v.rotateTo(normal)
    rotation = q.asEulerRotation()
    deg = [pm.util.degrees(x) for x in rotation]
    return deg


def get_raycast_translation_from_mouse_click(mesh, mpx, mpy):
    """get the raycasted translation of the mouse position

    Args:
        mesh (str): mesh name
        mpx (int): mouse position x
        mpy (int): mouse position x

    Returns:
        list: XYZ position
    """
    pos = om.MPoint()
    dir = om.MVector()
    hitpoint = om.MFloatPoint()
    omui.M3dView().active3dView().viewToWorld(int(mpx), int(mpy), pos, dir)
    pos2 = om.MFloatPoint(pos.x, pos.y, pos.z)
    selectionList = om.MSelectionList()
    selectionList.add(mesh)
    dagPath = om.MDagPath()
    selectionList.getDagPath(0, dagPath)
    fnMesh = om.MFnMesh(dagPath)
    intersection = fnMesh.closestIntersection(
        om.MFloatPoint(pos2),
        om.MFloatVector(dir),
        None,
        None,
        False,
        om.MSpace.kWorld,
        99999,
        False,
        None,
        hitpoint,
        None,
        None,
        None,
        None,
        None)
    if intersection:
        x = hitpoint.x
        y = hitpoint.y
        z = hitpoint.z

        return [x, y, z]
