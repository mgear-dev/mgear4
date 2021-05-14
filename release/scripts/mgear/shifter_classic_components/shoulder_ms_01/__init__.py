"""Component Shoulder MS 01 module"""

import pymel.core as pm
from pymel.core import datatypes

from mgear.shifter import component

from mgear.core import applyop, vector
from mgear.core import attribute, transform, primitive

#############################################
# COMPONENT
#############################################


class Component(component.Main):
    """Shifter component Class"""

    # =====================================================
    # OBJECTS
    # =====================================================
    def addObjects(self):
        """Add all the objects needed to create the component."""

        self.normal = self.guide.blades["blade"].z * -1
        self.binormal = self.guide.blades["blade"].x

        self.length0 = vector.getDistance(self.guide.apos[0],
                                          self.guide.apos[1])

        t = transform.getTransformLookingAt(self.guide.apos[0],
                                            self.guide.apos[1],
                                            self.normal,
                                            axis="xy",
                                            negate=self.negate)

        self.npo = primitive.addTransform(self.root, self.getName("npo"), t)

        self.ctl = self.addCtl(
            self.npo,
            "ctl",
            t,
            self.color_fk,
            "cube",
            w=self.length0,
            h=self.size * .1,
            d=self.size * .1,
            po=datatypes.Vector(.5 * self.length0 * self.n_factor, 0, 0),
            tp=self.parentCtlTag)

        self.mtx = primitive.addTransform(self.npo, self.getName("mtx"), t)

        t1 = transform.setMatrixPosition(t, self.guide.apos[1])
        t2 = transform.getInterpolateTransformMatrix(t, t1, blend=0.98)
        self.loc = primitive.addTransform(self.mtx, self.getName("loc"), t2)

        self.end = primitive.addTransform(self.ctl, self.getName("end"), t1)

        self.jnt_pos.append([self.mtx, "root"])
        self.jnt_pos.append([self.loc, 'end'])

        attribute.setKeyableAttributes(self.ctl)
        attribute.setInvertMirror(self.ctl, ["tx", "ty", "tz"])

    # =====================================================
    # ATTRIBUTES
    # =====================================================
    def addAttributes(self):
        """Create the anim and setupr rig attributes for the component"""
        return

    # =====================================================
    # OPERATORS
    # =====================================================
    def addOperators(self):
        """Create operators and set the relations for the component rig

        Apply operators, constraints, expressions to the hierarchy.
        In order to keep the code clean and easier to debug,
        we shouldn't create any new object in this method.

        """
        if self.negate:
            o_node = applyop.aimCns(self.mtx,
                                    self.end,
                                    axis="-xy",
                                    wupType=4,
                                    wupVector=[0, 1, 0],
                                    wupObject=self.mtx,
                                    maintainOffset=False)
        else:
            o_node = applyop.aimCns(self.mtx,
                                    self.end,
                                    axis="xy",
                                    wupType=4,
                                    wupVector=[0, 1, 0],
                                    wupObject=self.mtx,
                                    maintainOffset=False)

        # position constrint loc to ref
        o_node = applyop.gear_mulmatrix_op(
            self.end.attr("worldMatrix"), self.loc.attr("parentInverseMatrix"))
        dm_node = pm.createNode("decomposeMatrix")
        pm.connectAttr(o_node + ".output", dm_node + ".inputMatrix")
        pb_node = pm.createNode("pairBlend")
        # move back a little bit to avoid overlapping with limb jts
        pm.setAttr(pb_node + ".weight", 0.98)
        pm.connectAttr(dm_node + ".outputTranslate", pb_node + ".inTranslate2")
        pm.connectAttr(pb_node + ".outTranslate", self.loc.attr("translate"))

    # =====================================================
    # CONNECTOR
    # =====================================================
    def setRelation(self):
        """Set the relation beetween object from guide to rig"""
        self.relatives["root"] = self.root
        self.relatives["tip"] = self.loc

        self.controlRelatives["root"] = self.ctl
        self.controlRelatives["tip"] = self.ctl

        self.jointRelatives["root"] = 0
        self.jointRelatives["tip"] = 1

    def connect_standard(self):
        self.parent.addChild(self.root)
