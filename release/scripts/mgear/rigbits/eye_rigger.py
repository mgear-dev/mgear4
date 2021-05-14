"""Rigbits eye rigger tool"""

import json
import traceback
from functools import partial

import mgear.core.pyqt as gqt
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from mgear.core import meshNavigation, curve, applyop, node, primitive, icon
from mgear.core import transform, utils, attribute, skin, string
from mgear.vendor.Qt import QtCore, QtWidgets
from pymel.core import datatypes

from mgear import rigbits


##########################################################
# Eye rig constructor
##########################################################


def eyeRig(eyeMesh,
           edgeLoop,
           blinkH,
           namePrefix,
           offset,
           rigidLoops,
           falloffLoops,
           headJnt,
           doSkin,
           parent=None,
           ctlName="ctl",
           sideRange=False,
           customCorner=False,
           intCorner=None,
           extCorner=None,
           ctlGrp=None,
           defGrp=None):
    """Create eyelid and eye rig

    Args:
        eyeMesh (TYPE): Description
        edgeLoop (TYPE): Description
        blinkH (TYPE): Description
        namePrefix (TYPE): Description
        offset (TYPE): Description
        rigidLoops (TYPE): Description
        falloffLoops (TYPE): Description
        headJnt (TYPE): Description
        doSkin (TYPE): Description
        parent (None, optional): Description
        ctlName (str, optional): Description
        sideRange (bool, optional): Description
        customCorner (bool, optional): Description
        intCorner (None, optional): Description
        extCorner (None, optional): Description
        ctlGrp (None, optional): Description
        defGrp (None, optional): Description

    Returns:
        TYPE: Description
    """
    # Checkers
    if edgeLoop:
        edgeLoopList = [pm.PyNode(e) for e in edgeLoop.split(",")]
    else:
        pm.displayWarning("Please set the edge loop first")
        return

    if eyeMesh:
        try:
            eyeMesh = pm.PyNode(eyeMesh)
        except pm.MayaNodeError:
            pm.displayWarning("The object %s can not be found in the "
                              "scene" % (eyeMesh))
            return
    else:
        pm.displayWarning("Please set the eye mesh first")

    if doSkin:
        if not headJnt:
            pm.displayWarning("Please set the Head Jnt or unCheck "
                              "Compute Topological Autoskin")
            return

    # Initial Data
    bboxCenter = meshNavigation.bboxCenter(eyeMesh)

    extr_v = meshNavigation.getExtremeVertexFromLoop(edgeLoopList, sideRange)
    upPos = extr_v[0]
    lowPos = extr_v[1]
    inPos = extr_v[2]
    outPos = extr_v[3]
    edgeList = extr_v[4]
    vertexList = extr_v[5]

    # Detect the side L or R from the x value
    if inPos.getPosition(space='world')[0] < 0.0:
        side = "R"
        inPos = extr_v[3]
        outPos = extr_v[2]
        normalPos = outPos
        npw = normalPos.getPosition(space='world')
        normalVec = npw - bboxCenter
    else:
        side = "L"
        normalPos = outPos
        npw = normalPos.getPosition(space='world')
        normalVec = bboxCenter - npw
    # Manual Vertex corners
    if customCorner:
        if intCorner:
            try:
                if side == "R":
                    inPos = pm.PyNode(extCorner)
                else:
                    inPos = pm.PyNode(intCorner)
            except pm.MayaNodeError:
                pm.displayWarning("%s can not be found" % intCorner)
                return
        else:
            pm.displayWarning("Please set the internal eyelid corner")
            return

        if extCorner:
            try:
                normalPos = pm.PyNode(extCorner)
                npw = normalPos.getPosition(space='world')
                if side == "R":
                    outPos = pm.PyNode(intCorner)
                    normalVec = npw - bboxCenter
                else:
                    outPos = pm.PyNode(extCorner)
                    normalVec = bboxCenter - npw
            except pm.MayaNodeError:
                pm.displayWarning("%s can not be found" % extCorner)
                return
        else:
            pm.displayWarning("Please set the external eyelid corner")
            return

    # Check if we have prefix:
    if namePrefix:
        namePrefix = string.removeInvalidCharacter(namePrefix)
    else:
        pm.displayWarning("Prefix is needed")
        return

    def setName(name, ind=None):
        namesList = [namePrefix, side, name]
        if ind is not None:
            namesList[1] = side + str(ind)
        name = "_".join(namesList)
        return name

    if pm.ls(setName("root")):
        pm.displayWarning("The object %s already exist in the scene. Please "
                          "choose another name prefix" % setName("root"))
        return

    # Eye root
    eye_root = primitive.addTransform(None, setName("root"))
    eyeCrv_root = primitive.addTransform(eye_root, setName("crvs"))

    # Eyelid Main crvs
    try:
        upEyelid = meshNavigation.edgeRangeInLoopFromMid(
            edgeList, upPos, inPos, outPos)
        upCrv = curve.createCurveFromOrderedEdges(
            upEyelid, inPos, setName("upperEyelid"), parent=eyeCrv_root)
        upCrv_ctl = curve.createCurveFromOrderedEdges(
            upEyelid, inPos, setName("upCtl_crv"), parent=eyeCrv_root)
        pm.rebuildCurve(upCrv_ctl, s=2, rt=0, rpo=True, ch=False)

        lowEyelid = meshNavigation.edgeRangeInLoopFromMid(
            edgeList, lowPos, inPos, outPos)
        lowCrv = curve.createCurveFromOrderedEdges(
            lowEyelid, inPos, setName("lowerEyelid"), parent=eyeCrv_root)
        lowCrv_ctl = curve.createCurveFromOrderedEdges(
            lowEyelid,
            inPos,
            setName("lowCtl_crv"),
            parent=eyeCrv_root)

        pm.rebuildCurve(lowCrv_ctl, s=2, rt=0, rpo=True, ch=False)

    except UnboundLocalError:
        if customCorner:
            pm.displayWarning("This error is maybe caused because the custom "
                              "Corner vertex is not part of the edge loop")
        pm.displayError(traceback.format_exc())
        return

    upBlink = curve.createCurveFromCurve(
        upCrv, setName("upblink_crv"), nbPoints=30, parent=eyeCrv_root)
    lowBlink = curve.createCurveFromCurve(
        lowCrv, setName("lowBlink_crv"), nbPoints=30, parent=eyeCrv_root)

    upTarget = curve.createCurveFromCurve(
        upCrv, setName("upblink_target"), nbPoints=30, parent=eyeCrv_root)
    lowTarget = curve.createCurveFromCurve(
        lowCrv, setName("lowBlink_target"), nbPoints=30, parent=eyeCrv_root)
    midTarget = curve.createCurveFromCurve(
        lowCrv, setName("midBlink_target"), nbPoints=30, parent=eyeCrv_root)

    rigCrvs = [upCrv,
               lowCrv,
               upCrv_ctl,
               lowCrv_ctl,
               upBlink,
               lowBlink,
               upTarget,
               lowTarget,
               midTarget]

    for crv in rigCrvs:
        crv.attr("visibility").set(False)

    # localBBOX
    localBBox = eyeMesh.getBoundingBox(invisible=True, space='world')
    wRadius = abs((localBBox[0][0] - localBBox[1][0]))
    dRadius = abs((localBBox[0][1] - localBBox[1][1]) / 1.7)

    # Groups
    if not ctlGrp:
        ctlGrp = "rig_controllers_grp"
    try:
        ctlSet = pm.PyNode(ctlGrp)
    except pm.MayaNodeError:
        pm.sets(n=ctlGrp, em=True)
        ctlSet = pm.PyNode(ctlGrp)
    if not defGrp:
        defGrp = "rig_deformers_grp"
    try:
        defset = pm.PyNode(defGrp)
    except pm.MayaNodeError:
        pm.sets(n=defGrp, em=True)
        defset = pm.PyNode(defGrp)

    # Calculate center looking at
    averagePosition = ((upPos.getPosition(space='world')
                        + lowPos.getPosition(space='world')
                        + inPos.getPosition(space='world')
                        + outPos.getPosition(space='world'))
                       / 4)
    if side == "R":
        negate = False
        offset = offset
        over_offset = dRadius
    else:
        negate = False
        over_offset = dRadius

    if side == "R" and sideRange or side == "R" and customCorner:
        axis = "z-x"
        # axis = "zx"
    else:
        axis = "z-x"

    t = transform.getTransformLookingAt(
        bboxCenter,
        averagePosition,
        normalVec,
        axis=axis,
        negate=negate)

    over_npo = primitive.addTransform(
        eye_root, setName("center_lookatRoot"), t)

    over_ctl = icon.create(over_npo,
                           setName("over_%s" % ctlName),
                           t,
                           icon="square",
                           w=wRadius,
                           d=dRadius,
                           ro=datatypes.Vector(1.57079633, 0, 0),
                           po=datatypes.Vector(0, 0, over_offset),
                           color=4)
    node.add_controller_tag(over_ctl)
    attribute.add_mirror_config_channels(over_ctl)
    attribute.setKeyableAttributes(
        over_ctl,
        params=["tx", "ty", "tz", "ro", "rx", "ry", "rz", "sx", "sy", "sz"])

    if side == "R":
        over_npo.attr("rx").set(over_npo.attr("rx").get() * -1)
        over_npo.attr("ry").set(over_npo.attr("ry").get() + 180)
        over_npo.attr("sz").set(-1)

    if len(ctlName.split("_")) == 2 and ctlName.split("_")[-1] == "ghost":
        pass
    else:
        pm.sets(ctlSet, add=over_ctl)

    center_lookat = primitive.addTransform(
        over_ctl, setName("center_lookat"), t)

    # Tracking
    # Eye aim control
    t_arrow = transform.getTransformLookingAt(bboxCenter,
                                              averagePosition,
                                              upPos.getPosition(space='world'),
                                              axis="zy", negate=False)

    radius = abs((localBBox[0][0] - localBBox[1][0]) / 1.7)
    arrow_npo = primitive.addTransform(eye_root, setName("aim_npo"), t_arrow)
    arrow_ctl = icon.create(arrow_npo,
                            setName("aim_%s" % ctlName),
                            t_arrow,
                            icon="arrow",
                            w=1,
                            po=datatypes.Vector(0, 0, radius),
                            color=4)
    if len(ctlName.split("_")) == 2 and ctlName.split("_")[-1] == "ghost":
        pass
    else:
        pm.sets(ctlSet, add=arrow_ctl)
    attribute.setKeyableAttributes(arrow_ctl, params=["rx", "ry", "rz"])

    # tracking custom trigger
    if side == "R":
        tt = t_arrow
    else:
        tt = t
    aimTrigger_root = primitive.addTransform(
        center_lookat, setName("aimTrigger_root"), tt)
    aimTrigger_lvl = primitive.addTransform(
        aimTrigger_root, setName("aimTrigger_lvl"), tt)
    aimTrigger_lvl.attr("tz").set(1.0)
    aimTrigger_ref = primitive.addTransform(
        aimTrigger_lvl, setName("aimTrigger_ref"), tt)
    aimTrigger_ref.attr("tz").set(0.0)
    # connect  trigger with arrow_ctl
    pm.parentConstraint(arrow_ctl, aimTrigger_ref, mo=True)

    # Controls lists
    upControls = []
    trackLvl = []

    # upper eyelid controls
    upperCtlNames = ["inCorner", "upInMid", "upMid", "upOutMid", "outCorner"]
    cvs = upCrv_ctl.getCVs(space="world")
    if side == "R" and not sideRange:
        # if side == "R":
        cvs = [cv for cv in reversed(cvs)]
    for i, cv in enumerate(cvs):
        if utils.is_odd(i):
            color = 14
            wd = .5
            icon_shape = "circle"
            params = ["tx", "ty", "tz"]
        else:
            color = 4
            wd = .7
            icon_shape = "square"
            params = ["tx",
                      "ty",
                      "tz",
                      "ro",
                      "rx",
                      "ry",
                      "rz",
                      "sx",
                      "sy",
                      "sz"]

        t = transform.setMatrixPosition(t, cvs[i])
        npo = primitive.addTransform(center_lookat,
                                     setName("%s_npo" % upperCtlNames[i]),
                                     t)
        npoBase = npo
        if i == 2:
            # we add an extra level to input the tracking ofset values
            npo = primitive.addTransform(npo,
                                         setName("%s_trk" % upperCtlNames[i]),
                                         t)
            trackLvl.append(npo)

        ctl = icon.create(npo,
                          setName("%s_%s" % (upperCtlNames[i], ctlName)),
                          t,
                          icon=icon_shape,
                          w=wd,
                          d=wd,
                          ro=datatypes.Vector(1.57079633, 0, 0),
                          po=datatypes.Vector(0, 0, offset),
                          color=color)
        attribute.add_mirror_config_channels(ctl)
        node.add_controller_tag(ctl, over_ctl)
        upControls.append(ctl)
        if len(ctlName.split("_")) == 2 and ctlName.split("_")[-1] == "ghost":
            pass
        else:
            pm.sets(ctlSet, add=ctl)
        attribute.setKeyableAttributes(ctl, params)
        if side == "R":
            npoBase.attr("ry").set(180)
            npoBase.attr("sz").set(-1)

    # adding parent average contrains to odd controls
    for i, ctl in enumerate(upControls):
        if utils.is_odd(i):
            cns_node = pm.parentConstraint(upControls[i - 1],
                                upControls[i + 1],
                                ctl.getParent(),
                                mo=True)
            # Make the constraint "noFlip"
            cns_node.interpType.set(0)

    # lower eyelid controls
    lowControls = [upControls[0]]
    lowerCtlNames = ["inCorner",
                     "lowInMid",
                     "lowMid",
                     "lowOutMid",
                     "outCorner"]

    cvs = lowCrv_ctl.getCVs(space="world")
    if side == "R" and not sideRange:
        cvs = [cv for cv in reversed(cvs)]
    for i, cv in enumerate(cvs):
        # we skip the first and last point since is already in the uper eyelid
        if i in [0, 4]:
            continue
        if utils.is_odd(i):
            color = 14
            wd = .5
            icon_shape = "circle"
            params = ["tx", "ty", "tz"]
        else:
            color = 4
            wd = .7
            icon_shape = "square"
            params = ["tx",
                      "ty",
                      "tz",
                      "ro",
                      "rx",
                      "ry",
                      "rz",
                      "sx",
                      "sy",
                      "sz"]

        t = transform.setMatrixPosition(t, cvs[i])
        npo = primitive.addTransform(center_lookat,
                                     setName("%s_npo" % lowerCtlNames[i]),
                                     t)
        npoBase = npo
        if i == 2:
            # we add an extra level to input the tracking ofset values
            npo = primitive.addTransform(npo,
                                         setName("%s_trk" % lowerCtlNames[i]),
                                         t)
            trackLvl.append(npo)
        ctl = icon.create(npo,
                          setName("%s_%s" % (lowerCtlNames[i], ctlName)),
                          t,
                          icon=icon_shape,
                          w=wd,
                          d=wd,
                          ro=datatypes.Vector(1.57079633, 0, 0),
                          po=datatypes.Vector(0, 0, offset),
                          color=color)
        attribute.add_mirror_config_channels(ctl)

        lowControls.append(ctl)
        if len(ctlName.split("_")) == 2 and ctlName.split("_")[-1] == "ghost":
            pass
        else:
            pm.sets(ctlSet, add=ctl)
        attribute.setKeyableAttributes(ctl, params)
        # mirror behaviout on R side controls
        if side == "R":
            npoBase.attr("ry").set(180)
            npoBase.attr("sz").set(-1)
    for lctl in reversed(lowControls[1:]):
        node.add_controller_tag(lctl, over_ctl)
    lowControls.append(upControls[-1])

    # adding parent average contrains to odd controls
    for i, ctl in enumerate(lowControls):
        if utils.is_odd(i):
            cns_node = pm.parentConstraint(lowControls[i - 1],
                                lowControls[i + 1],
                                ctl.getParent(),
                                mo=True)
            # Make the constraint "noFlip"
            cns_node.interpType.set(0)

    # Connecting control crvs with controls
    applyop.gear_curvecns_op(upCrv_ctl, upControls)
    applyop.gear_curvecns_op(lowCrv_ctl, lowControls)

    # adding wires
    w1 = pm.wire(upCrv, w=upBlink)[0]
    w2 = pm.wire(lowCrv, w=lowBlink)[0]

    w3 = pm.wire(upTarget, w=upCrv_ctl)[0]
    w4 = pm.wire(lowTarget, w=lowCrv_ctl)[0]

    # adding blendshapes
    bs_upBlink = pm.blendShape(upTarget,
                               midTarget,
                               upBlink,
                               n="blendShapeUpBlink")
    bs_lowBlink = pm.blendShape(lowTarget,
                                midTarget,
                                lowBlink,
                                n="blendShapeLowBlink")
    bs_mid = pm.blendShape(lowTarget,
                           upTarget,
                           midTarget,
                           n="blendShapeLowBlink")

    # setting blendshape reverse connections
    rev_node = pm.createNode("reverse")
    pm.connectAttr(bs_upBlink[0].attr(midTarget.name()), rev_node + ".inputX")
    pm.connectAttr(rev_node + ".outputX", bs_upBlink[0].attr(upTarget.name()))
    rev_node = pm.createNode("reverse")
    pm.connectAttr(bs_lowBlink[0].attr(midTarget.name()), rev_node + ".inputX")
    pm.connectAttr(rev_node + ".outputX",
                   bs_lowBlink[0].attr(lowTarget.name()))
    rev_node = pm.createNode("reverse")
    pm.connectAttr(bs_mid[0].attr(upTarget.name()), rev_node + ".inputX")
    pm.connectAttr(rev_node + ".outputX", bs_mid[0].attr(lowTarget.name()))

    # setting default values
    bs_mid[0].attr(upTarget.name()).set(blinkH)

    # joints root
    jnt_root = primitive.addTransformFromPos(
        eye_root, setName("joints"), pos=bboxCenter)

    # head joint
    if headJnt:
        try:
            headJnt = pm.PyNode(headJnt)
            jnt_base = headJnt
        except pm.MayaNodeError:
            pm.displayWarning(
                "Aborted can not find %s " % headJnt)
            return
    else:
        # Eye root
        jnt_base = jnt_root

    eyeTargets_root = primitive.addTransform(eye_root,
                                             setName("targets"))

    eyeCenter_jnt = rigbits.addJnt(arrow_ctl,
                                   jnt_base,
                                   grp=defset,
                                   jntName=setName("center_jnt"))

    # Upper Eyelid joints ##################################################

    cvs = upCrv.getCVs(space="world")
    upCrv_info = node.createCurveInfoNode(upCrv)

    # aim constrain targets and joints
    upperEyelid_aimTargets = []
    upperEyelid_jnt = []
    upperEyelid_jntRoot = []

    for i, cv in enumerate(cvs):

        # aim targets
        trn = primitive.addTransformFromPos(eyeTargets_root,
                                            setName("upEyelid_aimTarget", i),
                                            pos=cv)
        upperEyelid_aimTargets.append(trn)
        # connecting positions with crv
        pm.connectAttr(upCrv_info + ".controlPoints[%s]" % str(i),
                       trn.attr("translate"))

        # joints
        jntRoot = primitive.addJointFromPos(jnt_root,
                                            setName("upEyelid_jnt_base", i),
                                            pos=bboxCenter)
        jntRoot.attr("radius").set(.08)
        jntRoot.attr("visibility").set(False)
        upperEyelid_jntRoot.append(jntRoot)
        applyop.aimCns(jntRoot, trn, axis="zy", wupObject=jnt_root)

        jnt_ref = primitive.addJointFromPos(jntRoot,
                                            setName("upEyelid_jnt_ref", i),
                                            pos=cv)
        jnt_ref.attr("radius").set(.08)
        jnt_ref.attr("visibility").set(False)

        jnt = rigbits.addJnt(jnt_ref,
                             jnt_base,
                             grp=defset,
                             jntName=setName("upEyelid_jnt", i))
        upperEyelid_jnt.append(jnt)

    # Lower Eyelid joints ##################################################

    cvs = lowCrv.getCVs(space="world")
    lowCrv_info = node.createCurveInfoNode(lowCrv)

    # aim constrain targets and joints
    lowerEyelid_aimTargets = []
    lowerEyelid_jnt = []
    lowerEyelid_jntRoot = []

    for i, cv in enumerate(cvs):
        if i in [0, len(cvs) - 1]:
            continue

        # aim targets
        trn = primitive.addTransformFromPos(eyeTargets_root,
                                            setName("lowEyelid_aimTarget", i),
                                            pos=cv)
        lowerEyelid_aimTargets.append(trn)
        # connecting positions with crv
        pm.connectAttr(lowCrv_info + ".controlPoints[%s]" % str(i),
                       trn.attr("translate"))

        # joints
        jntRoot = primitive.addJointFromPos(jnt_root,
                                            setName("lowEyelid_base", i),
                                            pos=bboxCenter)
        jntRoot.attr("radius").set(.08)
        jntRoot.attr("visibility").set(False)
        lowerEyelid_jntRoot.append(jntRoot)
        applyop.aimCns(jntRoot, trn, axis="zy", wupObject=jnt_root)

        jnt_ref = primitive.addJointFromPos(jntRoot,
                                            setName("lowEyelid_jnt_ref", i),
                                            pos=cv)
        jnt_ref.attr("radius").set(.08)
        jnt_ref.attr("visibility").set(False)

        jnt = rigbits.addJnt(jnt_ref,
                             jnt_base,
                             grp=defset,
                             jntName=setName("lowEyelid_jnt", i))
        lowerEyelid_jnt.append(jnt)

    # Channels
    # Adding and connecting attributes for the blink
    up_ctl = upControls[2]
    blink_att = attribute.addAttribute(
        over_ctl, "blink", "float", 0, minValue=0, maxValue=1)
    blinkMult_att = attribute.addAttribute(
        over_ctl, "blinkMult", "float", 1, minValue=1, maxValue=2)
    midBlinkH_att = attribute.addAttribute(
        over_ctl, "blinkHeight", "float", blinkH, minValue=0, maxValue=1)
    mult_node = node.createMulNode(blink_att, blinkMult_att)
    pm.connectAttr(mult_node + ".outputX",
                   bs_upBlink[0].attr(midTarget.name()))
    pm.connectAttr(mult_node + ".outputX",
                   bs_lowBlink[0].attr(midTarget.name()))
    pm.connectAttr(midBlinkH_att, bs_mid[0].attr(upTarget.name()))

    low_ctl = lowControls[2]

    # Adding channels for eye tracking
    upVTracking_att = attribute.addAttribute(up_ctl,
                                             "vTracking",
                                             "float",
                                             .02,
                                             minValue=0,
                                             maxValue=1,
                                             keyable=False,
                                             channelBox=True)
    upHTracking_att = attribute.addAttribute(up_ctl,
                                             "hTracking",
                                             "float",
                                             .01,
                                             minValue=0,
                                             maxValue=1,
                                             keyable=False,
                                             channelBox=True)

    lowVTracking_att = attribute.addAttribute(low_ctl,
                                              "vTracking",
                                              "float",
                                              .01,
                                              minValue=0,
                                              maxValue=1,
                                              keyable=False,
                                              channelBox=True)
    lowHTracking_att = attribute.addAttribute(low_ctl,
                                              "hTracking",
                                              "float",
                                              .01,
                                              minValue=0,
                                              maxValue=1,
                                              keyable=False,
                                              channelBox=True)

    mult_node = node.createMulNode(upVTracking_att, aimTrigger_ref.attr("ty"))
    pm.connectAttr(mult_node + ".outputX", trackLvl[0].attr("ty"))
    mult_node = node.createMulNode(upHTracking_att, aimTrigger_ref.attr("tx"))
    pm.connectAttr(mult_node + ".outputX", trackLvl[0].attr("tx"))

    mult_node = node.createMulNode(lowVTracking_att, aimTrigger_ref.attr("ty"))
    pm.connectAttr(mult_node + ".outputX", trackLvl[1].attr("ty"))
    mult_node = node.createMulNode(lowHTracking_att, aimTrigger_ref.attr("tx"))
    pm.connectAttr(mult_node + ".outputX", trackLvl[1].attr("tx"))

    # Tension on blink
    node.createReverseNode(blink_att, w1.scale[0])
    node.createReverseNode(blink_att, w3.scale[0])
    node.createReverseNode(blink_att, w2.scale[0])
    node.createReverseNode(blink_att, w4.scale[0])

    ###########################################
    # Reparenting
    ###########################################
    if parent:
        try:
            if isinstance(parent, basestring):
                parent = pm.PyNode(parent)
            parent.addChild(eye_root)
        except pm.MayaNodeError:
            pm.displayWarning("The eye rig can not be parent to: %s. Maybe "
                              "this object doesn't exist." % parent)

    ###########################################
    # Auto Skinning
    ###########################################
    if doSkin:
        # eyelid vertex rows
        totalLoops = rigidLoops + falloffLoops
        vertexLoopList = meshNavigation.getConcentricVertexLoop(vertexList,
                                                                totalLoops)
        vertexRowList = meshNavigation.getVertexRowsFromLoops(vertexLoopList)

        # we set the first value 100% for the first initial loop
        skinPercList = [1.0]
        # we expect to have a regular grid topology
        for r in range(rigidLoops):
            for rr in range(2):
                skinPercList.append(1.0)
        increment = 1.0 / float(falloffLoops)
        # we invert to smooth out from 100 to 0
        inv = 1.0 - increment
        for r in range(falloffLoops):
            for rr in range(2):
                if inv < 0.0:
                    inv = 0.0
                skinPercList.append(inv)
            inv -= increment

        # this loop add an extra 0.0 indices to avoid errors
        for r in range(10):
            for rr in range(2):
                skinPercList.append(0.0)

        # base skin
        geo = pm.listRelatives(edgeLoopList[0], parent=True)[0]
        # Check if the object has a skinCluster
        objName = pm.listRelatives(geo, parent=True)[0]

        skinCluster = skin.getSkinCluster(objName)
        if not skinCluster:
            skinCluster = pm.skinCluster(headJnt,
                                         geo,
                                         tsb=True,
                                         nw=2,
                                         n='skinClsEyelid')

        eyelidJoints = upperEyelid_jnt + lowerEyelid_jnt
        pm.progressWindow(title='Auto skinning process',
                          progress=0,
                          max=len(eyelidJoints))
        firstBoundary = False
        for jnt in eyelidJoints:
            pm.progressWindow(e=True, step=1, status='\nSkinning %s' % jnt)
            skinCluster.addInfluence(jnt, weight=0)
            v = meshNavigation.getClosestVertexFromTransform(geo, jnt)

            for row in vertexRowList:

                if v in row:
                    it = 0  # iterator
                    inc = 1  # increment
                    for i, rv in enumerate(row):
                        try:
                            perc = skinPercList[it]
                            t_val = [(jnt, perc), (headJnt, 1.0 - perc)]
                            pm.skinPercent(skinCluster,
                                           rv,
                                           transformValue=t_val)
                            if rv.isOnBoundary():
                                # we need to compare with the first boundary
                                # to check if the row have inverted direction
                                # and offset the value
                                if not firstBoundary:
                                    firstBoundary = True
                                    firstBoundaryValue = it

                                else:
                                    if it < firstBoundaryValue:
                                        it -= 1
                                    elif it > firstBoundaryValue:
                                        it += 1
                                inc = 2
                        except IndexError:
                            continue

                        it = it + inc
        pm.progressWindow(e=True, endProgress=True)

        # Eye Mesh skinning
        skinCluster = skin.getSkinCluster(eyeMesh)
        if not skinCluster:
            skinCluster = pm.skinCluster(eyeCenter_jnt,
                                         eyeMesh,
                                         tsb=True,
                                         nw=1,
                                         n='skinClsEye')

##########################################################
# Eye Rig UI
##########################################################


class eyeRigUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(eyeRigUI, self).__init__(parent)
        self.create()

    def create(self):

        self.setWindowTitle("Rigbits: Eye Rigger")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)

        self.create_controls()
        self.create_layout()
        self.create_connections()

    def create_controls(self):

        # Geometry input controls
        self.geometryInput_group = QtWidgets.QGroupBox("Geometry Input")
        self.eyeball_label = QtWidgets.QLabel("Eyeball:")
        self.eyeball_lineEdit = QtWidgets.QLineEdit()
        self.eyeball_button = QtWidgets.QPushButton("<<")
        self.edgeloop_label = QtWidgets.QLabel("Edge Loop:")
        self.edgeloop_lineEdit = QtWidgets.QLineEdit()
        self.edgeloop_button = QtWidgets.QPushButton("<<")

        # Manual corners
        self.manualCorners_group = QtWidgets.QGroupBox("Custom Eye Corners")
        self.manualCorners_check = QtWidgets.QCheckBox(
            "Set Manual Vertex Corners")
        self.manualCorners_check.setChecked(False)
        self.intCorner_label = QtWidgets.QLabel("Internal Corner")
        self.intCorner_lineEdit = QtWidgets.QLineEdit()
        self.intCorner_button = QtWidgets.QPushButton("<<")
        self.extCorner_label = QtWidgets.QLabel("External Corner")
        self.extCorner_lineEdit = QtWidgets.QLineEdit()
        self.extCorner_button = QtWidgets.QPushButton("<<")

        # Blink heigh slider
        self.blinkHeigh_group = QtWidgets.QGroupBox("Blink High")
        self.blinkHeight_value = QtWidgets.QSpinBox()
        self.blinkHeight_value.setRange(0, 100)
        self.blinkHeight_value.setSingleStep(10)
        self.blinkHeight_value.setValue(20)
        self.blinkHeight_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.blinkHeight_slider.setRange(0, 100)
        self.blinkHeight_slider.setSingleStep(
            self.blinkHeight_slider.maximum() / 10.0)
        self.blinkHeight_slider.setValue(20)

        # Name prefix
        self.prefix_group = QtWidgets.QGroupBox("Name Prefix")
        self.prefix_lineEdit = QtWidgets.QLineEdit()
        self.prefix_lineEdit.setText("eye")
        self.control_group = QtWidgets.QGroupBox("Control Name Extension")
        self.control_lineEdit = QtWidgets.QLineEdit()
        self.control_lineEdit.setText("ctl")

        # joints
        self.joints_group = QtWidgets.QGroupBox("Joints")
        self.headJnt_label = QtWidgets.QLabel("Head or Eye area Joint:")
        self.headJnt_lineEdit = QtWidgets.QLineEdit()
        self.headJnt_button = QtWidgets.QPushButton("<<")

        # Topological Autoskin
        self.topoSkin_group = QtWidgets.QGroupBox("Skin")
        self.rigidLoops_label = QtWidgets.QLabel("Rigid Loops:")
        self.rigidLoops_value = QtWidgets.QSpinBox()
        self.rigidLoops_value.setRange(0, 30)
        self.rigidLoops_value.setSingleStep(1)
        self.rigidLoops_value.setValue(2)
        self.falloffLoops_label = QtWidgets.QLabel("Falloff Loops:")
        self.falloffLoops_value = QtWidgets.QSpinBox()
        self.falloffLoops_value.setRange(0, 30)
        self.falloffLoops_value.setSingleStep(1)
        self.falloffLoops_value.setValue(4)

        self.topSkin_check = QtWidgets.QCheckBox(
            'Compute Topological Autoskin')
        self.topSkin_check.setChecked(True)

        # Options
        self.options_group = QtWidgets.QGroupBox("Options")
        self.parent_label = QtWidgets.QLabel("Rig Parent:")
        self.parent_lineEdit = QtWidgets.QLineEdit()
        self.parent_button = QtWidgets.QPushButton("<<")
        self.ctlShapeOffset_label = QtWidgets.QLabel("Controls Offset:")
        self.ctlShapeOffset_value = QtWidgets.QDoubleSpinBox()
        self.ctlShapeOffset_value.setRange(0, 10)
        self.ctlShapeOffset_value.setSingleStep(.05)
        self.ctlShapeOffset_value.setValue(.05)
        self.sideRange_check = QtWidgets.QCheckBox(
            "Use Z axis for wide calculation (i.e: Horse and fish side eyes)")
        self.sideRange_check.setChecked(False)

        self.ctlGrp_label = QtWidgets.QLabel("Controls Group:")
        self.ctlGrp_lineEdit = QtWidgets.QLineEdit()
        self.ctlGrp_button = QtWidgets.QPushButton("<<")

        self.deformersGrp_label = QtWidgets.QLabel("Deformers Group:")
        self.deformersGrp_lineEdit = QtWidgets.QLineEdit()
        self.deformersGrp_button = QtWidgets.QPushButton("<<")

        # Build button
        self.build_button = QtWidgets.QPushButton("Build Eye Rig")
        self.export_button = QtWidgets.QPushButton("Export Config to json")

    def create_layout(self):

        # Eyeball Layout
        eyeball_layout = QtWidgets.QHBoxLayout()
        eyeball_layout.setContentsMargins(1, 1, 1, 1)
        eyeball_layout.addWidget(self.eyeball_label)
        eyeball_layout.addWidget(self.eyeball_lineEdit)
        eyeball_layout.addWidget(self.eyeball_button)

        # Edge Loop Layout
        edgeloop_layout = QtWidgets.QHBoxLayout()
        edgeloop_layout.setContentsMargins(1, 1, 1, 1)
        edgeloop_layout.addWidget(self.edgeloop_label)
        edgeloop_layout.addWidget(self.edgeloop_lineEdit)
        edgeloop_layout.addWidget(self.edgeloop_button)

        # Geometry Input Layout
        geometryInput_layout = QtWidgets.QVBoxLayout()
        geometryInput_layout.setContentsMargins(6, 1, 6, 2)
        geometryInput_layout.addLayout(eyeball_layout)
        geometryInput_layout.addLayout(edgeloop_layout)
        self.geometryInput_group.setLayout(geometryInput_layout)

        # Blink High Layout
        blinkHeight_layout = QtWidgets.QHBoxLayout()
        blinkHeight_layout.setContentsMargins(1, 1, 1, 1)
        blinkHeight_layout.addWidget(self.blinkHeight_value)
        blinkHeight_layout.addWidget(self.blinkHeight_slider)
        self.blinkHeigh_group.setLayout(blinkHeight_layout)

        # joints Layout
        headJnt_layout = QtWidgets.QHBoxLayout()
        headJnt_layout.addWidget(self.headJnt_label)
        headJnt_layout.addWidget(self.headJnt_lineEdit)
        headJnt_layout.addWidget(self.headJnt_button)

        joints_layout = QtWidgets.QVBoxLayout()
        joints_layout.setContentsMargins(6, 4, 6, 4)
        joints_layout.addLayout(headJnt_layout)
        self.joints_group.setLayout(joints_layout)

        # topological autoskin Layout
        skinLoops_layout = QtWidgets.QGridLayout()
        skinLoops_layout.addWidget(self.rigidLoops_label, 0, 0)
        skinLoops_layout.addWidget(self.falloffLoops_label, 0, 1)
        skinLoops_layout.addWidget(self.rigidLoops_value, 1, 0)
        skinLoops_layout.addWidget(self.falloffLoops_value, 1, 1)

        topoSkin_layout = QtWidgets.QVBoxLayout()
        topoSkin_layout.setContentsMargins(6, 4, 6, 4)
        topoSkin_layout.addWidget(self.topSkin_check,
                                  alignment=QtCore.Qt.Alignment())
        topoSkin_layout.addLayout(skinLoops_layout)
        self.topoSkin_group.setLayout(topoSkin_layout)

        # Manual Corners Layout
        intCorner_layout = QtWidgets.QHBoxLayout()
        intCorner_layout.addWidget(self.intCorner_label)
        intCorner_layout.addWidget(self.intCorner_lineEdit)
        intCorner_layout.addWidget(self.intCorner_button)

        extCorner_layout = QtWidgets.QHBoxLayout()
        extCorner_layout.addWidget(self.extCorner_label)
        extCorner_layout.addWidget(self.extCorner_lineEdit)
        extCorner_layout.addWidget(self.extCorner_button)

        manualCorners_layout = QtWidgets.QVBoxLayout()
        manualCorners_layout.setContentsMargins(6, 4, 6, 4)
        manualCorners_layout.addWidget(self.manualCorners_check,
                                       alignment=QtCore.Qt.Alignment())
        manualCorners_layout.addLayout(intCorner_layout)
        manualCorners_layout.addLayout(extCorner_layout)
        self.manualCorners_group.setLayout(manualCorners_layout)

        # Options Layout
        parent_layout = QtWidgets.QHBoxLayout()
        parent_layout.addWidget(self.parent_label)
        parent_layout.addWidget(self.parent_lineEdit)
        parent_layout.addWidget(self.parent_button)
        offset_layout = QtWidgets.QHBoxLayout()
        offset_layout.addWidget(self.ctlShapeOffset_label)
        offset_layout.addWidget(self.ctlShapeOffset_value)
        ctlGrp_layout = QtWidgets.QHBoxLayout()
        ctlGrp_layout.addWidget(self.ctlGrp_label)
        ctlGrp_layout.addWidget(self.ctlGrp_lineEdit)
        ctlGrp_layout.addWidget(self.ctlGrp_button)
        deformersGrp_layout = QtWidgets.QHBoxLayout()
        deformersGrp_layout.addWidget(self.deformersGrp_label)
        deformersGrp_layout.addWidget(self.deformersGrp_lineEdit)
        deformersGrp_layout.addWidget(self.deformersGrp_button)

        options_layout = QtWidgets.QVBoxLayout()
        options_layout.setContentsMargins(6, 1, 6, 2)
        options_layout.addLayout(parent_layout)
        options_layout.addLayout(offset_layout)
        options_layout.addWidget(self.blinkHeigh_group)
        options_layout.addWidget(self.sideRange_check)
        options_layout.addLayout(ctlGrp_layout)
        options_layout.addLayout(deformersGrp_layout)
        self.options_group.setLayout(options_layout)

        # Name prefix
        namePrefix_layout = QtWidgets.QVBoxLayout()
        namePrefix_layout.setContentsMargins(1, 1, 1, 1)
        namePrefix_layout.addWidget(self.prefix_lineEdit)
        self.prefix_group.setLayout(namePrefix_layout)

        # Name prefix
        controlExtension_layout = QtWidgets.QVBoxLayout()
        controlExtension_layout.setContentsMargins(1, 1, 1, 1)
        controlExtension_layout.addWidget(self.control_lineEdit)
        self.control_group.setLayout(controlExtension_layout)

        # Main Layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self.prefix_group)
        main_layout.addWidget(self.control_group)
        main_layout.addWidget(self.geometryInput_group)
        main_layout.addWidget(self.manualCorners_group)
        main_layout.addWidget(self.options_group)
        main_layout.addWidget(self.joints_group)
        main_layout.addWidget(self.topoSkin_group)
        main_layout.addWidget(self.build_button)
        main_layout.addWidget(self.export_button)

        self.setLayout(main_layout)

    def create_connections(self):
        self.blinkHeight_value.valueChanged[int].connect(
            self.blinkHeight_slider.setValue)
        self.blinkHeight_slider.valueChanged[int].connect(
            self.blinkHeight_value.setValue)

        self.eyeball_button.clicked.connect(partial(self.populate_object,
                                                    self.eyeball_lineEdit))
        self.parent_button.clicked.connect(partial(self.populate_object,
                                                   self.parent_lineEdit))
        self.headJnt_button.clicked.connect(partial(self.populate_object,
                                                    self.headJnt_lineEdit,
                                                    1))

        self.edgeloop_button.clicked.connect(self.populate_edgeloop)

        self.build_button.clicked.connect(self.buildRig)
        self.export_button.clicked.connect(self.exportDict)

        self.intCorner_button.clicked.connect(partial(self.populate_element,
                                                      self.intCorner_lineEdit,
                                                      "vertex"))
        self.extCorner_button.clicked.connect(partial(self.populate_element,
                                                      self.extCorner_lineEdit,
                                                      "vertex"))

        self.ctlGrp_button.clicked.connect(partial(self.populate_element,
                                                   self.ctlGrp_lineEdit,
                                                   "objectSet"))
        self.deformersGrp_button.clicked.connect(partial(
            self.populate_element, self.deformersGrp_lineEdit, "objectSet"))

    # SLOTS ##########################################################
    def populate_element(self, lEdit, oType="transform"):
        if oType == "joint":
            oTypeInst = pm.nodetypes.Joint
        elif oType == "vertex":
            oTypeInst = pm.MeshVertex
        elif oType == "objectSet":
            oTypeInst = pm.nodetypes.ObjectSet
        else:
            oTypeInst = pm.nodetypes.Transform

        oSel = pm.selected()
        if oSel:
            if isinstance(oSel[0], oTypeInst):
                lEdit.setText(oSel[0].name())
            else:
                pm.displayWarning(
                    "The selected element is not a valid %s" % oType)
        else:
            pm.displayWarning("Please select first one %s." % oType)

    def populate_object(self, lEdit, oType=None):
        if oType == 1:
            oType = pm.nodetypes.Joint
        else:
            oType = pm.nodetypes.Transform

        oSel = pm.selected()
        if oSel:
            if isinstance(oSel[0], oType):
                lEdit.setText(oSel[0].name())
            else:
                pm.displayWarning("The selected element is not a valid object")
        else:
            pm.displayWarning("Please select first the  object.")

    def populate_edgeloop(self):
        oSel = pm.selected(fl=1)
        if oSel:
            edgeList = ""
            separator = ""
            for e in oSel:
                if isinstance(e, pm.MeshEdge):
                    if edgeList:
                        separator = ","
                    edgeList = edgeList + separator + str(e)
            if not edgeList:
                pm.displayWarning("Please select first the eyelid edge loop.")
            elif len(edgeList.split(",")) < 4:
                pm.displayWarning("The minimun edge count is 4")
            else:
                self.edgeloop_lineEdit.setText(edgeList)

        else:
            pm.displayWarning("Please select first the eyelid edge loop.")

    def populateDict(self):
        self.buildDict = {}
        blinkH = float(self.blinkHeight_value.value()) / 100.0
        self.buildDict["eye"] = [self.eyeball_lineEdit.text(),
                                 self.edgeloop_lineEdit.text(),
                                 blinkH,
                                 self.prefix_lineEdit.text(),
                                 self.ctlShapeOffset_value.value(),
                                 self.rigidLoops_value.value(),
                                 self.falloffLoops_value.value(),
                                 self.headJnt_lineEdit.text(),
                                 self.topSkin_check.isChecked(),
                                 self.parent_lineEdit.text(),
                                 self.control_lineEdit.text(),
                                 self.sideRange_check.isChecked(),
                                 self.manualCorners_check.isChecked(),
                                 self.intCorner_lineEdit.text(),
                                 self.extCorner_lineEdit.text(),
                                 self.ctlGrp_lineEdit.text(),
                                 self.deformersGrp_lineEdit.text()]

    def buildRig(self):
        self.populateDict()
        eyeRig(*self.buildDict["eye"])

    def exportDict(self):
        self.populateDict()

        data_string = json.dumps(self.buildDict, indent=4, sort_keys=True)
        filePath = pm.fileDialog2(
            fileMode=0,
            fileFilter='Eyes Rigger Configuration .eyes (*%s)' % ".eyes")
        if not filePath:
            return
        if not isinstance(filePath, basestring):
            filePath = filePath[0]
        f = open(filePath, 'w')
        f.write(data_string)
        f.close()


# build lips from json file:
def eyesFromfile(path):
    buildDict = json.load(open(path))
    eyeRig(*buildDict["eye"])


def showEyeRigUI(*args):
    gqt.showDialog(eyeRigUI)


if __name__ == "__main__":
    showEyeRigUI()

    # path = "C:\\Users\\miquel\\Desktop\\eye_L.eyes"
    # eyesFromfile(path)

    # path = "C:\\Users\\miquel\\Desktop\\eye_R.eyes"
    # eyesFromfile(path)
