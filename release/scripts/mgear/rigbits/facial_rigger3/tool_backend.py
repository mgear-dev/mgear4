"""Facial rigger tool backend: builds the facial rigs as standalone rigs.

Keeps the Eye Rigger 2.1 conventions: ``<prefix>_<side><index>_<name>``
names, controls and deform joints in object sets, joints under the head
joint and an optional rig parent and static rig parent.
"""

import mgear.pymaya as pm

from mgear.core import attribute
from mgear.core import curve
from mgear.core import icon
from mgear.core import node
from mgear.core import primitive
from mgear.core import string
from mgear.core.facial.backend import BaseBackend

from mgear import rigbits

COLORS = {"main": 4, "secondary": 14}


def get_or_create_set(name):
    """Get an object set, creating it when missing.

    Args:
        name (str): Set name.

    Returns:
        PyNode: The set.
    """
    if not pm.objExists(name):
        pm.sets(name=name, empty=True)
    return pm.PyNode(name)


def node_name(prefix, side, name, idx=None):
    """Get the name of a facial rigger node: ``<prefix>_<side><idx>_<name>``.

    Args:
        prefix (str): Name prefix, invalid characters are removed.
        side (str): Side.
        name (str): Short name.
        idx (int, optional): Index of the node.

    Returns:
        str: The node name.
    """
    side = side if idx is None else "{}{}".format(side, idx)
    return "_".join([string.removeInvalidCharacter(prefix), side, name])


def root_name(prefix, side):
    """Get the root name of a rig.

    Args:
        prefix (str): Name prefix.
        side (str): Side.

    Returns:
        str: The root name.
    """
    return node_name(prefix, side, "root")


class ToolBackend(BaseBackend):
    """Backend of the facial rigger tools.

    Args:
        prefix (str): Name prefix.
        side (str): "L", "R" or "C".
        ctl_name (str, optional): Control name suffix. Controls are left out
            of the controls set when it is "<name>_ghost".
        ctl_set (str, optional): Controls set, created if missing.
        def_set (str, optional): Deformers set, created if missing.
        head_joint (str, optional): Parent of the deform joints and base
            influence of the autoskin.
        parent_node (str, optional): Parent of the rig root.
        static_parent (str, optional): Static rig parent of the joints root,
            used when there is no head joint.
    """

    def __init__(
        self,
        prefix,
        side,
        ctl_name="ctl",
        ctl_set="rig_controllers_grp",
        def_set="rig_deformers_grp",
        head_joint=None,
        parent_node=None,
        static_parent=None,
    ):
        self.prefix = string.removeInvalidCharacter(prefix)
        self.side = side
        self.ctl_name = ctl_name or "ctl"
        self.ghost = self.ctl_name.split("_")[-1] == "ghost"
        self.ctl_set = get_or_create_set(ctl_set or "rig_controllers_grp")
        self.def_set = get_or_create_set(def_set or "rig_deformers_grp")
        self._head_joint = pm.PyNode(head_joint) if head_joint else None
        self.parent_node = parent_node
        self.static_parent = static_parent
        self._root = primitive.addTransform(None, self.name("root"))
        self._setup_root = primitive.addTransform(self._root, self.name("crvs"))
        self._setup_root.attr("visibility").set(False)
        self._joints_root = None

    @property
    def root(self):
        return self._root

    @property
    def setup_root(self):
        return self._setup_root

    def name(self, name, idx=None):
        return node_name(self.prefix, self.side, name, idx)

    def add_transform(self, parent, name, m, idx=None):
        return primitive.addTransform(parent, self.name(name, idx), m)

    def add_curve(self, parent, name, points):
        return curve.addCurve(parent, self.name(name), points)

    def add_ctl(
        self,
        parent,
        name,
        m,
        shape,
        role,
        keyable,
        w=1.0,
        d=None,
        ro=None,
        po=None,
        tag_parent=None,
    ):
        ctl = icon.create(
            parent,
            self.name("{}_{}".format(name, self.ctl_name)),
            m,
            icon=shape,
            color=COLORS[role],
            w=w,
            d=d if d is not None else w,
            ro=ro,
            po=po,
        )
        attribute.setKeyableAttributes(ctl, list(keyable))
        attribute.addAttribute(ctl, "isCtl", "bool", keyable=False)
        attribute.add_mirror_config_channels(ctl)
        node.add_controller_tag(ctl, tag_parent)
        if not self.ghost:
            self.ctl_set.add(ctl)
        return ctl

    def _joint_parent(self):
        if self._head_joint:
            return self._head_joint
        if self._joints_root is None:
            self._joints_root = primitive.addTransform(
                self._root, self.name("jnt_root")
            )
            if self.static_parent:
                pm.parentConstraint(self._root, self._joints_root, mo=True)
                pm.scaleConstraint(self._root, self._joints_root, mo=True)
                pm.PyNode(self.static_parent).addChild(self._joints_root)
        return self._joints_root

    def add_deform_joint(self, driver, name, idx=None):
        return rigbits.addJnt(
            driver,
            self._joint_parent(),
            grp=self.def_set,
            jntName=self.name(name, idx),
        )

    def deform_joint(self, handle):
        return handle.name()

    def head_joint(self):
        return self._head_joint.name() if self._head_joint else None

    def finalize(self):
        if self.parent_node:
            pm.PyNode(self.parent_node).addChild(self._root)
