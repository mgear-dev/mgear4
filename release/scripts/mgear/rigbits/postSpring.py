"""Post Spring tool

creates a spring dynamic rig on top of a pre-existing FK chain rig.
"""

import pymel.core as pm

from mgear.core import applyop, attribute


def postSpring(dist=5, hostUI=False, hostUI2=False, invertX=False):
    """Create the dynamic spring rig.

    This spring system use the mgear_spring node
    And transfer the position spring
    to rotation spring using an aim constraint.

    Note:
        The selected chain of object should be align with the X axis.

    Args:
        dist (float): The distance of the position spring.
        hostUI (dagNode): The spring active and intensity channel host.
        hostUI2 (dagNode): The daping and stiffness channel host for each
            object in the chain.
        invertX (bool): reverse the direction of the x axis.

    """
    oSel = pm.selected()

    if not hostUI2:
        hostUI2 = oSel[0]

    aSpring_active = attribute.addAttribute(
        hostUI2,
        "spring_active_%s" % oSel[0].name(),
        "double",
        1.0,
        "___spring_active_______%s" % oSel[0].name(),
        "spring_active_%s" % oSel[0].name(),
        0,
        1)

    aSpring_intensity = attribute.addAttribute(
        hostUI2,
        "spring_intensity_%s" % oSel[0].name(),
        "double",
        1.0,
        "___spring_intensity_______%s" % oSel[0].name(),
        "spring_intensity_%s" % oSel[0].name(),
        0,
        1)

    if invertX:
        dist = dist * -1
        # aim constraint
        aimAxis = "-xy"
    else:
        # aim constraint
        aimAxis = "xy"

    for obj in oSel:

        oParent = obj.getParent()

        oNpo = pm.PyNode(pm.createNode("transform",
                                       n=obj.name() + "_npo",
                                       p=oParent,
                                       ss=True))
        oNpo.setTransformation(obj.getMatrix())
        pm.parent(obj, oNpo)

        oSpring_cns = pm.PyNode(pm.createNode("transform",
                                              n=obj.name() + "_spr_cns",
                                              p=oNpo,
                                              ss=True))
        oSpring_cns.setTransformation(obj.getMatrix())
        pm.parent(obj, oSpring_cns)

        oSpringLvl = pm.PyNode(pm.createNode("transform",
                                             n=obj.name() + "_spr_lvl",
                                             p=oNpo,
                                             ss=True))
        oM = obj.getTransformation()
        oM.addTranslation([dist, 0, 0], "object")
        oSpringLvl.setTransformation(oM.asMatrix())

        oSpringDriver = pm.PyNode(pm.createNode("transform",
                                                n=obj.name() + "_spr",
                                                p=oSpringLvl,
                                                ss=True))

        try:
            defSet = pm.PyNode("rig_PLOT_grp")
            pm.sets(defSet, add=oSpring_cns)
        except TypeError:
            defSet = pm.sets(name="rig_PLOT_grp")
            pm.sets(defSet, remove=obj)
            pm.sets(defSet, add=oSpring_cns)

        # adding attributes:
        if not hostUI:
            hostUI = obj

        aSpring_damping = attribute.addAttribute(
            hostUI,
            "spring_damping_%s" % obj.name(),
            "double",
            .5,
            "damping_%s" % obj.name(),
            "damping_%s" % obj.name(),
            0,
            1)

        aSpring_stiffness_ = attribute.addAttribute(
            hostUI,
            "spring_stiffness_%s" % obj.name(),
            "double",
            .5,
            "stiffness_%s" % obj.name(),
            "stiffness_%s" % obj.name(),
            0,
            1)

        cns = applyop.aimCns(oSpring_cns,
                             oSpringDriver,
                             aimAxis,
                             2,
                             [0, 1, 0],
                             oNpo,
                             False)

        # change from fcurves to spring
        pb_node = pm.createNode("pairBlend")

        pm.connectAttr(cns + ".constraintRotateX", pb_node + ".inRotateX2")
        pm.connectAttr(cns + ".constraintRotateY", pb_node + ".inRotateY2")
        pm.connectAttr(cns + ".constraintRotateZ", pb_node + ".inRotateZ2")
        pm.setAttr(pb_node + ".translateXMode", 2)
        pm.setAttr(pb_node + ".translateYMode", 2)
        pm.setAttr(pb_node + ".translateZMode", 2)

        pm.connectAttr(pb_node + ".outRotateX",
                       oSpring_cns + ".rotateX",
                       f=True)
        pm.connectAttr(pb_node + ".outRotateY",
                       oSpring_cns + ".rotateY",
                       f=True)
        pm.connectAttr(pb_node + ".outRotateZ",
                       oSpring_cns + ".rotateZ",
                       f=True)

        pm.setKeyframe(oSpring_cns, at="rotateX")
        pm.setKeyframe(oSpring_cns, at="rotateY")
        pm.setKeyframe(oSpring_cns, at="rotateZ")

        # add sprint op
        springOP = applyop.gear_spring_op(oSpringDriver)

        # connecting attributes
        pm.connectAttr(aSpring_active, pb_node + ".weight")
        pm.connectAttr(aSpring_intensity, springOP + ".intensity")
        pm.connectAttr(aSpring_damping, springOP + ".damping")
        pm.connectAttr(aSpring_stiffness_, springOP + ".stiffness")


def spring_UI(*args):
    """Creates the post tool UI"""

    if pm.window("mGear_spring_window", exists=True):
        pm.deleteUI("mGear_spring_window")

    window = pm.window("mGear_spring_window",
                       title="mGear post Spring",
                       w=350,
                       h=200,
                       mxb=False,
                       sizeable=False)

    pm.rowColumnLayout(numberOfColumns=2,
                       columnAttach=(1, 'right', 0),
                       columnWidth=[(1, 100), (2, 250)])

    pm.text("spring Distance: ")
    pm.floatField("distance",
                  annotation="distane in X local for the spring  position",
                  w=50,
                  value=5)
    pm.text(label="Invert X to -X: ")
    pm.checkBox("invertX", label=" Invert X direction to -X ")
    pm.text(label="UI Host: ")
    pm.textField("hostUI")

    pm.separator(h=10)
    pm.button(label="Spring Me bro!!", w=150, h=50, command=build_spring)
    pm.separator(h=10)

    pm.separator(h=10)
    pm.separator(h=10)
    pm.text(label="Instructions: Select controls in order from root to tip",
            align="left")
    pm.separator(h=10)
    pm.separator(h=10)
    pm.separator(h=10)
    pm.button(label="Baker", w=50, h=50, command=bake_spring)

    pm.showWindow(window)


def build_spring(*args):
    dist = pm.floatField("distance", q=True, v=True)
    hostName = pm.textField("hostUI", q=True, text=True)
    try:
        hostUI = pm.PyNode(hostName)
    except TypeError:
        hostUI = False
    invertX = pm.checkBox("invertX", q=True, v=True)

    postSpring(dist, hostUI, hostUI, invertX)


def bake_spring(*args):
    """Shortcut fro the Maya's Bake Simulation Options"""
    pm.BakeSimulationOptions()
