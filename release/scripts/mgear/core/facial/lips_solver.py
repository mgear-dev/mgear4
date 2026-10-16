"""Lips geometry solver: reads the lips loop, creates nothing.

The solver orders the closed loop between the lips by topology, finds the
mouth corners and splits the loop into the upper and lower lips in a mouth
frame. Lips Rigger 1.0 sorted the points by world X and offset them along
world axes, which broke on tilted heads; the mouth frame makes them work the
same at any angle.
"""

from maya import cmds

from mgear.core import meshNavigation
from mgear.core import vector

from . import lips_schema
from ._solve_base import world_front

# the lateral axis of the mouth frame is world X: the left side is +lateral
LATERAL_HINT = (1.0, 0.0, 0.0)

# control shape offset in front of the lips, as a part of the mouth width,
# when no aim point gives it (Lips Rigger 1.0 proportion)
CONTROL_OFFSET_RATIO = 0.21


class LipsGeometry(object):
    """Solved lips geometry.

    Attributes:
        mesh (str): Mesh of the lips loop.
        frame (dict): Mouth frame, see
            :func:`mgear.core.vector.get_direction_frame`.
            Lateral points to the character left, up to the nose and normal
            out of the mouth.
        loop (list): Ordered loop vertices.
        r_corner (int): Right corner vertex.
        l_corner (int): Left corner vertex.
        upper (list): Upper lip vertices from the right to the left corner.
        lower (list): Lower lip vertices from the right to the left corner.
        upper_points (list): World positions of the upper vertices.
        lower_points (list): World positions of the lower vertices.
        up_mid (int): Upper lip vertex nearest the mouth center.
        low_mid (int): Lower lip vertex nearest the mouth center.
        thickness (float): Depth of the joints inside the lips.
        upper_curve_points (list): Upper lip points moved into the lip by
            the thickness, where the upper joints sit at rest.
        lower_curve_points (list): Same for the lower lip.
        mouth_width (float): Distance between the corners.
        control_offset (float): Distance of the control shapes in front of
            the lips.
        rig_matrix (list): Flat 4x4 right handed matrix of the mouth frame
            at the loop center.
        control_matrix (list): Flat 4x4 control space of the center and left
            controls, the rig matrix.
        r_control_matrix (list): Control space of the right controls: the
            mirrored, left handed frame with mirror behavior, else the rig
            matrix.
    """

    def __init__(self):
        self.mesh = None
        self.frame = None
        self.loop = []
        self.r_corner = None
        self.l_corner = None
        self.upper = []
        self.lower = []
        self.upper_points = []
        self.lower_points = []
        self.up_mid = None
        self.low_mid = None
        self.thickness = 0.0
        self.upper_curve_points = []
        self.lower_curve_points = []
        self.mouth_width = 1.0
        self.control_offset = 0.0
        self.rig_matrix = None
        self.control_matrix = None
        self.r_control_matrix = None

    def side_matrix(self, side):
        """Get the control space of a side.

        Args:
            side (str): "R", "C" or "L".

        Returns:
            list: Flat 4x4 matrix.
        """
        return self.r_control_matrix if side == "R" else self.control_matrix


def _offset(point, *moves):
    """Move a point by (axis, distance) pairs."""
    point = list(point)
    for axis, distance in moves:
        for i in range(3):
            point[i] += axis[i] * distance
    return tuple(point)


def _mid_vertex(path, positions, frame):
    """Get the vertex of a path nearest the mouth center laterally."""
    inner = path[1:-1] or path
    return min(
        inner,
        key=lambda v: abs(vector.to_frame_coordinates(positions[v], frame)[0]),
    )


def _lip_curve_points(points, frame, thickness, upper):
    """Move the lip points into the lip, along the frame.

    The inner points move up (upper lip) or down (lower lip). The corners
    move back and outward, as Lips Rigger 1.0 did along world axes.
    """
    up = frame["up"]
    lateral = frame["lateral"]
    back = tuple(-value for value in frame["normal"])
    sign = 1.0 if upper else -1.0
    last = len(points) - 1
    result = []
    for i, point in enumerate(points):
        if i == 0:
            result.append(_offset(point, (back, thickness), (lateral, -thickness)))
        elif i == last:
            result.append(_offset(point, (back, thickness), (lateral, thickness)))
        else:
            result.append(_offset(point, (up, thickness * sign)))
    return result


def solve(settings, center=None, aim=None, front=None):
    """Solve the lips geometry from the settings.

    A Shifter component gives the mouth center and an aim point from its
    guide. The tool gives a front point, or nothing: the mouth then faces
    the scene front. The loop normal is not used, a lips loop curves too
    much in depth for it.

    Args:
        settings (dict): Coerced lips settings, see
            :mod:`mgear.core.facial.lips_schema`.
        center (tuple, optional): Mouth center, the start of the aim
            direction.
        aim (tuple, optional): Point in front of the mouth. The mouth frame
            faces it, and the control offset is its depth in front of the
            lips.
        front (tuple, optional): Point in front of the mouth, the mouth
            faces it from the loop center. Only the direction is used.

    Returns:
        LipsGeometry: The solved geometry.

    Raises:
        ValueError: If the settings don't describe a valid lips loop.
    """
    loop_type = lips_schema.LOOP_TYPES[settings["loopType"]]
    mesh, kind, indices = meshNavigation.parse_component_string(
        lips_schema.loop_string(settings)
    )
    if not indices:
        raise ValueError("Set the lips {} loop".format(loop_type))
    if not cmds.objExists(mesh):
        raise ValueError("The lips mesh {} doesn't exist".format(mesh))

    ordered, closed = meshNavigation.get_ordered_loop(mesh, indices, kind)
    if not closed:
        raise ValueError("The lips loop must be a closed loop")
    points = meshNavigation.get_vertex_world_positions(mesh, ordered)
    positions = dict(zip(ordered, points))
    count = float(len(points))
    loop_center = tuple(sum(p[i] for p in points) / count for i in range(3))

    if aim is not None:
        start = tuple(center) if center is not None else loop_center
        direction = tuple(aim[i] - start[i] for i in range(3))
    elif front is not None:
        direction = tuple(front[i] - loop_center[i] for i in range(3))
    else:
        direction = world_front()
    frame = vector.get_direction_frame(loop_center, direction, LATERAL_HINT)

    extremes = vector.extremes_in_frame(points, frame)
    r_corner = ordered[extremes["lateral_min"]]
    l_corner = ordered[extremes["lateral_max"]]
    path, other = meshNavigation.split_loop_at_vertices(
        ordered, True, r_corner, l_corner
    )

    def height(path_vertices):
        inner = path_vertices[1:-1] or path_vertices
        return sum(
            vector.to_frame_coordinates(positions[v], frame)[1] for v in inner
        ) / len(inner)

    # the mean height of the whole lip, so a mid vertex crossing under the
    # other lip (closed lips) doesn't swap them
    upper, lower = (path, other) if height(path) >= height(other) else (other, path)
    if settings["invertLips"]:
        upper, lower = lower, upper

    geometry = LipsGeometry()
    geometry.mesh = mesh
    geometry.frame = frame
    geometry.loop = ordered
    geometry.r_corner = r_corner
    geometry.l_corner = l_corner
    geometry.upper = upper
    geometry.lower = lower
    geometry.upper_points = [positions[v] for v in upper]
    geometry.lower_points = [positions[v] for v in lower]
    geometry.up_mid = _mid_vertex(upper, positions, frame)
    geometry.low_mid = _mid_vertex(lower, positions, frame)
    thickness = settings["thickness"]
    geometry.thickness = thickness
    geometry.upper_curve_points = _lip_curve_points(
        geometry.upper_points, frame, thickness, upper=True
    )
    geometry.lower_curve_points = _lip_curve_points(
        geometry.lower_points, frame, thickness, upper=False
    )
    geometry.mouth_width = (
        vector.distance(positions[r_corner], positions[l_corner]) or 1.0
    )
    if aim is not None:
        geometry.control_offset = max(vector.to_frame_coordinates(aim, frame)[2], 0.0)
    else:
        geometry.control_offset = geometry.mouth_width * CONTROL_OFFSET_RATIO

    lateral = frame["lateral"]
    geometry.rig_matrix = vector.axes_matrix(
        lateral, frame["up"], frame["normal"], loop_center
    )
    geometry.control_matrix = geometry.rig_matrix
    if settings["mirrorBehavior"]:
        geometry.r_control_matrix = vector.axes_matrix(
            tuple(-value for value in lateral),
            frame["up"],
            frame["normal"],
            loop_center,
        )
    else:
        geometry.r_control_matrix = geometry.rig_matrix
    return geometry


def detection_selection(geometry):
    """Get what Check Detection selects: the upper lip, corners included.

    Args:
        geometry (LipsGeometry): Solved geometry.

    Returns:
        list: Component strings to select.
    """
    text = meshNavigation.format_component_string(
        geometry.mesh, "vertex", geometry.upper
    )
    return text.split(",")
