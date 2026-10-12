"""Eyelid geometry solver: reads the eye and eyelid loop, creates nothing.

The solver orders the eyelid loop, finds its corners and splits it into the
upper and lower lid, in a frame local to the loop. It replaces the world
axes and scene up axis checks of Eye Rigger 2.1, so tilted and side facing
eyes work the same.
"""

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
        eye_size (float): Mean bounding box size of the eyeball.
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


def solve(settings):
    """Solve the eyelid geometry from the settings.

    Args:
        settings (dict): Coerced eyelid settings, see
            :mod:`mgear.core.facial.eyelid_schema`.

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
    eye_mesh = settings["eyeMesh"]
    if not eye_mesh or not cmds.objExists(eye_mesh):
        raise ValueError("Set an existing eyeball mesh")

    ordered, closed = meshNavigation.get_ordered_loop(mesh, indices, kind)
    if not closed:
        raise ValueError("The eyelid loop must be a closed loop")
    points = meshNavigation.get_vertex_world_positions(mesh, ordered)
    positions = dict(zip(ordered, points))

    bbox = cmds.exactWorldBoundingBox(eye_mesh)
    eye_center = tuple((bbox[i] + bbox[i + 3]) * 0.5 for i in range(3))
    eye_size = sum(bbox[i + 3] - bbox[i] for i in range(3)) / 3.0

    count = float(len(points))
    loop_center = tuple(sum(p[i] for p in points) / count for i in range(3))
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
        if settings["sideRange"]:
            # front corner is the inner one
            in_vertex, out_vertex = last, first
        elif abs(positions[last][0]) < abs(positions[first][0]):
            in_vertex, out_vertex = last, first
        else:
            in_vertex, out_vertex = first, last

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
    geometry.side = vector.detect_side(eye_center[0])
    geometry.mirrored = geometry.side == "R" and settings["mirrorBehavior"]
    geometry.frame = frame
    geometry.eye_center = eye_center
    geometry.eye_size = eye_size
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
