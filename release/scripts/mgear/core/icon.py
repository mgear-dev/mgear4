"""Predefined nurbsCurve shapes to be use as a rigging control Icons"""

#############################################
# GLOBAL
#############################################
import mgear.pymaya as pm
from maya import cmds
import maya.OpenMaya as om
import mgear.pymaya.util as pmu
from mgear.pymaya import datatypes
from mgear.core import curve, attribute

import math

import mgear

#############################################
# ICON
#############################################


def create(
    parent=None,
    name="icon",
    m=datatypes.Matrix(),
    color=(0, 0, 0),
    icon="cube",
    **kwargs
):
    """Icon master function

    **Create icon master function.**
    This function centralize all the icons creation

    Arguments:
        parent (dagNode): The parent for the new icon
        name (str): Name of the Icon.
        m (matrix): Transformation matrix of the icon
        color (int | list of float | tuple of float): The color in index base or RGB.
        icon (str): Icon type. Options: "cube", "pyramid", "square",
            "flower", "circle", "cylinder", "compas", "diamond",
                    "cubewithpeak", "sphere", "arrow", "crossarrow",
                    "cross", "null", "gear", "mgear"
        kwargs: The keyword arguments can vary depending of the icon type.
                    Please refear to the specific icon method for more info.

    Returns:
        dagNode: The newly created icon.

    """
    kwargs.setdefault("w", 1)
    kwargs.setdefault("h", 1)
    kwargs.setdefault("d", 1)
    kwargs.setdefault("po", None)
    kwargs.setdefault("ro", None)
    kwargs.setdefault("degree", 3)

    if icon == "cube":
        ctl = cube(
            parent,
            name,
            kwargs["w"],
            kwargs["h"],
            kwargs["d"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
        )
    elif icon == "pyramid":
        ctl = pyramid(
            parent,
            name,
            kwargs["w"],
            kwargs["h"],
            kwargs["d"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
        )
    elif icon == "square":
        ctl = square(
            parent,
            name,
            kwargs["w"],
            kwargs["d"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
        )
    elif icon == "flower":
        ctl = flower(
            parent,
            name,
            kwargs["w"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
            kwargs["degree"],
        )
    elif icon == "circle":
        ctl = circle(
            parent,
            name,
            kwargs["w"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
            kwargs["degree"],
        )
    elif icon == "cylinder":
        ctl = cylinder(
            parent,
            name,
            kwargs["w"],
            kwargs["h"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
            kwargs["degree"],
        )
    elif icon == "compas":
        ctl = compas(
            parent,
            name,
            kwargs["w"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
            kwargs["degree"],
        )
    elif icon == "diamond":
        ctl = diamond(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )
    elif icon == "cubewithpeak":
        ctl = cubewithpeak(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )
    elif icon == "sphere":
        ctl = sphere(
            parent,
            name,
            kwargs["w"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
            kwargs["degree"],
        )
    elif icon == "arrow":
        ctl = arrow(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )
    elif icon == "crossarrow":
        ctl = crossarrow(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )
    elif icon == "cross":
        ctl = cross(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )
    elif icon == "null":
        ctl = null(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )
    elif icon == "gear":
        kwargs.setdefault("teeth", 8)
        kwargs.setdefault("tooth_depth", 0.3)
        ctl = gear(
            parent,
            name,
            kwargs["w"],
            color,
            m,
            kwargs["po"],
            kwargs["ro"],
            kwargs["teeth"],
            kwargs["tooth_depth"],
        )
    elif icon == "mgear":
        ctl = mgear_icon(
            parent, name, kwargs["w"], color, m, kwargs["po"], kwargs["ro"]
        )

    else:
        mgear.log("invalid type of ico", mgear.sev_error)
        return

    return ctl


def cube(
    parent=None,
    name="cube",
    width=1,
    height=1,
    depth=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a CUBE shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        height (float): Height of the shape.
        depth (float): Depth of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve
            from its center.
        rot_offset (vector): The xyz rotation offset of the curve
            from its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    curves = _cube_curves(width, height, depth, pos_offset, rot_offset)
    return _build_icon(parent, name, m, curves, color=color)


def _cube_curves(width, height, depth, pos_offset=None, rot_offset=None):
    """Curve specs of the CUBE icon. See ``_build_icon``."""
    lenX = width * 0.5
    lenY = height * 0.5
    lenZ = depth * 0.5

    # p is positive, N is negative
    ppp = datatypes.Vector(lenX, lenY, lenZ)
    ppN = datatypes.Vector(lenX, lenY, lenZ * -1)
    pNp = datatypes.Vector(lenX, lenY * -1, lenZ)
    Npp = datatypes.Vector(lenX * -1, lenY, lenZ)
    pNN = datatypes.Vector(lenX, lenY * -1, lenZ * -1)
    NNp = datatypes.Vector(lenX * -1, lenY * -1, lenZ)
    NpN = datatypes.Vector(lenX * -1, lenY, lenZ * -1)
    NNN = datatypes.Vector(lenX * -1, lenY * -1, lenZ * -1)

    v_array = [
        ppp,
        ppN,
        NpN,
        NNN,
        NNp,
        Npp,
        NpN,
        Npp,
        ppp,
        pNp,
        NNp,
        pNp,
        pNN,
        ppN,
        pNN,
        NNN,
    ]

    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)

    return [("Shape", points, False, 1)]


def pyramid(
    parent=None,
    name="pyramid",
    width=1,
    height=1,
    depth=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a PYRAMIDE shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        height (float): Height of the shape.
        depth (float): Depth of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve
            from its center.
        rot_offset (vector): The xyz rotation offset of the curve
            from its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    lenX = width * 0.5
    lenY = height
    lenZ = depth * 0.5

    # p is positive, N is negative
    top = datatypes.Vector(0, lenY, 0)
    pp = datatypes.Vector(lenX, 0, lenZ)
    pN = datatypes.Vector(lenX, 0, lenZ * -1)
    Np = datatypes.Vector(lenX * -1, 0, lenZ)
    NN = datatypes.Vector(lenX * -1, 0, lenZ * -1)

    v_array = [pp, top, pN, pp, Np, top, NN, Np, NN, pN]

    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)

    node = curve.addCurve(parent, name, points, False, 1, m)

    setcolor(node, color)

    return node


def square(
    parent=None,
    name="square",
    width=1,
    depth=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a SQUARE shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        depth (float): Depth of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    curves = _square_curves(width, depth, pos_offset, rot_offset)
    return _build_icon(parent, name, m, curves, color=color)


def _square_curves(width, depth, pos_offset=None, rot_offset=None):
    """Curve specs of the SQUARE icon. See ``_build_icon``."""
    lenX = width * 0.5
    lenZ = depth * 0.5

    v0 = datatypes.Vector(lenX, 0, lenZ)
    v1 = datatypes.Vector(lenX, 0, lenZ * -1)
    v2 = datatypes.Vector(lenX * -1, 0, lenZ * -1)
    v3 = datatypes.Vector(lenX * -1, 0, lenZ)

    points = getPointArrayWithOffset([v0, v1, v2, v3], pos_offset, rot_offset)

    return [("Shape", points, True, 1)]


def flower(
    parent=None,
    name="flower",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
    degree=3,
):
    """Create a curve with a FLOWER shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width

    v0 = datatypes.Vector(0, -dlen, 0)
    v1 = datatypes.Vector(-dlen * 0.4, dlen * 0.4, 0)
    v2 = datatypes.Vector(dlen, 0, 0)
    v3 = datatypes.Vector(-dlen * 0.4, -dlen * 0.4, 0)
    v4 = datatypes.Vector(0, dlen, 0)
    v5 = datatypes.Vector(dlen * 0.4, -dlen * 0.4, 0)
    v6 = datatypes.Vector(-dlen, 0, 0)
    v7 = datatypes.Vector(dlen * 0.4, dlen * 0.4, 0)

    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6, v7], pos_offset, rot_offset
    )

    node = curve.addCurve(parent, name, points, True, degree, m)

    setcolor(node, color)

    return node


def circle(
    parent=None,
    name="circle",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
    degree=3,
):
    """Create a curve with a CIRCLE shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    v0 = datatypes.Vector(0, 0, -dlen * 1.108)
    v1 = datatypes.Vector(dlen * 0.78, 0, -dlen * 0.78)
    v2 = datatypes.Vector(dlen * 1.108, 0, 0)
    v3 = datatypes.Vector(dlen * 0.78, 0, dlen * 0.78)
    v4 = datatypes.Vector(0, 0, dlen * 1.108)
    v5 = datatypes.Vector(-dlen * 0.78, 0, dlen * 0.78)
    v6 = datatypes.Vector(-dlen * 1.108, 0, 0)
    v7 = datatypes.Vector(-dlen * 0.78, 0, -dlen * 0.78)

    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6, v7], pos_offset, rot_offset
    )

    node = curve.addCurve(parent, name, points, True, degree, m)

    setcolor(node, color)

    return node


def cylinder(
    parent=None,
    name="cylinder",
    width=1,
    heigth=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
    degree=3,
):
    """Create a curve with a CYLINDER shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        height (float): Height of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5
    dhei = heigth * 0.5

    if degree == 3:
        offsetMult = 1
    else:
        offsetMult = 1.108

    # upper circle
    v0 = datatypes.Vector(0, dhei, -dlen * 1.108)
    v1 = datatypes.Vector(dlen * 0.78, dhei, -dlen * 0.78)
    v2 = datatypes.Vector(dlen * 1.108, dhei, 0)
    v3 = datatypes.Vector(dlen * 0.78, dhei, dlen * 0.78)
    v4 = datatypes.Vector(0, dhei, dlen * 1.108)
    v5 = datatypes.Vector(-dlen * 0.78, dhei, dlen * 0.78)
    v6 = datatypes.Vector(-dlen * 1.108, dhei, 0)
    v7 = datatypes.Vector(-dlen * 0.78, dhei, -dlen * 0.78)

    # lower circle
    v8 = datatypes.Vector(0, -dhei, -dlen * 1.108)
    v9 = datatypes.Vector(dlen * 0.78, -dhei, -dlen * 0.78)
    v10 = datatypes.Vector(dlen * 1.108, -dhei, 0)
    v11 = datatypes.Vector(dlen * 0.78, -dhei, dlen * 0.78)
    v12 = datatypes.Vector(0, -dhei, dlen * 1.108)
    v13 = datatypes.Vector(-dlen * 0.78, -dhei, dlen * 0.78)
    v14 = datatypes.Vector(-dlen * 1.108, -dhei, 0)
    v15 = datatypes.Vector(-dlen * 0.78, -dhei, -dlen * 0.78)

    # curves
    v16 = datatypes.Vector(0, dhei, -dlen * offsetMult)
    v17 = datatypes.Vector(0, -dhei, -dlen * offsetMult)
    v18 = datatypes.Vector(0, -dhei, dlen * offsetMult)
    v19 = datatypes.Vector(0, dhei, dlen * offsetMult)

    v20 = datatypes.Vector(dlen * offsetMult, dhei, 0)
    v21 = datatypes.Vector(dlen * offsetMult, -dhei, 0)
    v22 = datatypes.Vector(-dlen * offsetMult, -dhei, 0)
    v23 = datatypes.Vector(-dlen * offsetMult, dhei, 0)

    def offset(vectors):
        return getPointArrayWithOffset(vectors, pos_offset, rot_offset)

    curves = [
        ("Shape", offset([v0, v1, v2, v3, v4, v5, v6, v7]), True, degree),
        ("_0crvShape", offset([v8, v9, v10, v11, v12, v13, v14, v15]), True, degree),
        ("_1crvShape", offset([v16, v17]), True, 1),
        ("_2crvShape", offset([v18, v19]), True, 1),
        ("_3crvShape", offset([v20, v21]), True, 1),
        ("_4crvShape", offset([v22, v23]), True, 1),
    ]
    return _build_icon(parent, name, m, curves, color=color)


def compas(
    parent=None,
    name="compas",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
    degree=3,
):
    """Create a curve with a COMPAS shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    division = 24

    point_pos = []
    v = datatypes.Vector(0, 0, dlen)

    for i in range(division):
        if i == division / 2:
            w = datatypes.Vector(v.x, v.y, v.z - dlen * 0.4)
        else:
            w = datatypes.Vector(v.x, v.y, v.z)
        point_pos.append(w)
        v = v.rotateBy((0, (2 * pmu.math.pi) / (division + 0.0), 0))

    points = getPointArrayWithOffset(point_pos, pos_offset, rot_offset)
    node = curve.addCurve(parent, name, points, True, degree, m)

    setcolor(node, color)

    return node


def diamond(
    parent=None,
    name="diamond",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a DIAMOND shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        height (float): Height of the shape.
        depth (float): Depth of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    top = datatypes.Vector(0, dlen, 0)
    pp = datatypes.Vector(dlen, 0, dlen)
    pN = datatypes.Vector(dlen, 0, dlen * -1)
    Np = datatypes.Vector(dlen * -1, 0, dlen)
    NN = datatypes.Vector(dlen * -1, 0, dlen * -1)
    bottom = datatypes.Vector(0, -dlen, 0)

    v_array = [
        pp,
        top,
        pN,
        pp,
        Np,
        top,
        NN,
        Np,
        NN,
        pN,
        bottom,
        NN,
        bottom,
        Np,
        bottom,
        pp,
    ]

    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)

    node = curve.addCurve(parent, name, points, False, 1, m)

    setcolor(node, color)

    return node


def cubewithpeak(
    parent=None,
    name="cubewithpeak",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a CUBE WITH PEAK shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    peak = datatypes.Vector(0, width, 0)
    ppp = datatypes.Vector(dlen, dlen, dlen)
    ppN = datatypes.Vector(dlen, dlen, dlen * -1)
    pNp = datatypes.Vector(dlen, 0, dlen)
    Npp = datatypes.Vector(dlen * -1, dlen, dlen)
    pNN = datatypes.Vector(dlen, 0, dlen * -1)
    NNp = datatypes.Vector(dlen * -1, 0, dlen)
    NpN = datatypes.Vector(dlen * -1, dlen, dlen * -1)
    NNN = datatypes.Vector(dlen * -1, 0, dlen * -1)

    v_array = [
        peak,
        ppp,
        ppN,
        peak,
        NpN,
        ppN,
        NpN,
        peak,
        Npp,
        NpN,
        NNN,
        NNp,
        Npp,
        NpN,
        Npp,
        ppp,
        pNp,
        NNp,
        pNp,
        pNN,
        ppN,
        pNN,
        NNN,
    ]

    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)

    node = curve.addCurve(parent, name, points, False, 1, m)

    setcolor(node, color)

    return node


def sphere(
    parent=None,
    name="sphere",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
    degree=3,
):
    """Create a curve with a SPHERE shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    curves = _sphere_curves(width, pos_offset, rot_offset, degree)
    return _build_icon(parent, name, m, curves, color=color)


def _sphere_curves(width, pos_offset=None, rot_offset=None, degree=3):
    """Curve specs of the SPHERE icon. See ``_build_icon``."""
    dlen = width * 0.5

    v0 = datatypes.Vector(0, 0, -dlen * 1.108)
    v1 = datatypes.Vector(dlen * 0.78, 0, -dlen * 0.78)
    v2 = datatypes.Vector(dlen * 1.108, 0, 0)
    v3 = datatypes.Vector(dlen * 0.78, 0, dlen * 0.78)
    v4 = datatypes.Vector(0, 0, dlen * 1.108)
    v5 = datatypes.Vector(-dlen * 0.78, 0, dlen * 0.78)
    v6 = datatypes.Vector(-dlen * 1.108, 0, 0)
    v7 = datatypes.Vector(-dlen * 0.78, 0, -dlen * 0.78)

    ro = datatypes.Vector([1.5708, 0, 0])

    curves = []
    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6, v7], pos_offset, rot_offset
    )
    curves.append(("Shape", points, True, degree))

    if rot_offset:
        rot_offset += ro
    else:
        rot_offset = ro
    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6, v7], pos_offset, rot_offset
    )
    curves.append(("_0crvShape", points, True, degree))

    ro = datatypes.Vector([1.5708, 0, 1.5708])
    if rot_offset:
        rot_offset += ro
    else:
        rot_offset = ro
    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6, v7], pos_offset, rot_offset + ro + ro
    )
    curves.append(("_1crvShape", points, True, degree))

    return curves


def arrow(
    parent=None,
    name="arrow",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a ARROW shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    v0 = datatypes.Vector(0, 0.3 * dlen, -dlen)
    v1 = datatypes.Vector(0, 0.3 * dlen, 0.3 * dlen)
    v2 = datatypes.Vector(0, 0.6 * dlen, 0.3 * dlen)
    v3 = datatypes.Vector(0, 0, dlen)
    v4 = datatypes.Vector(0, -0.6 * dlen, 0.3 * dlen)
    v5 = datatypes.Vector(0, -0.3 * dlen, 0.3 * dlen)
    v6 = datatypes.Vector(0, -0.3 * dlen, -dlen)

    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6], pos_offset, rot_offset
    )

    node = curve.addCurve(parent, name, points, True, 1, m)

    setcolor(node, color)

    return node


def crossarrow(
    parent=None,
    name="crossArrow",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a CROSS ARROW shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    v0 = datatypes.Vector(0.2 * dlen, 0, 0.2 * dlen)
    v1 = datatypes.Vector(0.2 * dlen, 0, 0.6 * dlen)
    v2 = datatypes.Vector(0.4 * dlen, 0, 0.6 * dlen)
    v3 = datatypes.Vector(0, 0, dlen)
    v4 = datatypes.Vector(-0.4 * dlen, 0, 0.6 * dlen)
    v5 = datatypes.Vector(-0.2 * dlen, 0, 0.6 * dlen)
    v6 = datatypes.Vector(-0.2 * dlen, 0, 0.2 * dlen)
    v7 = datatypes.Vector(-0.6 * dlen, 0, 0.2 * dlen)
    v8 = datatypes.Vector(-0.6 * dlen, 0, 0.4 * dlen)
    v9 = datatypes.Vector(-dlen, 0, 0)
    v10 = datatypes.Vector(-0.6 * dlen, 0, -0.4 * dlen)
    v11 = datatypes.Vector(-0.6 * dlen, 0, -0.2 * dlen)
    v12 = datatypes.Vector(-0.2 * dlen, 0, -0.2 * dlen)
    v13 = datatypes.Vector(-0.2 * dlen, 0, -0.6 * dlen)
    v14 = datatypes.Vector(-0.4 * dlen, 0, -0.6 * dlen)
    v15 = datatypes.Vector(0, 0, -dlen)
    v16 = datatypes.Vector(0.4 * dlen, 0, -0.6 * dlen)
    v17 = datatypes.Vector(0.2 * dlen, 0, -0.6 * dlen)
    v18 = datatypes.Vector(0.2 * dlen, 0, -0.2 * dlen)
    v19 = datatypes.Vector(0.6 * dlen, 0, -0.2 * dlen)
    v20 = datatypes.Vector(0.6 * dlen, 0, -0.4 * dlen)
    v21 = datatypes.Vector(dlen, 0, 0)
    v22 = datatypes.Vector(0.6 * dlen, 0, 0.4 * dlen)
    v23 = datatypes.Vector(0.6 * dlen, 0, 0.2 * dlen)

    v_array = [
        v0,
        v1,
        v2,
        v3,
        v4,
        v5,
        v6,
        v7,
        v8,
        v9,
        v10,
        v11,
        v12,
        v13,
        v14,
        v15,
        v16,
        v17,
        v18,
        v19,
        v20,
        v21,
        v22,
        v23,
    ]
    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)

    node = curve.addCurve(parent, name, points, True, 1, m)

    setcolor(node, color)

    return node


def cross(
    parent=None,
    name="cross",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a CROSS shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    width = width * 0.35
    offset1 = width * 0.5
    offset2 = width * 1.5

    v0 = datatypes.Vector(width, offset2, 0)
    v1 = datatypes.Vector(offset2, width, 0)
    v2 = datatypes.Vector(offset1, 0, 0)

    v3 = datatypes.Vector(offset2, -width, 0)
    v4 = datatypes.Vector(width, -offset2, 0)
    v5 = datatypes.Vector(0, -offset1, 0)

    v6 = datatypes.Vector(-width, -offset2, 0)
    v7 = datatypes.Vector(-offset2, -width, 0)
    v8 = datatypes.Vector(-offset1, 0, 0)

    v9 = datatypes.Vector(-offset2, width, 0)
    v10 = datatypes.Vector(-width, offset2, 0)
    v11 = datatypes.Vector(0, offset1, 0)

    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11],
        pos_offset,
        rot_offset,
    )

    node = curve.addCurve(parent, name, points, True, 1, m)

    setcolor(node, color)

    return node


def gear(
    parent=None,
    name="gear",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
    teeth=8,
    tooth_depth=0.3,
):
    """Create a curve with a gear shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians
        teeth (int): Number of teeth on the gear. Default is 8.
        tooth_depth (float): Depth of the teeth as a ratio of the radius.
            Default is 0.3. Range 0.0-1.0 where 0 is no teeth and 1 is
            teeth reaching the center.

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5
    tooth_depth = max(0.0, min(1.0, tooth_depth))  # Clamp between 0 and 1
    inner_radius = dlen * (1.0 - tooth_depth)
    outer_radius = dlen

    v_array = []
    teeth = max(3, teeth)  # Ensure at least 3 teeth
    angle_per_tooth = (2 * math.pi) / teeth

    for i in range(teeth):
        # Start angle for this tooth
        base_angle = i * angle_per_tooth

        # Inner point (start of tooth)
        angle1 = base_angle
        v_array.append(
            datatypes.Vector(
                math.sin(angle1) * inner_radius,
                0,
                math.cos(angle1) * inner_radius,
            )
        )

        # Outer point (first corner of tooth top)
        angle2 = base_angle + angle_per_tooth * 0.15
        v_array.append(
            datatypes.Vector(
                math.sin(angle2) * outer_radius,
                0,
                math.cos(angle2) * outer_radius,
            )
        )

        # Outer point (second corner of tooth top)
        angle3 = base_angle + angle_per_tooth * 0.35
        v_array.append(
            datatypes.Vector(
                math.sin(angle3) * outer_radius,
                0,
                math.cos(angle3) * outer_radius,
            )
        )

        # Inner point (end of tooth)
        angle4 = base_angle + angle_per_tooth * 0.5
        v_array.append(
            datatypes.Vector(
                math.sin(angle4) * inner_radius,
                0,
                math.cos(angle4) * inner_radius,
            )
        )

    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)

    node = curve.addCurve(parent, name, points, True, 1, m)

    setcolor(node, color)

    return node


def mgear_icon(
    parent=None,
    name="mgear",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with the MGEAR logo shape as a single  curve.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    dlen = width * 0.5

    cx, cy = 677.5, 678.5

    svg_scale = 550.0

    icx, icy = 657.783, 674.892
    inner_r = 300.0

    import math as _math

    inner_circle_pts = []
    start_angle = _math.radians(135)  # bottom-left of C
    end_angle = _math.radians(-135)  # top-left where gap starts
    num_inner_pts = 18
    for i in range(num_inner_pts):
        t = i / (num_inner_pts - 1)
        angle = start_angle + t * (end_angle - start_angle)
        px = icx + inner_r * _math.cos(angle)
        py = icy + inner_r * _math.sin(angle)
        inner_circle_pts.append((px, py))

    svg_points = [
        # M356.241,1095.8 - Start point
        (356.241, 1095.8),
        # C-body outer arc (bottom-left going to notch) - 3 pts
        (250.0, 990.0),
        (174.501, 860.748),
        # L - notch
        (272.058, 687.337),
        (566.274, 687.337),
        (446.906, 886.82),
        # Inner circle (generated points)
        *inner_circle_pts,
        # Gap opening to tooth 2
        (383.753, 554.6),
        # L - tooth 2 (left)
        (154.494, 553.394),
        # Outer arc - 3 pts
        (200.0, 420.0),
        (280.0, 310.0),
        (352.873, 256.473),
        # Tooth 2 tip
        (339.37, 153.042),
        (463.408, 82.072),
        # Tooth 3 base
        (558.491, 166.665),
        # Top outer edge - 3 pts
        (610.0, 157.15),
        (657.783, 157.15),
        (710.0, 160.0),
        (741.179, 163.831),
        # Tooth 3 tip
        (804.728, 82.679),
        (942.291, 121.402),
        # Tooth 4 base
        (948.502, 246.407),
        # Outer arc - 3 pts
        (1000.0, 290.0),
        (1050.0, 340.0),
        (1078.72, 373.354),
        # Tooth 4 tip
        (1158.01, 353.698),
        (1242.54, 468.925),
        # Tooth 5 base
        (1166.33, 577.058),
        # Right outer edge - 3 pts
        (1175.56, 630.0),
        (1175.56, 674.926),
        (1170.0, 720.0),
        (1168.32, 761.715),
        # Tooth 5 tip
        (1247.19, 827.407),
        (1204.32, 963.741),
        # Tooth 6 base
        (1086.04, 966.031),
        # Bottom-right outer arc - 3 pts
        (1040.0, 1020.0),
        (990.0, 1070.0),
        (953.021, 1100.33),
        # Tooth 6 tip
        (959.854, 1211.36),
        (831.258, 1273.7),
        # Back toward tooth 1
        (744.737, 1185.42),
        # Bottom outer edge - 3 pts
        (700.0, 1192.69),
        (657.783, 1192.69),
        (610.0, 1190.0),
        (559.465, 1183.37),
        # Tooth 1 tip
        (489.569, 1261.96),
        (354.693, 1214.71),
        # Z closes back to start
    ]

    v_array = []

    for svg_x, svg_y in svg_points:
        # Center the coordinates
        x = (svg_x - cx) / svg_scale
        z = (svg_y - cy) / svg_scale
        v_array.append(datatypes.Vector(x * dlen, 0, -z * dlen))

    points = getPointArrayWithOffset(v_array, pos_offset, rot_offset)
    node = curve.addCurve(parent, name, points, True, 1, m)

    setcolor(node, color)

    return node


def null(
    parent=None,
    name="null",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a NULL shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    curves = _null_curves(width, pos_offset, rot_offset)
    return _build_icon(parent, name, m, curves, base=name, color=color)


def _null_curves(width, pos_offset=None, rot_offset=None):
    """Curve specs of the NULL icon, x, y and z lines. See ``_build_icon``."""
    dlen = width * 0.5

    v0 = datatypes.Vector(dlen, 0, 0)
    v1 = datatypes.Vector(-dlen, 0, 0)
    v2 = datatypes.Vector(0, dlen, 0)
    v3 = datatypes.Vector(0, -dlen, 0)
    v4 = datatypes.Vector(0, 0, dlen)
    v5 = datatypes.Vector(0, 0, -dlen)

    return _line_curves(([v0, v1], [v2, v3], [v4, v5]), pos_offset, rot_offset)


def axis(
    parent=None,
    name="axis",
    width=1,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a AXIS shape.

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    curves = _axis_curves(width, pos_offset, rot_offset)
    node = _build_icon(parent, name, m, curves, base=name)
    _color_axis_shapes(cmds.listRelatives(node.longName(), shapes=True, fullPath=True))

    return node


def _axis_curves(width, pos_offset=None, rot_offset=None):
    """Curve specs of the AXIS icon, x, y and z lines. See ``_build_icon``."""
    dlen = width * 0.5

    v0 = datatypes.Vector(0, 0, 0)
    v1 = datatypes.Vector(dlen, 0, 0)
    v2 = datatypes.Vector(0, dlen, 0)
    v3 = datatypes.Vector(0, 0, dlen)

    return _line_curves(([v0, v1], [v0, v2], [v0, v3]), pos_offset, rot_offset)


def _line_curves(lines, pos_offset=None, rot_offset=None):
    """Curve specs of 2 point lines named Shape, 1Shape, 2Shape..."""
    return [
        (
            "{}Shape".format(index or ""),
            getPointArrayWithOffset(line, pos_offset, rot_offset),
            False,
            1,
        )
        for index, line in enumerate(lines)
    ]


def _color_axis_shapes(shapes):
    """Color the AXIS icon shapes: red x, green y, blue z."""
    for shape, axis_color in zip(shapes, (4, 14, 6)):
        curve.set_shapes_color([shape], axis_color)


##########################################################
# Display helper Icons
##########################################################
def connection_display_curve(name, centers=[], degree=1):
    """Visual reference curves connectiong points.

    Display curve object is a simple curve to show the connection between
    different guide element..

    Args:
        name (str): Local name of the element.
        centers (list of dagNode):  List of object to define the curve.
        degree (int): Curve degree. Default 1 = lineal.

    Returns:
        dagNode: The newly creted curve.

    """
    crv = curve.addCnsCurve(centers[0], name, centers, degree)
    crv.attr("overrideEnabled").set(1)
    crv.attr("overrideDisplayType").set(1)

    return crv


def direction_arrow(
    axis="z", length=1, name="direction_arrow", parent_name=None
):
    """
    Creates a curve shaped like an arrow, aligned with a specified axis and length.

    Args:
        parent_name (str): The name of the parent object. The arrow is created
            relative to its local axis.
        axis (str): The axis for the arrow direction ('x', 'y', 'z', '-x', '-y', '-z').
        length (float): The length of the arrow.

    Returns:
        str: The name of the created arrow curve.

    """
    # Validate axis input
    valid_axes = ["x", "y", "z", "-x", "-y", "-z"]
    if axis not in valid_axes:
        raise ValueError(
            "Invalid axis '{}'. Must be one of: {}".format(axis, valid_axes)
        )

    # Define arrow points in local space
    size_ratio = 0.9
    tip = [0, 0, length]
    base1 = [-0.1 * length, 0, size_ratio * length]
    base2 = [0.1 * length, 0, size_ratio * length]
    base3 = [-0.05 * length, 0, size_ratio * length]
    base4 = [0.05 * length, 0, size_ratio * length]
    shaft_start = [0, 0, 0]
    shaft_end = [0, 0, size_ratio * length]

    # Assemble the arrow shape
    points = [
        shaft_start,
        shaft_end,
        base4,
        base2,
        tip,
        base1,
        base3,
        shaft_end,
    ]

    # Transform points to match the axis
    for i in range(len(points)):
        if axis == "x":
            points[i] = [points[i][2], points[i][1], points[i][0]]
        elif axis == "-x":
            points[i] = [-points[i][2], points[i][1], points[i][0]]
        elif axis == "y":
            points[i] = [points[i][0], points[i][2], points[i][1]]
        elif axis == "-y":
            points[i] = [points[i][0], -points[i][2], points[i][1]]
        elif axis == "-z":
            points[i] = [points[i][0], points[i][1], -points[i][2]]

    # Create the curve
    arrow_curve = cmds.curve(p=points, d=1, n=name)

    if parent_name:
        cmds.parent(arrow_curve, parent_name)

    return pm.PyNode(arrow_curve)


##########################################################
# Guide Icons
##########################################################


def guideRootIcon(
    parent=None,
    name="root",
    width=0.5,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a ROOT GUIDE shape.

    Note:
        This icon is specially design for **Shifter** root guides

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    cubeWidth = width / 2.0
    return _guide_icon(
        parent,
        name,
        m,
        color,
        _null_curves(width, pos_offset, rot_offset),
        _cube_curves(cubeWidth, cubeWidth, cubeWidth, pos_offset, rot_offset),
    )


def guideRootIcon2D(
    parent=None,
    name="root",
    width=0.5,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a 2D ROOT GUIDE shape.

    Note:
        This icon is specially design for **Shifter** root guides

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    rot_offset_orig = datatypes.Vector(math.radians(90), 0, 0)
    if rot_offset:
        rot_offset_orig.rotateBy(rot_offset)

    squareWidth = width / 2.0
    return _guide_icon(
        parent,
        name,
        m,
        color,
        # null without the z axis
        _null_curves(width, pos_offset, rot_offset)[:2],
        _square_curves(squareWidth, squareWidth, pos_offset, rot_offset_orig),
    )


def guideLocatorIcon(
    parent=None,
    name="locator",
    width=0.5,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a LOCATOR GUIDE shape.

    Note:
        This icon is specially design for **Shifter** locator guides

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        width (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    spheWidth = width / 2.0
    return _guide_icon(
        parent,
        name,
        m,
        color,
        _null_curves(width, pos_offset, rot_offset),
        _sphere_curves(spheWidth, pos_offset, rot_offset, degree=3),
    )


def guideBladeIcon(
    parent=None,
    name="blade",
    lenX=1.0,
    color=(0, 0, 0),
    m=datatypes.Matrix(),
    pos_offset=None,
    rot_offset=None,
):
    """Create a curve with a BLADE GUIDE shape.

    Note:
        This icon is specially design for **Shifter** blade guides

    Arguments:
        parent (dagNode): The parent object of the newly created curve.
        name (str): Name of the curve.
        lenX (float): Width of the shape.
        color (int | list of float | tuple of float): The color in index base or RGB.
        m (matrix): The global transformation of the curve.
        pos_offset (vector): The xyz position offset of the curve from
            its center.
        rot_offset (vector): The xyz rotation offset of the curve from
            its center. xyz in radians

    Returns:
        dagNode: The newly created icon.

    """
    v0 = datatypes.Vector(0, 0, 0)
    v1 = datatypes.Vector(lenX / 2, 0, 0)
    v2 = datatypes.Vector(lenX, lenX / 4, 0)
    v3 = datatypes.Vector(lenX / 2, lenX / 2, 0)
    v4 = datatypes.Vector(0, lenX / 2, 0)

    points = getPointArrayWithOffset(
        [v0, v1, v2, v3, v4], pos_offset, rot_offset
    )

    bladeIco = curve.addCurve(parent, name, points, True, 1, m)

    setcolor(bladeIco, color)

    attribute.setNotKeyableAttributes(bladeIco)
    attribute.unlockAttribute(
        bladeIco,
        attributes=[
            "tx",
            "ty",
            "tz",
            "rx",
            "ry",
            "rz",
            "sx",
            "sy",
            "sz",
            "v",
            "ro",
        ],
    )
    # bladeIco.scale.set(1, 1, 1)
    # Set the control shapes isHistoricallyInteresting
    for oShape in bladeIco.getShapes():
        oShape.isHistoricallyInteresting.set(False)

    return bladeIco


##########################################################
# MISC
##########################################################
# ========================================================


def _build_icon(parent, name, m, curves, base=None, color=None):
    """Create an icon transform with all its curve shapes.

    The first curve creates the transform (``curve.addCurve``). The others
    are added under it as extra shapes, with no temporary transforms.

    Args:
        parent (dagNode): The parent of the icon.
        name (str): Name of the icon.
        m (matrix): The global transformation of the icon.
        curves (list of tuple): ``(suffix, points, close, degree)`` per
            curve, from the ``_<icon>_curves`` functions.
        base (str, optional): Name base of the extra shapes, see
            ``_add_curves``.
        color (int | list of float | tuple of float, optional): Icon color.
            None leaves the shapes uncolored.

    Returns:
        dagNode: The icon transform.
    """
    _, points, close, degree = curves[0]
    node = curve.addCurve(parent, name, points, close, degree, m)
    _add_curves(node, curves[1:], base)
    if color is not None:
        setcolor(node, color)
    return node


def _guide_icon(parent, name, m, color, null_curves, extra_curves):
    """Create a guide icon: a null with an extra shape (cube, sphere...).

    Args:
        parent (dagNode): The parent of the icon.
        name (str): Name of the icon.
        m (matrix): The global transformation of the icon.
        color (int | list of float | tuple of float): The icon color.
        null_curves (list of tuple): Curve specs of the null part.
        extra_curves (list of tuple): Curve specs of the extra shape.

    Returns:
        dagNode: The guide icon.
    """
    node = _build_icon(parent, name, m, null_curves, base=name)
    _add_curves(node, extra_curves, name + "3")
    return _finish_guide_icon(node, color)


def _add_curves(node, curves, base=None):
    """Add curve shapes under an icon transform.

    Icons used to build each extra curve as a temporary transform and move
    its shape under the icon. The shapes keep the names they got that way:
    ``<base><suffix>``.

    Args:
        node (str or dagNode): The icon transform.
        curves (list of tuple): ``(suffix, points, close, degree)`` per
            curve, in the icon's object space.
        base (str, optional): Shape name base. Defaults to the icon name.

    Returns:
        list of str: Long names of the new shapes.
    """
    base = base or str(node).split("|")[-1]
    return [
        curve.add_curve_shape(node, points, close, degree, name=base + suffix)
        for suffix, points, close, degree in curves
    ]


def add_icon_shapes(
    node,
    icon="sphere",
    name=None,
    width=1,
    color=(0, 0, 0),
    scale=None,
    pos_offset=None,
    rot_offset=None,
    degree=3,
):
    """Add the curve shapes of an icon under an existing transform.

    Creates no transform, so it is the cheap way to add a visual reference
    (an axis, a sphere...) to an object that already exists.

    Args:
        node (str or dagNode): The transform to add the shapes to.
        icon (str, optional): Icon type: "axis", "sphere", "null", "cube"
            or "square".
        name (str, optional): Shape name base. Defaults to the node name.
        width (float, optional): Width of the icon.
        color (int | list of float | tuple of float, optional): The color in
            index base or RGB. The axis icon is always red, green, blue.
        scale (list of float, optional): Per axis scale multiplied into the
            points, e.g. to bake the node's world scale in the shapes.
        pos_offset (vector, optional): The xyz position offset of the icon.
        rot_offset (vector, optional): The xyz rotation offset of the icon,
            in radians.
        degree (int, optional): Curve degree of the sphere icon.

    Returns:
        list of str: Long names of the new shapes.
    """
    if icon == "axis":
        curves = _axis_curves(width, pos_offset, rot_offset)
    elif icon == "sphere":
        curves = _sphere_curves(width, pos_offset, rot_offset, degree)
    elif icon == "null":
        curves = _null_curves(width, pos_offset, rot_offset)
    elif icon == "cube":
        curves = _cube_curves(width, width, width, pos_offset, rot_offset)
    elif icon == "square":
        curves = _square_curves(width, width, pos_offset, rot_offset)
    else:
        raise ValueError("Icon type {!r} can't be added as shapes".format(icon))

    if scale is not None:
        curves = [
            (suffix, [[p[i] * scale[i] for i in range(3)] for p in points], close, d)
            for suffix, points, close, d in curves
        ]
    shapes = _add_curves(node, curves, name)
    if icon == "axis":
        _color_axis_shapes(shapes)
    else:
        curve.set_shapes_color(shapes, color)
    return shapes


def _finish_guide_icon(node, color):
    """Color a guide icon and set the guide icon channels and attributes.

    Args:
        node (dagNode): The guide icon transform.
        color (int | list of float | tuple of float): The color in index
            base or RGB.

    Returns:
        dagNode: The guide icon.
    """
    shapes = cmds.listRelatives(node.longName(), shapes=True, fullPath=True)
    curve.set_shapes_color(shapes, color)
    attribute.setNotKeyableAttributes(node)
    cmds.addAttr(
        node.longName(), longName="isGearGuide", attributeType="bool", defaultValue=True
    )
    for shape in shapes:
        cmds.setAttr(shape + ".isHistoricallyInteresting", False)
    return node


def getPointArrayWithOffset(point_pos, pos_offset=None, rot_offset=None):
    """Get Point array with offset

    Convert a list of vector to a List of float and add the position and
    rotation offset.

    Arguments:
        point_pos (list of vector): Point positions.
        pos_offset (vector):  The position offset of the curve from its
            center.
        rot_offset (vector): The rotation offset of the curve from its
            center. In radians.

    Returns:
        list of vector: the new point positions

    """
    points = []
    for v in point_pos:
        if rot_offset:
            mv = om.MVector(v.x, v.y, v.z)
            mv = mv.rotateBy(
                om.MEulerRotation(
                    rot_offset.x,
                    rot_offset.y,
                    rot_offset.z,
                    om.MEulerRotation.kXYZ,
                )
            )
            v = datatypes.Vector(mv.x, mv.y, mv.z)
        if pos_offset:
            v = v + pos_offset

        points.append(v)

    return points


def setcolor(node, color):
    """Set the color in the Icons.

    Arguments:
        node(dagNode): The object
        color (int | list of float | tuple of float): The color in index base or RGB.

    """
    # TODO: configure this funcion to work with RGB or Index color base
    # on Maya version.
    # version = mgear.core.getMayaver()

    curve.set_color(node, color)
