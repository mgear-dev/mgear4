"""Eyelid geometry solver: reads the eye and eyelid loop, creates nothing.

The solver orders the eyelid loop, finds its corners and splits it into the
upper and lower lid, in a frame local to the loop. It replaces the world
axes and scene up axis checks of Eye Rigger 2.1, so tilted and side facing
eyes work the same.
"""

import math

from maya import cmds

from mgear.core import meshNavigation
from mgear.core import vector

from . import eyelid_schema


class EyelidGeometry(object):
    """Solved eyelid geometry.

    Attributes:
        mesh (str): Mesh of the eyelid loop.
        side (str): "L", "R" or "C".
        mirrored (bool): True when the control frame is mirrored (R side
            with mirror behavior).
        frame (dict): Loop frame, see :func:`mgear.core.vector.get_loop_frame`.
            Its lateral axis is the world X axis on the loop plane.
        eye_center (tuple): Center of the eyeball.
        eye_size (float): Mean bounding box size of the eyeball, or twice
            the eyelid opening radius without an eyeball mesh.
        offset (float): Distance of the eyelid control shapes in front of
            the eyelid.
        aim_distance (float): Distance of the aim control shape from the
            eye center.
        loop (list): Ordered eyelid loop vertices.
        in_vertex (int): Inner (medial) corner vertex.
        out_vertex (int): Outer (lateral) corner vertex.
        upper (list): Upper lid vertices from the inner to the outer corner.
        lower (list): Lower lid vertices from the inner to the outer corner.
        upper_points (list): World positions of the upper vertices.
        lower_points (list): World positions of the lower vertices.
        control_matrix (list): Flat 4x4 world matrix of the controls space,
            at the eye center. X follows the lid from the inner to the outer
            corner when mirrored, else the frame lateral axis. Y is up and
            Z points out of the eye. Left handed when mirrored.
        rig_matrix (list): Flat 4x4 right handed world matrix of the frame
            at the eye center, for joint drivers.
    """

    def __init__(self):
        self.mesh = None
        self.side = None
        self.mirrored = False
        self.frame = None
        self.eye_center = None
        self.eye_size = 1.0
        self.offset = 0.0
        self.aim_distance = 1.0
        self.loop = []
        self.in_vertex = None
        self.out_vertex = None
        self.upper = []
        self.lower = []
        self.upper_points = []
        self.lower_points = []
        self.control_matrix = None
        self.rig_matrix = None


def _single_vertex(text, mesh, label):
    """Get the index of a one vertex component string."""
    vertex_mesh, kind, indices = meshNavigation.parse_component_string(text)
    if kind != "vertex" or len(indices) != 1:
        raise ValueError("Set the {} vertex".format(label))
    if vertex_mesh.split("|")[-1] != mesh.split("|")[-1]:
        raise ValueError(
            "The {} vertex is not on the eyelid mesh {}".format(label, mesh)
        )
    return indices[0]


def loop_string(settings):
    """Get the eyelid loop component string of the selected loop type.

    Args:
        settings (dict): Eyelid settings.

    Returns:
        str: The edge or vertex loop.
    """
    if eyelid_schema.LOOP_TYPES[settings["loopType"]] == "vertex":
        return settings["vertexLoop"]
    return settings["edgeLoop"]


def _world_up():
    if cmds.upAxis(query=True, axis=True) == "z":
        return (0.0, 0.0, 1.0)
    return (0.0, 1.0, 0.0)


def _world_front():
    if cmds.upAxis(query=True, axis=True) == "z":
        return (0.0, -1.0, 0.0)
    return (0.0, 0.0, 1.0)


def _inner_first(first, last, positions, by_front):
    """Tell if the first lateral extreme is the inner corner.

    The inner corner is nearer the mid-plane. When both are about as far
    (side facing eyes) and by_front is set, it is the one further forward.
    """
    first_x = abs(positions[first][0])
    last_x = abs(positions[last][0])
    width = math.dist(positions[first], positions[last]) or 1.0
    if by_front and abs(first_x - last_x) < width * 0.1:
        front = _world_front()
        return vector._dot(positions[first], front) >= vector._dot(
            positions[last], front
        )
    return first_x <= last_x


def solve(settings, eye_center=None, aim=None, side=None):
    """Solve the eyelid geometry from the settings.

    A Shifter component gives the eye center, aim point and side from its
    guide. The tool leaves them None: the eye center comes from the eyeball
    mesh, the frame from the loop and the side from the eye position.

    Args:
        settings (dict): Coerced eyelid settings, see
            :mod:`mgear.core.facial.eyelid_schema`.
        eye_center (tuple, optional): Eye center, instead of the eyeball
            bounding box center.
        aim (tuple, optional): Point in front of the eye. The eye frame
            faces it, and the control offset is its depth in front of the
            eyelid loop. sideRange and the eyeball mesh are then not needed.
        side (str, optional): "L", "R" or "C", instead of detecting it.

    Returns:
        EyelidGeometry: The solved geometry.

    Raises:
        ValueError: If the settings don't describe a valid eye.
    """
    loop_type = eyelid_schema.LOOP_TYPES[settings["loopType"]]
    mesh, kind, indices = meshNavigation.parse_component_string(loop_string(settings))
    if not indices:
        raise ValueError("Set the eyelid {} loop".format(loop_type))
    if not cmds.objExists(mesh):
        raise ValueError("The eyelid mesh {} doesn't exist".format(mesh))
    eye_mesh = settings.get("eyeMesh")
    if eye_center is None and (not eye_mesh or not cmds.objExists(eye_mesh)):
        raise ValueError("Set an existing eyeball mesh")

    ordered, closed = meshNavigation.get_ordered_loop(mesh, indices, kind)
    if not closed:
        raise ValueError("The eyelid loop must be a closed loop")
    points = meshNavigation.get_vertex_world_positions(mesh, ordered)
    positions = dict(zip(ordered, points))
    count = float(len(points))
    loop_center = tuple(sum(p[i] for p in points) / count for i in range(3))

    if eye_center is None:
        bbox = cmds.exactWorldBoundingBox(eye_mesh)
        eye_center = tuple((bbox[i] + bbox[i + 3]) * 0.5 for i in range(3))
        eye_size = sum(bbox[i + 3] - bbox[i] for i in range(3)) / 3.0
    else:
        eye_center = tuple(eye_center)
        # eyeball about as wide as the eyelid opening
        eye_size = 2.0 * max(math.dist(p, loop_center) for p in points)

    offset = settings.get("offset", 0.0)
    aim_distance = eye_size / 1.7
    if aim is not None:
        direction = tuple(aim[i] - eye_center[i] for i in range(3))
        frame = vector.get_direction_frame(
            loop_center, direction, vector._cross(_world_up(), direction)
        )
        offset = max(
            vector.to_frame_coordinates(aim, frame)[2],
            0.0,
        )
        aim_distance = math.dist(eye_center, aim)
    else:
        normal_hint = tuple(loop_center[i] - eye_center[i] for i in range(3))
        lateral_hint = (1.0, 0.0, 0.0)
        if settings["sideRange"]:
            z_up = cmds.upAxis(query=True, axis=True) == "z"
            lateral_hint = (0.0, 1.0, 0.0) if z_up else (0.0, 0.0, 1.0)
        frame = vector.get_loop_frame(points, normal_hint, lateral_hint)

    if settings["customCorner"]:
        in_vertex = _single_vertex(settings["intCorner"], mesh, "internal corner")
        out_vertex = _single_vertex(settings["extCorner"], mesh, "external corner")
        for vertex in (in_vertex, out_vertex):
            if vertex not in positions:
                raise ValueError(
                    "Corner vertex {} is not on the eyelid loop".format(vertex)
                )
    else:
        extremes = vector.extremes_in_frame(points, frame)
        first = ordered[extremes["lateral_min"]]
        last = ordered[extremes["lateral_max"]]
        if aim is None and settings["sideRange"]:
            # front corner is the inner one
            in_vertex, out_vertex = last, first
        elif _inner_first(first, last, positions, aim is not None):
            in_vertex, out_vertex = first, last
        else:
            in_vertex, out_vertex = last, first

    path, other = meshNavigation.split_loop_at_vertices(
        ordered, True, in_vertex, out_vertex
    )

    def height(path_vertices):
        inner = path_vertices[1:-1] or path_vertices
        return sum(
            vector.to_frame_coordinates(positions[v], frame)[1] for v in inner
        ) / len(inner)

    upper, lower = (path, other) if height(path) >= height(other) else (other, path)

    geometry = EyelidGeometry()
    geometry.mesh = mesh
    geometry.side = side or vector.detect_side(eye_center[0])
    geometry.mirrored = geometry.side == "R" and settings["mirrorBehavior"]
    geometry.frame = frame
    geometry.eye_center = eye_center
    geometry.eye_size = eye_size
    geometry.offset = offset
    geometry.aim_distance = aim_distance
    geometry.loop = ordered
    geometry.in_vertex = in_vertex
    geometry.out_vertex = out_vertex
    geometry.upper = upper
    geometry.lower = lower
    geometry.upper_points = [positions[v] for v in upper]
    geometry.lower_points = [positions[v] for v in lower]

    lateral = frame["lateral"]
    if geometry.mirrored:
        x_axis = tuple(-value for value in lateral)
    else:
        x_axis = lateral
    geometry.control_matrix = vector.axes_matrix(
        x_axis, frame["up"], frame["normal"], eye_center
    )
    geometry.rig_matrix = vector.axes_matrix(
        lateral, frame["up"], frame["normal"], eye_center
    )
    return geometry
