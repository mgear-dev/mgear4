"""Shifter backend of the facial rig builders.

Builds the :mod:`mgear.core.facial` rigs inside a Shifter component: Shifter
names, controls, colors and joints. Joints are registered in the component
``jnt_pos`` and created in the component joint step.
"""

from maya import cmds

from mgear.pymaya import datatypes

from mgear.core import attribute
from mgear.core import curve
from mgear.core import primitive
from mgear.core.facial.backend import BaseBackend

NO_MIRROR = (0, 0, 0, 0, 0, 0, 0, 0, 0)


class ComponentBackend(BaseBackend):
    """Backend building a facial rig in a Shifter component.

    Args:
        component (shifter.component.Main): The component being built.
    """

    def __init__(self, component):
        self.component = component
        self._setup_root = None

    @property
    def root(self):
        return self.component.root

    @property
    def setup_root(self):
        if self._setup_root is None:
            self._setup_root = primitive.addTransform(
                self.component.root, self.name("setup"), datatypes.Matrix()
            )
            self._setup_root.attr("visibility").set(False)
        return self._setup_root

    def name(self, name, idx=None):
        if idx is not None:
            name = "{}{}".format(name, idx)
        return self.component.getName(name)

    def add_transform(self, parent, name, m, idx=None):
        return primitive.addTransform(parent, self.name(name, idx), m)

    def add_curve(self, parent, name, points, edit_points=False):
        return curve.addCurve(parent, self.name(name), points, op=edit_points)

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
        mirror_conf=None,
    ):
        comp = self.component
        color = comp.color_ik if role == "main" else comp.color_fk
        ctl = comp.addCtl(
            parent,
            name,
            m,
            color,
            shape,
            tp=tag_parent or comp.parentCtlTag,
            mirrorConf=list(mirror_conf or NO_MIRROR),
            w=w * comp.size,
            d=(d if d is not None else w) * comp.size,
            ro=ro,
            po=po,
        )
        attribute.setKeyableAttributes(ctl, list(keyable))
        return ctl

    def add_deform_joint(self, driver, name, idx=None, parent=None):
        # Shifter parents every component joint the same way: parent is
        # ignored. The Shifter joint rule adds its own extension
        if name.endswith("_jnt"):
            name = name[: -len("_jnt")]
        entry = {
            "obj": driver,
            "name": name if idx is None else "{}{}".format(name, idx),
        }
        # without joints Shifter makes them under the drivers
        if self.component.options["joint_rig"]:
            entry["newActiveJnt"] = "parent_relative_jnt"
        self.component.jnt_pos.append(entry)
        return len(self.component.jnt_pos) - 1

    def deform_joint(self, handle):
        joints = self.component.jointList
        return joints[handle].name() if handle < len(joints) else None

    def head_joint(self):
        if not self.component.options["joint_rig"]:
            return None
        parent = self.component.parent_relative_jnt.name()
        # without a parent component joint it is the rig joints group
        if cmds.nodeType(parent) != "joint":
            return None
        return parent

    def finalize(self):
        return None
