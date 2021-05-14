"""Component Squash 01 module"""

import pymel.core as pm
import pymel.core.datatypes as dt

from mgear.shifter import component

from mgear.core import primitive, transform, applyop, attribute, node, vector

##########################################################
# COMPONENT
##########################################################


class Component(component.Main):
    """Shifter component Class"""

    # =====================================================
    # OBJECTS
    # =====================================================
    def addObjects(self):
        """Add all the objects needed to create the component."""

        self.normal = self.guide.blades["blade"].z * -1
        self.binormal = self.guide.blades["blade"].x

        t = transform.getTransformLookingAt(self.guide.apos[0],
                                            self.guide.apos[1],
                                            self.normal,
                                            axis="yx",
                                            negate=self.negate)
        self.ctl_npo = primitive.addTransform(self.root,
                                              self.getName("ctl_npo"), t)
        self.ctl = self.addCtl(self.ctl_npo,
                               "base_ctl",
                               t,
                               self.color_ik,
                               "square",
                               w=1.0,
                               tp=self.parentCtlTag)

        self.ref_base = primitive.addTransform(self.ctl,
                                               self.getName("ref_base"),
                                               t)

        t = transform.setMatrixPosition(t, self.guide.apos[1])

        self.ik_cns = primitive.addTransform(self.ctl,
                                             self.getName("ik_cns"),
                                             t)
        self.squash_npo = primitive.addTransform(self.ik_cns,
                                                 self.getName("squash_npo"),
                                                 t)
        self.squash_ctl = self.addCtl(self.squash_npo,
                                      "squash_ctl",
                                      t,
                                      self.color_ik,
                                      "crossarrow",
                                      w=1.0,
                                      ro=dt.Vector(1.5708, 0, 0),
                                      tp=self.ctl)

        attribute.setKeyableAttributes(self.squash_ctl, ["tx", "ty", "tz"])

        self.ref_squash = primitive.addTransform(self.squash_ctl,
                                                 self.getName("ref_squash"),
                                                 t)

        self.div_cns = []

        div_cns = primitive.addTransform(self.root, self.getName("div0_loc"))

        self.div_cns.append(div_cns)
        self.jnt_pos.append([div_cns, 0, None, False])

    # =====================================================
    # ATTRIBUTES
    # =====================================================
    def addAttributes(self):
        """Create the anim and setupr rig attributes for the component"""

        # Ref
        if self.settings["ikrefarray"]:
            ref_names = self.settings["ikrefarray"].split(",")
            if len(ref_names) > 1:
                self.ikref_att = self.addAnimEnumParam(
                    "ikref",
                    "Ik Ref",
                    0,
                    self.settings["ikrefarray"].split(","))

    # =====================================================
    # OPERATORS
    # =====================================================
    def addOperators(self):
        """Create operators and set the relations for the component rig

        Apply operators/Solvers, constraints, expressions to the hierarchy.
        In order to keep the code clean and easier to debug,
        we shouldn't create any new object in this method.

        """
        applyop.aimCns(self.ref_base,
                       self.squash_ctl,
                       axis="yx",
                       wupType=2,
                       wupVector=[1, 0, 0],
                       wupObject=self.ctl,
                       maintainOffset=False)
        applyop.aimCns(self.ref_squash,
                       self.ctl,
                       axis="-yx",
                       wupType=2,
                       wupVector=[1, 0, 0],
                       wupObject=self.squash_ctl,
                       maintainOffset=False)
        bIncrement = 1.0
        blend = 0
        for i, div_cns in enumerate(self.div_cns):
            intMatrix = applyop.gear_intmatrix_op(
                self.ref_base.attr("worldMatrix"),
                self.ref_squash.attr("worldMatrix"),
                blend)

            applyop.gear_mulmatrix_op(intMatrix.attr("output"),
                                      div_cns.attr("parentInverseMatrix[0]"),
                                      div_cns)

            blend = blend + bIncrement

        d = vector.getDistance(self.guide.apos[0], self.guide.apos[1])
        dist_node = node.createDistNode(self.squash_ctl, self.ctl)

        rootWorld_node = node.createDecomposeMatrixNode(
            self.ctl.attr("worldMatrix"))

        div_node = node.createDivNode(dist_node + ".distance",
                                      rootWorld_node + ".outputScaleY")

        div_node = node.createDivNode(div_node + ".outputX", d)
        rev_node = node.createReverseNode(div_node + ".outputX")
        add_node = pm.createNode("plusMinusAverage")

        add_node.input1D[0].set(1.0)
        rev_node.outputX >> add_node.input1D[1]

        div_node.outputX >> self.ref_base.scaleY
        add_node.output1D >> self.ref_base.scaleX
        add_node.output1D >> self.ref_base.scaleZ

    # =====================================================
    # CONNECTOR
    # =====================================================
    def setRelation(self):
        """Set the relation beetween object from guide to rig"""
        self.relatives["root"] = self.ref_base
        self.relatives["squash"] = self.ref_squash

        self.controlRelatives["root"] = self.ctl
        self.controlRelatives["squash"] = self.squash_ctl

        for i in range(0, len(self.div_cns) - 1):
            self.relatives["%s_loc" % i] = self.div_cns[i + 1]
            self.jointRelatives["%s_loc" % i] = i + 1
        self.relatives["%s_loc" % (len(self.div_cns) - 1)] = self.div_cns[-1]
        jnt_rel_len = len(self.div_cns) - 1
        self.jointRelatives["%s_loc" % (len(self.div_cns) - 1)] = jnt_rel_len

    def connect_standard(self):
        """standard connection definition for the component"""
        self.connect_standardWithSimpleIkRef()
