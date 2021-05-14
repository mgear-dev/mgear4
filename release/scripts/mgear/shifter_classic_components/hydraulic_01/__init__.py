"""Component Hydraulic 01 module"""

from mgear.shifter import component
from mgear.core import attribute, transform, primitive, applyop


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

        self.ctl_npo = primitive.addTransform(
            self.root, self.getName("ctl_npo"), t)
        self.ctl = self.addCtl(self.ctl_npo,
                               "base_ctl",
                               t,
                               self.color_ik,
                               "square",
                               w=1.0,
                               tp=self.parentCtlTag)
        attribute.setKeyableAttributes(self.ctl, self.tr_params)

        self.ref_base = primitive.addTransform(
            self.ctl, self.getName("ref_base"), t)

        t = transform.setMatrixPosition(t, self.guide.apos[1])
        self.ik_cns = primitive.addTransform(
            self.root, self.getName("ik_cns"), t)
        self.tip_npo = primitive.addTransform(
            self.ik_cns, self.getName("tip_npo"), t)

        self.tip_ctl = self.addCtl(self.tip_npo,
                                   "tip_ctl",
                                   t,
                                   self.color_ik,
                                   "square",
                                   w=1.0,
                                   tp=self.ctl)

        attribute.setKeyableAttributes(self.tip_ctl, self.tr_params)

        self.ref_tip = primitive.addTransform(
            self.tip_ctl, self.getName("ref_tip"), t)

        self.div_cns = []

        for i in range(self.settings["div"]):

            div_cns = primitive.addTransform(self.root,
                                             self.getName("div%s_loc" % i))

            self.div_cns.append(div_cns)
            self.jnt_pos.append([div_cns, i])

    # =====================================================
    # ATTRIBUTES
    # =====================================================
    def addAttributes(self):
        """Create the anim and setupr rig attributes for the component"""

        # Ref
        if self.settings["ikrefarray"]:
            ref_names = self.get_valid_alias_list(
                self.settings["ikrefarray"].split(","))
            if len(ref_names) > 1:
                self.ikref_att = self.addAnimEnumParam(
                    "ikref",
                    "Ik Ref",
                    0,
                    ref_names)

    # =====================================================
    # OPERATORS
    # =====================================================
    def addOperators(self):
        """Create operators and set the relations for the component rig

        Apply operators, constraints, expressions to the hierarchy.
        In order to keep the code clean and easier to debug,
        we shouldn't create any new object in this method.

        """
        applyop.aimCns(self.ref_base,
                       self.tip_ctl,
                       axis="yx",
                       wupType=2,
                       wupVector=[1, 0, 0],
                       wupObject=self.ctl,
                       maintainOffset=False)
        applyop.aimCns(self.ref_tip,
                       self.ctl,
                       axis="-yx",
                       wupType=2,
                       wupVector=[1, 0, 0],
                       wupObject=self.tip_ctl,
                       maintainOffset=False)

        bIncrement = 1.0 / (self.settings["div"] - 1)
        blend = 0
        for i, div_cns in enumerate(self.div_cns):
            intMatrix = applyop.gear_intmatrix_op(
                self.ref_base.attr("worldMatrix"),
                self.ref_tip.attr("worldMatrix"),
                blend)

            applyop.gear_mulmatrix_op(intMatrix.attr("output"),
                                      div_cns.attr("parentInverseMatrix[0]"),
                                      div_cns)

            blend = blend + bIncrement

    # =====================================================
    # CONNECTOR
    # =====================================================
    def setRelation(self):
        """Set the relation beetween object from guide to rig"""
        self.relatives["root"] = self.ref_base
        self.relatives["tip"] = self.ref_tip

        self.controlRelatives["root"] = self.ctl
        self.controlRelatives["tip"] = self.tip_ctl

        for i in range(0, len(self.div_cns) - 1):
            self.relatives["%s_loc" % i] = self.div_cns[i + 1]
            self.jointRelatives["%s_loc" % i] = i + 1

        self.relatives["%s_loc" % (len(self.div_cns) - 1)] = self.div_cns[-1]

        dlen = len(self.div_cns) - 1
        self.jointRelatives["%s_loc" % (len(self.div_cns) - 1)] = dlen

    def connect_standard(self):
        """standard connection definition for the component"""
        self.connect_standardWithSimpleIkRef()
