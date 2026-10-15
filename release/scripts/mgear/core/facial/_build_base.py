"""Shared base of the facial rig builders.

Helpers every facial builder uses: utility nodes named with the rig naming,
smooth remaps, control matrices and the choice of the curve points that get
a joint.
"""

from maya import cmds

import mgear.pymaya as pm
from mgear.pymaya import datatypes

from mgear.core import applyop
from mgear.core import skin
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


def uniform_curve(crv, count):
    """Rebuild a cubic curve with count CVs and uniform 0 to 1 knots.

    Curves rebuilt with the same count share their knots, so they average
    and blend CV by CV.

    Args:
        crv (str or dagNode): Curve.
        count (int): CVs, at least 4.
    """
    cmds.rebuildCurve(
        str(crv),
        rebuildType=0,
        spans=count - 3,
        degree=3,
        keepRange=0,
        keepEndPoints=True,
        replaceOriginal=True,
        constructionHistory=False,
    )


def cv_points(crv):
    """Get the world positions of the CVs of a curve."""
    return [xyz(p) for p in pm.PyNode(crv).getCVs(space="world")]


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
        self._root_scale = None

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

    def _world_drivers_root(self, name="ropeDrivers"):
        """Create the group of the joint drivers placed by motion paths.

        Motion paths give world positions: the group doesn't inherit
        transforms, and the drivers take the rig scale from the root.

        Args:
            name (str, optional): Short group name.

        Returns:
            tuple: (group, decomposeMatrix of the root world matrix)
        """
        b = self.backend
        group = b.add_transform(b.root, name, datatypes.Matrix())
        cmds.setAttr(str(group) + ".inheritsTransform", False)
        # without inheritance its local offset under the root would be world
        cmds.xform(
            str(group), translation=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)
        )
        return group, self._root_scale_node()

    def _fixed_orientation(self, name, matrix):
        """Create a transform giving translate only joint drivers their rotation.

        Args:
            name (str): Short transform name.
            matrix (Matrix): Its world matrix, the joints rest orientation.

        Returns:
            tuple: (transform, decomposeMatrix of its world matrix)
        """
        b = self.backend
        orient = b.add_transform(b.root, name, matrix)
        decompose = self._create_node("decomposeMatrix", name + "_decomp")
        pm.connectAttr(orient.attr("worldMatrix[0]"), decompose.attr("inputMatrix"))
        return orient, decompose

    def _add_path_driver(self, prefix, idx, rope, upv_rope, u, orientation=None):
        """Create a joint driver sliding on a rope curve.

        The driver aims X along the rope, with Y to an up vector sliding on
        the up vector rope. With an orientation it only slides, and takes
        the orientation rotation instead. It takes the rig scale.

        Args:
            prefix (str): Name prefix of the driver nodes.
            idx (int): Index of the driver nodes.
            rope (dagNode): Curve the driver slides on.
            upv_rope (dagNode): Curve the up vector slides on.
            u (float): Length ratio on the curves.
            orientation (PyNode, optional): decomposeMatrix giving the
                rotation of a translate only driver.

        Returns:
            dagNode: The driver, under the drivers root.
        """
        b = self.backend
        rig_m = datatypes.Matrix(self.geometry.rig_matrix)
        follow = orientation is None
        driver = b.add_transform(self.drivers_root, prefix + "Drv", rig_m, idx=idx)
        path = applyop.pathCns(driver, rope, u=u, tangent=follow)
        self._name_node(path, prefix + "_motionPath", idx)
        if follow:
            upv = b.add_transform(self.drivers_root, prefix + "Upv", rig_m, idx=idx)
            upv_path = applyop.pathCns(upv, upv_rope, u=u)
            self._name_node(upv_path, prefix + "Upv_motionPath", idx)
            # X along the rope, Y to the up vector
            path.attr("worldUpType").set(1)
            path.attr("frontAxis").set(0)
            path.attr("upAxis").set(1)
            pm.connectAttr(upv.attr("worldMatrix[0]"), path.attr("worldUpMatrix"))
        else:
            pm.connectAttr(
                orientation.attr("outputRotate"), driver.attr("rotate"), force=True
            )
        pm.connectAttr(
            self._root_scale_node().attr("outputScale"), driver.attr("scale")
        )
        return driver

    def _root_scale_node(self):
        """Get the decomposeMatrix of the rig root world matrix, created once.

        Returns:
            PyNode: The decomposeMatrix node.
        """
        if self._root_scale is None:
            b = self.backend
            self._root_scale = self._create_node("decomposeMatrix", "rootScale_decomp")
            pm.connectAttr(
                b.root.attr("worldMatrix[0]"), self._root_scale.attr("inputMatrix")
            )
        return self._root_scale

    def _autoskin(self, joint_seeds, loop_vertices, label):
        """Skin the mesh with the topological autoskin, when doSkin is on.

        The joint weights blend with the strongest existing influence of
        each vertex. A mesh without skin cluster is skinned to the head
        joint first.

        Args:
            joint_seeds (list): (joint handle, seed vertex) pairs.
            loop_vertices (list): All the vertices of the rigged path.
            label (str): Rig name for the warning, e.g. "Lips".

        Returns:
            str: The skin cluster, or None when skipped.
        """
        s = self.settings
        if not s["doSkin"]:
            return None
        mesh = self.geometry.mesh
        head = None
        if not skin.getSkinCluster(mesh):
            head = self.backend.head_joint()
            if not head:
                pm.displayWarning(
                    "{} autoskin skipped: the mesh has no skin cluster, set "
                    "the head joint to skin against".format(label)
                )
                return None
        seeds = [
            (self.backend.deform_joint(handle), vertex)
            for handle, vertex in joint_seeds
        ]
        return skin.apply_topological_autoskin(
            mesh,
            seeds,
            base_influence=head,
            rigid_loops=s["rigidLoops"],
            falloff_loops=s["falloffLoops"],
            loop_vertices=loop_vertices,
            smooth_iterations=s["skinSmooth"],
        )
