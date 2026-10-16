"""Brow geometry solver: reads the brow path, creates nothing.

The solver orders the open path along the brow by topology, from the inner
to the outer end for the left and right brows, and from the right to the
left end for the center brow. Brow Rigger 1.0 used world axes and built
both sides and the center at once; 3.0 solves one brow in a brow frame.
"""

from maya import cmds

from mgear.core import meshNavigation
from mgear.core import vector

from . import brow_schema
from ._solve_base import world_front

# the lateral axis of the brow frame is world X: the left side is +lateral
LATERAL_HINT = (1.0, 0.0, 0.0)

# control shape offset in front of the brow, as a part of its length, when
# no aim point gives it
CONTROL_OFFSET_RATIO = 0.07

# path centers this close to the head mid plane, as a part of the path
# length, are center brows
CENTER_TOLERANCE = 0.1


class BrowGeometry(object):
    """Solved brow geometry.

    Attributes:
        mesh (str): Mesh of the brow path.
        side (str): "L", "R" or "C".
        frame (dict): Brow frame, see
            :func:`mgear.core.vector.get_direction_frame`.
        path (list): Path vertices, inner to outer end (L and R) or right to
            left end (C).
        points (list): World positions of the path vertices.
        curve_points (list): Points moved under the brow by the joint depth,
            where the joints sit at rest.
        thickness (float): Joint depth under the brow.
        length (float): Length of the path.
        control_offset (float): Distance of the control shapes in front of
            the brow.
        rig_matrix (list): Flat 4x4 right handed matrix of the frame at the
            path center.
        control_matrix (list): Control space: X from the first to the last
            path end. Mirrored, left handed, for a right brow with mirror
            behavior.
    """

    def __init__(self):
        self.mesh = None
        self.side = None
        self.frame = None
        self.path = []
        self.points = []
        self.curve_points = []
        self.thickness = 0.0
        self.length = 1.0
        self.control_offset = 0.0
        self.rig_matrix = None
        self.control_matrix = None


def _length(points):
    return sum(vector.distance(a, b) for a, b in zip(points, points[1:]))


def solve(settings, center=None, aim=None, front=None, side=None):
    """Solve the brow geometry from the settings.

    A Shifter component gives the guide center, aim point and side. The
    tool gives a front point, or nothing: the brow then faces the scene
    front, and the side comes from the settings or the path position.

    Args:
        settings (dict): Coerced brow settings, see
            :mod:`mgear.core.facial.brow_schema`.
        center (tuple, optional): Guide root, the start of the aim direction.
        aim (tuple, optional): Point in front of the brow. The brow frame
            faces it, and the control offset is its depth in front of the
            brow.
        front (tuple, optional): Point in front of the brow, the brow faces
            it from the path center. Only the direction is used.
        side (str, optional): "L", "R" or "C", instead of the settings.

    Returns:
        BrowGeometry: The solved geometry.

    Raises:
        ValueError: If the settings don't describe a valid brow path.
    """
    loop_type = brow_schema.LOOP_TYPES[settings["loopType"]]
    mesh, kind, indices = meshNavigation.parse_component_string(
        brow_schema.loop_string(settings)
    )
    if not indices:
        raise ValueError("Set the brow {} path".format(loop_type))
    if not cmds.objExists(mesh):
        raise ValueError("The brow mesh {} doesn't exist".format(mesh))

    ordered, closed = meshNavigation.get_ordered_loop(mesh, indices, kind)
    if closed:
        raise ValueError("The brow needs an open path, not a closed loop")
    if len(ordered) < 2:
        raise ValueError("The brow path needs at least 2 vertices")
    points = meshNavigation.get_vertex_world_positions(mesh, ordered)
    count = float(len(points))
    path_center = tuple(sum(p[i] for p in points) / count for i in range(3))
    length = _length(points)

    if aim is not None:
        start = tuple(center) if center is not None else path_center
        direction = tuple(aim[i] - start[i] for i in range(3))
    elif front is not None:
        direction = tuple(front[i] - path_center[i] for i in range(3))
    else:
        direction = world_front()
    frame = vector.get_direction_frame(path_center, direction, LATERAL_HINT)

    if not side:
        side = brow_schema.SIDES[settings.get("side", 0)]
    if side == "auto":
        side = vector.detect_side(path_center[0], length * CENTER_TOLERANCE)

    if side == "C":
        first, last = (
            vector.to_frame_coordinates(points[i], frame)[0] for i in (0, -1)
        )
        reverse = first > last
    else:
        # the inner end is the one nearest the head mid plane
        reverse = abs(points[0][0]) > abs(points[-1][0])
    if reverse:
        ordered = ordered[::-1]
        points = points[::-1]

    geometry = BrowGeometry()
    geometry.mesh = mesh
    geometry.side = side
    geometry.frame = frame
    geometry.path = ordered
    geometry.points = [tuple(p) for p in points]
    thickness = settings["thickness"]
    geometry.thickness = thickness
    normal = frame["normal"]
    geometry.curve_points = [
        tuple(p[i] - normal[i] * thickness for i in range(3)) for p in points
    ]
    geometry.length = length or 1.0
    if aim is not None:
        geometry.control_offset = max(vector.to_frame_coordinates(aim, frame)[2], 0.0)
    else:
        geometry.control_offset = geometry.length * CONTROL_OFFSET_RATIO

    lateral = frame["lateral"]
    geometry.rig_matrix = vector.axes_matrix(lateral, frame["up"], normal, path_center)
    if side == "R" and settings["mirrorBehavior"]:
        geometry.control_matrix = vector.axes_matrix(
            tuple(-value for value in lateral), frame["up"], normal, path_center
        )
    else:
        geometry.control_matrix = geometry.rig_matrix
    return geometry


def detection_selection(geometry):
    """Get what Check Detection selects: the first path end.

    It is the inner end of a left or right brow, the right end of a center
    brow.

    Args:
        geometry (BrowGeometry): Solved geometry.

    Returns:
        list: Component strings to select.
    """
    return ["{}.vtx[{}]".format(geometry.mesh, geometry.path[0])]
