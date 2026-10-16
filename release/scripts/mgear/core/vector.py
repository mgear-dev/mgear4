"""Functions to work with vectors"""

import math
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya

from mgear.pymaya import datatypes
from mgear.core import utils


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


@utils.ensure_pynode
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


def get_mvector(obj):
    """Get MVector position of an object in world space.

    Args:
        obj (str): Object name.

    Returns:
        OpenMaya.MVector: Position in world space.
    """
    pos = cmds.xform(obj, q=True, ws=True, t=True)
    return OpenMaya.MVector(pos[0], pos[1], pos[2])


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

    if vector0.isParallel(vector1):
        # if vectors are parallel, we use an arbitrary up vector to resolve the plane.
        # TODO: add an optional parameter to this function so joints will be aligned from the given guide axis instead of arbitrary vector.
        normal = vector0 ^ datatypes.Vector(0, 0, -1)
    else:
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


def calculatePoleVector(p1, p2, p3, poleDistance=1, time=1):
    """
    This function takes 3  PyNodes as inputs.
    Creates a pole vector position at a "nice" distance away from a triangle
    of positions.
    Normalizes the bone lengths relative to the knee to calculate straight
    ahead without shifting up and down if the bone lengths are different.
    Returns a pymel.core.datatypes.Vector

    Arguments:
        p1 (dagNode): Object A
        p2 (dagNode): Object B
        p3 (dagNode): Object C
        poleDistance (float): distance of the pole vector from the mid point

    Returns:
        vector: The transposed vector.
    """

    vec1 = p1.worldMatrix.get(time=time).translate
    vec2 = p2.worldMatrix.get(time=time).translate
    vec3 = p3.worldMatrix.get(time=time).translate

    # 1. Calculate a "nice distance" based on average of the two bone lengths.
    leg_length = (vec2 - vec1).length()
    knee_length = (vec3 - vec2).length()
    distance = (leg_length + knee_length) * 0.5 * poleDistance

    # 2. Normalize the length of leg and ankle, relative to the knee.
    # This will ensure that the pole vector goes STRAIGHT ahead of the knee
    # Avoids up-down offset if there is a length difference between the two
    # bones.
    vec1norm = ((vec1 - vec2).normal() * distance) + vec2
    vec3norm = ((vec3 - vec2).normal() * distance) + vec2

    # 3. given 3 points, calculate a pole vector position
    mid = vec1norm + (vec2 - vec1norm).projectionOnto(vec3norm - vec1norm)

    # 4. Move the pole vector in front of the knee by the "nice distance".
    mid_pointer = vec2 - mid
    pole_vector = (mid_pointer.normal() * distance) + vec2

    return pole_vector


def subtract_3Dvectors_list(vec_a, vec_b):
    """Subtract two 3D vectors represented as lists.

    Args:
        vec_a (list): First vector [x, y, z].
        vec_b (list): Second vector [x, y, z].

    Returns:
        list: Resulting vector after subtraction.
    """
    if len(vec_a) != 3 or len(vec_b) != 3:
        raise ValueError("Both vectors must have 3 elements.")

    return [a - b for a, b in zip(vec_a, vec_b)]


def add_3Dvectors_list(vec_a, vec_b):
    """Add two 3D vectors represented as lists.

    Args:
        vec_a (list): First vector [x, y, z].
        vec_b (list): Second vector [x, y, z].

    Returns:
        list: Resulting vector after addition.
    """
    if len(vec_a) != 3 or len(vec_b) != 3:
        raise ValueError("Both vectors must have 3 elements.")

    return [a + b for a, b in zip(vec_a, vec_b)]


#############################################
# LOOP FRAME
#############################################


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def distance(a, b):
    """Get the distance between 2 points given as plain sequences.

    Same result as math.dist, which needs Python 3.8 (Maya 2022 is 3.7).

    Args:
        a (tuple or list): First point as 3 floats.
        b (tuple or list): Second point as 3 floats.

    Returns:
        float: Distance between the points.
    """
    offset = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    return math.sqrt(_dot(offset, offset))


def _unit(v):
    length = math.sqrt(_dot(v, v))
    if length < 1e-12:
        raise ValueError("Can't normalize a zero length vector")
    return (v[0] / length, v[1] / length, v[2] / length)


def newell_normal(points):
    """Get the unit normal of an ordered loop of points (Newell's method).

    Args:
        points (list): Ordered (x, y, z) points, at least 3.

    Returns:
        tuple: (x, y, z) unit normal. Its direction follows the point order
            (counterclockwise seen from the normal).
    """
    normal = [0.0, 0.0, 0.0]
    count = len(points)
    for i in range(count):
        a = points[i]
        b = points[(i + 1) % count]
        normal[0] += (a[1] - b[1]) * (a[2] + b[2])
        normal[1] += (a[2] - b[2]) * (a[0] + b[0])
        normal[2] += (a[0] - b[0]) * (a[1] + b[1])
    return _unit(normal)


def axes_matrix(x_axis, y_axis, z_axis, position):
    """Get a flat row-major 4x4 matrix from its axes and position.

    Args:
        x_axis (tuple): X axis.
        y_axis (tuple): Y axis.
        z_axis (tuple): Z axis.
        position (tuple): Translation.

    Returns:
        list: 16 floats.
    """
    matrix = []
    for row, w in ((x_axis, 0.0), (y_axis, 0.0), (z_axis, 0.0), (position, 1.0)):
        matrix += [row[0], row[1], row[2], w]
    return matrix


def get_loop_frame(points, normal_hint=None, lateral_hint=(1.0, 0.0, 0.0)):
    """Get a local frame for a loop of points.

    The normal is the loop normal, flipped to agree with normal_hint. The
    lateral axis is lateral_hint projected on the loop plane, and
    up = normal x lateral. The matrix axes are X = lateral, Y = up,
    Z = normal, at the loop center.

    Args:
        points (list): Ordered (x, y, z) points, at least 3.
        normal_hint (tuple, optional): Direction the normal should face.
        lateral_hint (tuple, optional): Direction of the lateral axis.

    Returns:
        dict: center, normal, lateral and up tuples, and matrix (a flat
            row-major list of 16 floats).
    """
    count = float(len(points))
    center = tuple(sum(p[i] for p in points) / count for i in range(3))
    normal = newell_normal(points)
    if normal_hint is not None and _dot(normal, normal_hint) < 0:
        normal = (-normal[0], -normal[1], -normal[2])
    return get_direction_frame(center, normal, lateral_hint)


def get_direction_frame(center, direction, lateral_hint=(1.0, 0.0, 0.0)):
    """Get a local frame facing a direction.

    The normal is the direction. The lateral axis is lateral_hint projected
    on the plane facing the direction (another axis when the hint is
    parallel to it), and up = normal x lateral. The matrix axes are
    X = lateral, Y = up, Z = normal, at center.

    Args:
        center (tuple): Frame origin.
        direction (tuple): Direction the frame faces, any length.
        lateral_hint (tuple, optional): Direction of the lateral axis.

    Returns:
        dict: center, normal, lateral and up tuples, and matrix (a flat
            row-major list of 16 floats).
    """
    normal = _unit(direction)
    hints = (lateral_hint, (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))
    for hint in hints:
        along = _dot(hint, normal)
        projected = tuple(hint[i] - normal[i] * along for i in range(3))
        if _dot(projected, projected) > 1e-6:
            break
    lateral = _unit(projected)
    up = _cross(normal, lateral)
    return {
        "center": tuple(center),
        "normal": normal,
        "lateral": lateral,
        "up": up,
        "matrix": axes_matrix(lateral, up, normal, center),
    }


def to_frame_coordinates(point, frame):
    """Get the coordinates of a point in a loop frame.

    Args:
        point (tuple): (x, y, z) world point.
        frame (dict): Frame from get_loop_frame.

    Returns:
        tuple: (lateral, up, normal) coordinates.
    """
    offset = tuple(point[i] - frame["center"][i] for i in range(3))
    return (
        _dot(offset, frame["lateral"]),
        _dot(offset, frame["up"]),
        _dot(offset, frame["normal"]),
    )


def extremes_in_frame(points, frame):
    """Get the indices of the extreme points measured in a loop frame.

    Args:
        points (list): (x, y, z) points.
        frame (dict): Frame from get_loop_frame.

    Returns:
        dict: Point indices for "lateral_min", "lateral_max", "up_min" and
            "up_max".
    """
    coordinates = [to_frame_coordinates(p, frame) for p in points]
    indices = range(len(points))
    return {
        "lateral_min": min(indices, key=lambda i: coordinates[i][0]),
        "lateral_max": max(indices, key=lambda i: coordinates[i][0]),
        "up_min": min(indices, key=lambda i: coordinates[i][1]),
        "up_max": max(indices, key=lambda i: coordinates[i][1]),
    }


def detect_side(x, tolerance=1e-3):
    """Get the side of a position from its X value.

    Args:
        x (float): World X value.
        tolerance (float): Values within it are center.

    Returns:
        str: "L", "R" or "C".
    """
    if x > tolerance:
        return "L"
    if x < -tolerance:
        return "R"
    return "C"


##########################################################
# CLASS
##########################################################
class Blade(object):
    """The Blade object for shifter guides"""

    def __init__(self, t=datatypes.Matrix()):

        self.transform = t
        mdata = t.get()
        # Flatten matrix efficiently
        d = [val for row in mdata for val in row]

        m = OpenMaya.MMatrix()
        OpenMaya.MScriptUtil.createMatrixFromList(d, m)
        m = OpenMaya.MTransformationMatrix(m)

        x = OpenMaya.MVector(1, 0, 0).rotateBy(m.rotation())
        y = OpenMaya.MVector(0, 1, 0).rotateBy(m.rotation())
        z = OpenMaya.MVector(0, 0, 1).rotateBy(m.rotation())

        self.x = datatypes.Vector(x.x, x.y, x.z)
        self.y = datatypes.Vector(y.x, y.y, y.z)
        self.z = datatypes.Vector(z.x, z.y, z.z)
