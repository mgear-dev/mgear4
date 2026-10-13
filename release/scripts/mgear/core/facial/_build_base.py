"""Shared base of the facial rig builders.

Helpers every facial builder uses: utility nodes named with the rig naming,
smooth remaps, control matrices and the choice of the curve points that get
a joint.
"""

from maya import cmds

import mgear.pymaya as pm
from mgear.pymaya import datatypes

from mgear.core import transform

MAIN_KEYABLE = ("tx", "ty", "tz", "ro", "rx", "ry", "rz", "sx", "sy", "sz")
SECONDARY_KEYABLE = ("tx", "ty", "tz")


def select_joint_indices(
    count, every_n=1, fixed=False, fixed_number=3, skip_ends=False
):
    """Choose the curve points that get a joint.

    Args:
        count (int): Number of curve points (loop vertices).
        every_n (int, optional): One joint every N points.
        fixed (bool, optional): Use fixed_number evenly spread joints
            instead, including both ends.
        fixed_number (int, optional): Number of fixed joints.
        skip_ends (bool, optional): Skip the first and last points, which
            the curve shares with another one (lower lid or lower lip).

    Returns:
        list: (point index, joint index) pairs. The joint index is the point
            index, or a running number for fixed joints.
    """
    last = count - 1
    ends = (0, last) if skip_ends else ()
    if fixed:
        number = max(2, min(fixed_number, count))
        points = sorted(
            set(int(round(k * last / float(number - 1))) for k in range(number))
        )
        points = [i for i in points if i not in ends]
        return [(point, j) for j, point in enumerate(points)]
    return [(i, i) for i in range(0, count, max(1, every_n)) if i not in ends]


def xyz(point):
    """Get the x, y, z tuple of a point or vector."""
    return (point[0], point[1], point[2])


def curve_points(crv):
    """Get the world positions of the CVs of a curve."""
    return [xyz(p) for p in pm.PyNode(crv).getCVs(space="world")]


def mid_point(crv):
    """Get the world point at half the length of a curve."""
    crv = pm.PyNode(crv)
    param = crv.findParamFromLength(crv.length() * 0.5)
    return xyz(crv.getPointAtParam(param, space="world"))


class FacialBuilder(object):
    """Base of the facial rig builders.

    Args:
        settings (dict): Coerced rig settings.
        geometry (object): Solved geometry, with a ``control_matrix``.
        backend (BaseBackend): Backend creating the nodes.
    """

    def __init__(self, settings, geometry, backend):
        self.settings = settings
        self.geometry = geometry
        self.backend = backend

    def _create_node(self, node_type, name, idx=None):
        """Create a utility node with the rig naming."""
        return pm.PyNode(cmds.createNode(node_type, name=self.backend.name(name, idx)))

    def _smooth_remap(
        self,
        name,
        input_attr,
        input_min=0.0,
        input_max=1.0,
        outputs=(0.0, 1.0),
        idx=None,
    ):
        """Create a remapValue easing its input in and out.

        Read ``outValue``: the smooth interpolation is on the value ramp.

        Args:
            name (str): Short node name.
            input_attr (Attribute): Input plug.
            input_min (float, optional): Input start.
            input_max (float, optional): Input end.
            outputs (tuple, optional): Output at the input start and end.
            idx (int, optional): Index of the node.

        Returns:
            PyNode: The remapValue node.
        """
        remap = self._create_node("remapValue", name, idx)
        pm.connectAttr(input_attr, remap.attr("inputValue"))
        remap.attr("value[0].value_Interp").set(2)
        remap.attr("inputMin").set(input_min)
        remap.attr("inputMax").set(input_max)
        remap.attr("outputMin").set(outputs[0])
        remap.attr("outputMax").set(outputs[1])
        return remap

    def _name_node(self, utility, name, idx=None):
        """Rename a utility node made by a :mod:`mgear.core.node` helper."""
        return pm.PyNode(utility).rename(self.backend.name(name, idx))

    def _control_matrix(self, position, matrix=None):
        """Get a control space matrix at a position.

        Args:
            position (tuple): World position.
            matrix (list, optional): Flat 4x4 control space. Defaults to the
                geometry ``control_matrix``.

        Returns:
            Matrix: The matrix.
        """
        if matrix is None:
            matrix = self.geometry.control_matrix
        return transform.setMatrixPosition(
            datatypes.Matrix(matrix), datatypes.Vector(*position)
        )
