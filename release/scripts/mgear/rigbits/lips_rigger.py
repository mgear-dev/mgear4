"""Rigbits lips rigger tool"""

import json
from functools import partial

import mgear.core.pyqt as gqt
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from mgear.vendor.Qt import QtCore, QtWidgets
from pymel.core import datatypes

from mgear import rigbits
from mgear.core import meshNavigation, curve, applyop, primitive, icon
from mgear.core import transform, attribute, skin, vector
from .six import string_types

##########################################################
# Lips rig constructor
##########################################################


def lipsRig(eLoop,
            upVertex,
            lowVertex,
            namePrefix,
            thickness,
            doSkin,
            rigidLoops,
            falloffLoops,
            headJnt=None,
            jawJnt=None,
            parent=None,
            ctlName="ctl"):

    ######
    # Var
    ######

    FRONT_OFFSET = .02
    NB_ROPE = 15

    ##################
    # Helper functions
    ##################
    def setName(name, side="C", idx=None):
        namesList = [namePrefix, side, name]
        if idx is not None:
            namesList[1] = side + str(idx)
        name = "_".join(namesList)
        return name

    ###############
    # Checkers
    ##############

    # Loop
    if eLoop:
        try:
            eLoop = [pm.PyNode(e) for e in eLoop.split(",")]
        except pm.MayaNodeError:
            pm.displayWarning(
                "Some of the edges listed in edge loop can not be found")
            return
    else:
        pm.displayWarning("Please set the edge loop first")
        return

    # Vertex
    if upVertex:
        try:
            upVertex = pm.PyNode(upVertex)
        except pm.MayaNodeError:
            pm.displayWarning("%s can not be found" % upVertex)
            return
    else:
        pm.displayWarning("Please set the upper lip central vertex")
        return

    if lowVertex:
        try:
            lowVertex = pm.PyNode(lowVertex)
        except pm.MayaNodeError:
            pm.displayWarning("%s can not be found" % lowVertex)
            return
    else:
        pm.displayWarning("Please set the lower lip central vertex")
        return

    # skinnign data
    if doSkin:
        if not headJnt:
            pm.displayWarning("Please set the Head Jnt or unCheck Compute "
                              "Topological Autoskin")
            return
        else:
            try:
                headJnt = pm.PyNode(headJnt)
            except pm.MayaNodeError:
                pm.displayWarning("Head Joint: %s can not be found" % headJnt)
                return
        if not jawJnt:
            pm.displayWarning("Please set the Jaw Jnt or unCheck Compute "
                              "Topological Autoskin")
            return
        else:
            try:
                jawJnt = pm.PyNode(jawJnt)
            except pm.MayaNodeError:
                pm.displayWarning("Jaw Joint: %s can not be found" % jawJnt)
                return
    # check if the rig already exist in the current scene
    if pm.ls(setName("root")):
        pm.displayWarning("The object %s already exist in the scene. Please "
                          "choose another name prefix" % setName("root"))
        return

    #####################
    # Root creation
    #####################
    lips_root = primitive.addTransform(None, setName("root"))
    lipsCrv_root = primitive.addTransform(lips_root, setName("crvs"))
    lipsRope_root = primitive.addTransform(lips_root, setName("rope"))

    #####################
    # Geometry
    #####################
    geo = pm.listRelatives(eLoop[0], parent=True)[0]

    #####################
    # Groups
    #####################
    try:
        ctlSet = pm.PyNode("rig_controllers_grp")
    except pm.MayaNodeError:
        pm.sets(n="rig_controllers_grp", em=True)
        ctlSet = pm.PyNode("rig_controllers_grp")
    try:
        defset = pm.PyNode("rig_deformers_grp")
    except pm.MayaNodeError:
        pm.sets(n="rig_deformers_grp", em=True)
        defset = pm.PyNode("rig_deformers_grp")

    #####################
    # Curves creation
    #####################

    # get extreme position using the outer loop
    extr_v = meshNavigation.getExtremeVertexFromLoop(eLoop)
    upPos = extr_v[0]
    lowPos = extr_v[1]
    inPos = extr_v[2]
    outPos = extr_v[3]
    edgeList = extr_v[4]
    vertexList = extr_v[5]
    upPos = upVertex
    lowPos = lowVertex

    # upper crv
    upLip_edgeRange = meshNavigation.edgeRangeInLoopFromMid(edgeList,
                                                            upPos,
                                                            inPos,
                                                            outPos)
    upCrv = curve.createCuveFromEdges(upLip_edgeRange,
                                      setName("upperLip"),
                                      parent=lipsCrv_root)
    # store the closest vertex by curv cv index. To be use fo the auto skining
    upLip_closestVtxList = []
    # offset upper lip Curve
    cvs = upCrv.getCVs(space="world")
    for i, cv in enumerate(cvs):

        closestVtx = meshNavigation.getClosestVertexFromTransform(geo, cv)
        upLip_closestVtxList.append(closestVtx)
        if i == 0:
            # we know the curv starts from right to left
            offset = [cv[0] - thickness, cv[1], cv[2] - thickness]
        elif i == len(cvs) - 1:
            offset = [cv[0] + thickness, cv[1], cv[2] - thickness]
        else:
            offset = [cv[0], cv[1] + thickness, cv[2]]
        upCrv.setCV(i, offset, space='world')

    # lower crv
    lowLip_edgeRange = meshNavigation.edgeRangeInLoopFromMid(edgeList,
                                                             lowPos,
                                                             inPos,
                                                             outPos)
    lowCrv = curve.createCuveFromEdges(lowLip_edgeRange,
                                       setName("lowerLip"),
                                       parent=lipsCrv_root)
    lowLip_closestVtxList = []
    # offset lower lip Curve
    cvs = lowCrv.getCVs(space="world")
    for i, cv in enumerate(cvs):
        closestVtx = meshNavigation.getClosestVertexFromTransform(geo, cv)
        lowLip_closestVtxList.append(closestVtx)
        if i == 0:
            # we know the curv starts from right to left
            offset = [cv[0] - thickness, cv[1], cv[2] - thickness]
        elif i == len(cvs) - 1:
            offset = [cv[0] + thickness, cv[1], cv[2] - thickness]
        else:
            # we populate the closest vertext list here to skipt the first
            # and latest point
            offset = [cv[0], cv[1] - thickness, cv[2]]
        lowCrv.setCV(i, offset, space='world')

    upCrv_ctl = curve.createCurveFromCurve(upCrv,
                                           setName("upCtl_crv"),
                                           nbPoints=7,
                                           parent=lipsCrv_root)
    lowCrv_ctl = curve.createCurveFromCurve(lowCrv,
                                            setName("lowCtl_crv"),
                                            nbPoints=7,
                                            parent=lipsCrv_root)

    upRope = curve.createCurveFromCurve(upCrv,
                                        setName("upRope_crv"),
                                        nbPoints=NB_ROPE,
                                        parent=lipsCrv_root)
    lowRope = curve.createCurveFromCurve(lowCrv,
                                         setName("lowRope_crv"),
                                         nbPoints=NB_ROPE,
                                         parent=lipsCrv_root)

    upCrv_upv = curve.createCurveFromCurve(upCrv,
                                           setName("upCrv_upv"),
                                           nbPoints=7,
                                           parent=lipsCrv_root)
    lowCrv_upv = curve.createCurveFromCurve(lowCrv,
                                            setName("lowCrv_upv"),
                                            nbPoints=7,
                                            parent=lipsCrv_root)

    upRope_upv = curve.createCurveFromCurve(upCrv,
                                            setName("upRope_upv"),
                                            nbPoints=NB_ROPE,
                                            parent=lipsCrv_root)
    lowRope_upv = curve.createCurveFromCurve(lowCrv,
                                             setName("lowRope_upv"),
                                             nbPoints=NB_ROPE,
                                             parent=lipsCrv_root)

    # offset upv curves

    for crv in [upCrv_upv, lowCrv_upv, upRope_upv, lowRope_upv]:
        cvs = crv.getCVs(space="world")
        for i, cv in enumerate(cvs):

            # we populate the closest vertext list here to skipt the first
            # and latest point
            offset = [cv[0], cv[1], cv[2] + FRONT_OFFSET]
            crv.setCV(i, offset, space='world')

    rigCrvs = [upCrv,
               lowCrv,
               upCrv_ctl,
               lowCrv_ctl,
               upRope,
               lowRope,
               upCrv_upv,
               lowCrv_upv,
               upRope_upv,
               lowRope_upv]

    for crv in rigCrvs:
        crv.attr("visibility").set(False)

    ##################
    # Controls
    ##################

    # Controls lists
    upControls = []
    upVec = []
    upNpo = []
    lowControls = []
    lowVec = []
    lowNpo = []
    # controls options
    axis_list = ["sx", "sy", "sz", "ro"]
    upCtlOptions = [["corner", "R", "square", 4, .05, axis_list],
                    ["upOuter", "R", "circle", 14, .03, []],
                    ["upInner", "R", "circle", 14, .03, []],
                    ["upper", "C", "square", 4, .05, axis_list],
                    ["upInner", "L", "circle", 14, .03, []],
                    ["upOuter", "L", "circle", 14, .03, []],
                    ["corner", "L", "square", 4, .05, axis_list]]

    lowCtlOptions = [["lowOuter", "R", "circle", 14, .03, []],
                     ["lowInner", "R", "circle", 14, .03, []],
                     ["lower", "C", "square", 4, .05, axis_list],
                     ["lowInner", "L", "circle", 14, .03, []],
                     ["lowOuter", "L", "circle", 14, .03, []]]

    params = ["tx", "ty", "tz"]

    # upper controls
    cvs = upCrv_ctl.getCVs(space="world")
    pm.progressWindow(title='Upper controls', progress=0, max=len(cvs))

    v0 = transform.getTransformFromPos(cvs[0])
    v1 = transform.getTransformFromPos(cvs[-1])
    distSize = vector.getDistance(v0, v1) * 3
    # print distSize

    for i, cv in enumerate(cvs):
        pm.progressWindow(e=True,
                          step=1,
                          status='\nCreating control for%s' % cv)
        t = transform.getTransformFromPos(cv)

        oName = upCtlOptions[i][0]
        oSide = upCtlOptions[i][1]
        o_icon = upCtlOptions[i][2]
        color = upCtlOptions[i][3]
        wd = upCtlOptions[i][4]
        oPar = upCtlOptions[i][5]
        npo = primitive.addTransform(lips_root,
                                     setName("%s_npo" % oName, oSide),
                                     t)
        upNpo.append(npo)
        ctl = icon.create(npo,
                          setName("%s_%s" % (oName, ctlName), oSide),
                          t,
                          icon=o_icon,
                          w=wd * distSize,
                          d=wd * distSize,
                          ro=datatypes.Vector(1.57079633, 0, 0),
                          po=datatypes.Vector(0, 0, .07 * distSize),
                          color=color)

        upControls.append(ctl)
        if len(ctlName.split("_")) == 2 and ctlName.split("_")[-1] == "ghost":
            pass
        else:
            pm.sets(ctlSet, add=ctl)
        attribute.setKeyableAttributes(ctl, params + oPar)

        upv = primitive.addTransform(ctl, setName("%s_upv" % oName, oSide), t)
        upv.attr("tz").set(FRONT_OFFSET)
        upVec.append(upv)
        if oSide == "R":
            npo.attr("sx").set(-1)
    pm.progressWindow(e=True, endProgress=True)

    # lower controls
    cvs = lowCrv_ctl.getCVs(space="world")
    pm.progressWindow(title='Lower controls', progress=0, max=len(cvs))

    for i, cv in enumerate(cvs[1:-1]):
        pm.progressWindow(e=True,
                          step=1,
                          status='\nCreating control for%s' % cv)

        t = transform.getTransformFromPos(cv)

        oName = lowCtlOptions[i][0]
        oSide = lowCtlOptions[i][1]
        o_icon = lowCtlOptions[i][2]
        color = lowCtlOptions[i][3]
        wd = lowCtlOptions[i][4]
        oPar = lowCtlOptions[i][5]
        npo = primitive.addTransform(lips_root,
                                     setName("%s_npo" % oName, oSide),
                                     t)
        lowNpo.append(npo)
        ctl = icon.create(npo,
                          setName("%s_%s" % (oName, ctlName), oSide),
                          t,
                          icon=o_icon,
                          w=wd * distSize,
                          d=wd * distSize,
                          ro=datatypes.Vector(1.57079633, 0, 0),
                          po=datatypes.Vector(0, 0, .07 * distSize),
                          color=color)
        lowControls.append(ctl)
        if len(ctlName.split("_")) == 2 and ctlName.split("_")[-1] == "ghost":
            pass
        else:
            pm.sets(ctlSet, add=ctl)
        attribute.setKeyableAttributes(ctl, params + oPar)

        upv = primitive.addTransform(ctl, setName("%s_upv" % oName, oSide), t)
        upv.attr("tz").set(FRONT_OFFSET)
        lowVec.append(upv)
        if oSide == "R":
            npo.attr("sx").set(-1)
    pm.progressWindow(e=True, endProgress=True)

    # reparentig controls
    pm.parent(upNpo[1], lowNpo[0], upControls[0])
    pm.parent(upNpo[2], upNpo[4], upControls[3])
    pm.parent(upNpo[-2], lowNpo[-1], upControls[-1])
    pm.parent(lowNpo[1], lowNpo[3], lowControls[2])

    # Connecting control crvs with controls
    applyop.gear_curvecns_op(upCrv_ctl, upControls)
    applyop.gear_curvecns_op(lowCrv_ctl,
                             [upControls[0]] + lowControls + [upControls[-1]])

    applyop.gear_curvecns_op(upCrv_upv, upVec)
    applyop.gear_curvecns_op(lowCrv_upv, [upVec[0]] + lowVec + [upVec[-1]])

    # adding wires
    pm.wire(upCrv, w=upCrv_ctl, dropoffDistance=[0, 1000])
    pm.wire(lowCrv, w=lowCrv_ctl, dropoffDistance=[0, 1000])
    pm.wire(upRope, w=upCrv_ctl, dropoffDistance=[0, 1000])
    pm.wire(lowRope, w=lowCrv_ctl, dropoffDistance=[0, 1000])

    pm.wire(upRope_upv, w=upCrv_upv, dropoffDistance=[0, 1000])
    pm.wire(lowRope_upv, w=lowCrv_upv, dropoffDistance=[0, 1000])

    # setting constrains
    # up
    cns_node = pm.parentConstraint(upControls[0],
                                   upControls[3],
                                   upControls[1].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(upControls[0].name() + "W0").set(.75)
    cns_node.attr(upControls[3].name() + "W1").set(.25)
    cns_node.interpType.set(0) # noFlip

    cns_node = pm.parentConstraint(upControls[0],
                                   upControls[3],
                                   upControls[2].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(upControls[0].name() + "W0").set(.25)
    cns_node.attr(upControls[3].name() + "W1").set(.75)
    cns_node.interpType.set(0) # noFlip

    cns_node = pm.parentConstraint(upControls[3],
                                   upControls[6],
                                   upControls[4].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(upControls[3].name() + "W0").set(.75)
    cns_node.attr(upControls[6].name() + "W1").set(.25)
    cns_node.interpType.set(0) # noFlip

    cns_node = pm.parentConstraint(upControls[3],
                                   upControls[6],
                                   upControls[5].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(upControls[3].name() + "W0").set(.25)
    cns_node.attr(upControls[6].name() + "W1").set(.75)
    cns_node.interpType.set(0) # noFlip

    # low
    cns_node = pm.parentConstraint(upControls[0],
                                   lowControls[2],
                                   lowControls[0].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(upControls[0].name() + "W0").set(.75)
    cns_node.attr(lowControls[2].name() + "W1").set(.25)
    cns_node.interpType.set(0) # noFlip

    cns_node = pm.parentConstraint(upControls[0],
                                   lowControls[2],
                                   lowControls[1].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(upControls[0].name() + "W0").set(.25)
    cns_node.attr(lowControls[2].name() + "W1").set(.75)
    cns_node.interpType.set(0) # noFlip

    cns_node = pm.parentConstraint(lowControls[2],
                                   upControls[6],
                                   lowControls[3].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(lowControls[2].name() + "W0").set(.75)
    cns_node.attr(upControls[6].name() + "W1").set(.25)
    cns_node.interpType.set(0) # noFlip

    cns_node = pm.parentConstraint(lowControls[2],
                                   upControls[6],
                                   lowControls[4].getParent(),
                                   mo=True,
                                   skipRotate=["x", "y", "z"])
    cns_node.attr(lowControls[2].name() + "W0").set(.25)
    cns_node.attr(upControls[6].name() + "W1").set(.75)
    cns_node.interpType.set(0) # noFlip

    ##################
    # Joints
    ##################

    lvlType = "transform"

    # upper joints
    upperJoints = []
    cvs = upCrv.getCVs(space="world")
    pm.progressWindow(title='Creating Upper Joints', progress=0, max=len(cvs))

    for i, cv in enumerate(cvs):
        pm.progressWindow(e=True,
                          step=1,
                          status='\nCreating Joint for  %s' % cv)
        oTransUpV = pm.PyNode(pm.createNode(
            lvlType,
            n=setName("upLipRopeUpv", idx=str(i).zfill(3)),
            p=lipsRope_root,
            ss=True))
        oTrans = pm.PyNode(
            pm.createNode(lvlType,
                          n=setName("upLipRope", idx=str(i).zfill(3)),
                          p=lipsRope_root, ss=True))

        oParam, oLength = curve.getCurveParamAtPosition(upRope, cv)
        uLength = curve.findLenghtFromParam(upRope, oParam)
        u = uLength / oLength

        applyop.pathCns(
            oTransUpV, upRope_upv, cnsType=False, u=u, tangent=False)

        cns = applyop.pathCns(
            oTrans, upRope, cnsType=False, u=u, tangent=False)

        cns.setAttr("worldUpType", 1)
        cns.setAttr("frontAxis", 0)
        cns.setAttr("upAxis", 1)

        pm.connectAttr(oTransUpV.attr("worldMatrix[0]"),
                       cns.attr("worldUpMatrix"))

        # getting joint parent
        if headJnt and isinstance(headJnt, string_types):
            try:
                j_parent = pm.PyNode(headJnt)
            except pm.MayaNodeError:
                j_parent = False
        elif headJnt and isinstance(headJnt, pm.PyNode):
            j_parent = headJnt
        else:
            j_parent = False

        jnt = rigbits.addJnt(oTrans, noReplace=True, parent=j_parent)
        upperJoints.append(jnt)
        pm.sets(defset, add=jnt)
    pm.progressWindow(e=True, endProgress=True)

    # lower joints
    lowerJoints = []
    cvs = lowCrv.getCVs(space="world")
    pm.progressWindow(title='Creating Lower Joints', progress=0, max=len(cvs))

    for i, cv in enumerate(cvs):
        pm.progressWindow(e=True,
                          step=1,
                          status='\nCreating Joint for  %s' % cv)
        oTransUpV = pm.PyNode(pm.createNode(
            lvlType,
            n=setName("lowLipRopeUpv", idx=str(i).zfill(3)),
            p=lipsRope_root,
            ss=True))

        oTrans = pm.PyNode(pm.createNode(
            lvlType,
            n=setName("lowLipRope", idx=str(i).zfill(3)),
            p=lipsRope_root,
            ss=True))

        oParam, oLength = curve.getCurveParamAtPosition(lowRope, cv)
        uLength = curve.findLenghtFromParam(lowRope, oParam)
        u = uLength / oLength

        applyop.pathCns(oTransUpV,
                        lowRope_upv,
                        cnsType=False,
                        u=u,
                        tangent=False)
        cns = applyop.pathCns(oTrans,
                              lowRope,
                              cnsType=False,
                              u=u,
                              tangent=False)

        cns.setAttr("worldUpType", 1)
        cns.setAttr("frontAxis", 0)
        cns.setAttr("upAxis", 1)

        pm.connectAttr(oTransUpV.attr("worldMatrix[0]"),
                       cns.attr("worldUpMatrix"))

        # getting joint parent
        if jawJnt and isinstance(jawJnt, string_types):
            try:
                j_parent = pm.PyNode(jawJnt)
            except pm.MayaNodeError:
                pass
        elif jawJnt and isinstance(jawJnt, pm.PyNode):
            j_parent = jawJnt
        else:
            j_parent = False
        jnt = rigbits.addJnt(oTrans, noReplace=True, parent=j_parent)
        lowerJoints.append(jnt)
        pm.sets(defset, add=jnt)
    pm.progressWindow(e=True, endProgress=True)

    ###########################################
    # Connecting rig
    ###########################################
    if parent:
        try:
            if isinstance(parent, string_types):
                parent = pm.PyNode(parent)
            parent.addChild(lips_root)
        except pm.MayaNodeError:
            pm.displayWarning("The Lips rig can not be parent to: %s. Maybe "
                              "this object doesn't exist." % parent)
    if headJnt and jawJnt:
        try:
            if isinstance(headJnt, string_types):
                headJnt = pm.PyNode(headJnt)
        except pm.MayaNodeError:
            pm.displayWarning("Head Joint or Upper Lip Joint %s. Can not be "
                              "fount in the scene" % headJnt)
            return
        try:
            if isinstance(jawJnt, string_types):
                jawJnt = pm.PyNode(jawJnt)
        except pm.MayaNodeError:
            pm.displayWarning("Jaw Joint or Lower Lip Joint %s. Can not be "
                              "fount in the scene" % jawJnt)
            return

        # in order to avoid flips lets create a reference transform
        # also to avoid flips, set any multi target parentConstraint to noFlip
        ref_cns_list = []
        for cns_ref in [headJnt, jawJnt]:

            t = transform.getTransformFromPos(
                cns_ref.getTranslation(space='world'))
            ref = pm.createNode("transform",
                                n=cns_ref.name() + "_cns",
                                p=cns_ref,
                                ss=True)
            ref.setMatrix(t, worldSpace=True)
            ref_cns_list.append(ref)
        # right corner connection
        cns_node = pm.parentConstraint(ref_cns_list[0],
                            ref_cns_list[1],
                            upControls[0].getParent(),
                            mo=True)
        cns_node.interpType.set(0) # noFlip
        # left corner connection
        cns_node = pm.parentConstraint(ref_cns_list[0],
                            ref_cns_list[1],
                            upControls[-1].getParent(),
                            mo=True)
        cns_node.interpType.set(0) # noFlip
        # up control connection
        cns_node = pm.parentConstraint(headJnt,
                            upControls[3].getParent(),
                            mo=True)
        # low control connection
        cns_node = pm.parentConstraint(jawJnt,
                            lowControls[2].getParent(),
                            mo=True)

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
        if headJnt:
            try:
                headJnt = pm.PyNode(headJnt)
            except pm.MayaNodeError:
                pm.displayWarning(
                    "Auto skin aborted can not find %s " % headJnt)
                return

        # Check if the object has a skinCluster
        objName = pm.listRelatives(geo, parent=True)[0]

        skinCluster = skin.getSkinCluster(objName)
        if not skinCluster:
            skinCluster = pm.skinCluster(headJnt,
                                         geo,
                                         tsb=True,
                                         nw=2,
                                         n='skinClsEyelid')

        lipsJoints = upperJoints + lowerJoints
        closestVtxList = upLip_closestVtxList + lowLip_closestVtxList
        pm.progressWindow(title='Auto skinning process',
                          progress=0,
                          max=len(lipsJoints))

        for i, jnt in enumerate(lipsJoints):
            pm.progressWindow(e=True, step=1, status='\nSkinning %s' % jnt)
            skinCluster.addInfluence(jnt, weight=0)
            v = closestVtxList[i]
            for row in vertexRowList:
                if v in row:
                    for i, rv in enumerate(row):
                        # find the deformer with max value for each vertex
                        w = pm.skinPercent(skinCluster,
                                           rv,
                                           query=True,
                                           value=True)
                        transJoint = pm.skinPercent(skinCluster,
                                                    rv,
                                                    query=True,
                                                    t=None)
                        max_value = max(w)
                        max_index = w.index(max_value)

                        perc = skinPercList[i]
                        t_value = [(jnt, perc),
                                   (transJoint[max_index], 1.0 - perc)]
                        pm.skinPercent(skinCluster,
                                       rv,
                                       transformValue=t_value)
        pm.progressWindow(e=True, endProgress=True)


##########################################################
# Lips Rig UI
##########################################################

class lipRigUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(lipRigUI, self).__init__(parent)
        self.create()

    def create(self):

        self.setWindowTitle("Rigbits: Lips Rigger")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)

        self.create_controls()
        self.create_layout()
        self.create_connections()

    def create_controls(self):

        # Geometry input controls
        self.geometryInput_group = QtWidgets.QGroupBox("Geometry Input")
        self.edgeloop_label = QtWidgets.QLabel("Edge Loop:")
        self.edgeloop_lineEdit = QtWidgets.QLineEdit()
        self.edgeloop_button = QtWidgets.QPushButton("<<")
        self.upVertex_label = QtWidgets.QLabel("Upper Vertex:")
        self.upVertex_lineEdit = QtWidgets.QLineEdit()
        self.upVertex_button = QtWidgets.QPushButton("<<")
        self.lowVertex_label = QtWidgets.QLabel("Lower Vertex:")
        self.lowVertex_lineEdit = QtWidgets.QLineEdit()
        self.lowVertex_button = QtWidgets.QPushButton("<<")

        # Name prefix
        self.prefix_group = QtWidgets.QGroupBox("Name Prefix")
        self.prefix_lineEdit = QtWidgets.QLineEdit()
        self.prefix_lineEdit.setText("lips")

        # control extension
        self.control_group = QtWidgets.QGroupBox("Control Name Extension")
        self.control_lineEdit = QtWidgets.QLineEdit()
        self.control_lineEdit.setText("ctl")

        # joints
        self.joints_group = QtWidgets.QGroupBox("Joints")
        self.headJnt_label = QtWidgets.QLabel("Head or Upper Lip Joint:")
        self.headJnt_lineEdit = QtWidgets.QLineEdit()
        self.headJnt_button = QtWidgets.QPushButton("<<")
        self.jawJnt_label = QtWidgets.QLabel("Jaw or Lower Lip Joint:")
        self.jawJnt_lineEdit = QtWidgets.QLineEdit()
        self.jawJnt_button = QtWidgets.QPushButton("<<")

        # Topological Autoskin
        self.topoSkin_group = QtWidgets.QGroupBox("Skin")
        self.rigidLoops_label = QtWidgets.QLabel("Rigid Loops:")
        self.rigidLoops_value = QtWidgets.QSpinBox()
        self.rigidLoops_value.setRange(0, 30)
        self.rigidLoops_value.setSingleStep(1)
        self.rigidLoops_value.setValue(5)
        self.falloffLoops_label = QtWidgets.QLabel("Falloff Loops:")
        self.falloffLoops_value = QtWidgets.QSpinBox()
        self.falloffLoops_value.setRange(0, 30)
        self.falloffLoops_value.setSingleStep(1)
        self.falloffLoops_value.setValue(8)

        self.topSkin_check = QtWidgets.QCheckBox(
            'Compute Topological Autoskin')
        self.topSkin_check.setChecked(True)

        # Options
        self.options_group = QtWidgets.QGroupBox("Options")
        self.lipThickness_label = QtWidgets.QLabel("Lips Thickness:")
        self.lipThickness_value = QtWidgets.QDoubleSpinBox()
        self.lipThickness_value.setRange(0, 10)
        self.lipThickness_value.setSingleStep(.01)
        self.lipThickness_value.setValue(.03)
        self.parent_label = QtWidgets.QLabel("Static Rig Parent:")
        self.parent_lineEdit = QtWidgets.QLineEdit()
        self.parent_button = QtWidgets.QPushButton("<<")
        # Build button
        self.build_button = QtWidgets.QPushButton("Build Lips Rig")
        self.export_button = QtWidgets.QPushButton("Export Config to json")

    def create_layout(self):

        # Edge Loop Layout
        edgeloop_layout = QtWidgets.QHBoxLayout()
        edgeloop_layout.setContentsMargins(1, 1, 1, 1)
        edgeloop_layout.addWidget(self.edgeloop_label)
        edgeloop_layout.addWidget(self.edgeloop_lineEdit)
        edgeloop_layout.addWidget(self.edgeloop_button)

        # Outer Edge Loop Layout
        upVertex_layout = QtWidgets.QHBoxLayout()
        upVertex_layout.setContentsMargins(1, 1, 1, 1)
        upVertex_layout.addWidget(self.upVertex_label)
        upVertex_layout.addWidget(self.upVertex_lineEdit)
        upVertex_layout.addWidget(self.upVertex_button)

        # inner Edge Loop Layout
        lowVertex_layout = QtWidgets.QHBoxLayout()
        lowVertex_layout.setContentsMargins(1, 1, 1, 1)
        lowVertex_layout.addWidget(self.lowVertex_label)
        lowVertex_layout.addWidget(self.lowVertex_lineEdit)
        lowVertex_layout.addWidget(self.lowVertex_button)

        # Geometry Input Layout
        geometryInput_layout = QtWidgets.QVBoxLayout()
        geometryInput_layout.setContentsMargins(6, 1, 6, 2)
        geometryInput_layout.addLayout(edgeloop_layout)
        geometryInput_layout.addLayout(upVertex_layout)
        geometryInput_layout.addLayout(lowVertex_layout)
        self.geometryInput_group.setLayout(geometryInput_layout)

        # joints Layout
        headJnt_layout = QtWidgets.QHBoxLayout()
        headJnt_layout.addWidget(self.headJnt_label)
        headJnt_layout.addWidget(self.headJnt_lineEdit)
        headJnt_layout.addWidget(self.headJnt_button)

        jawJnt_layout = QtWidgets.QHBoxLayout()
        jawJnt_layout.addWidget(self.jawJnt_label)
        jawJnt_layout.addWidget(self.jawJnt_lineEdit)
        jawJnt_layout.addWidget(self.jawJnt_button)

        joints_layout = QtWidgets.QVBoxLayout()
        joints_layout.setContentsMargins(6, 4, 6, 4)
        joints_layout.addLayout(headJnt_layout)
        joints_layout.addLayout(jawJnt_layout)
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
        topoSkin_layout.addLayout(headJnt_layout)
        topoSkin_layout.addLayout(jawJnt_layout)
        self.topoSkin_group.setLayout(topoSkin_layout)

        # Options Layout
        lipThickness_layout = QtWidgets.QHBoxLayout()
        lipThickness_layout.addWidget(self.lipThickness_label)
        lipThickness_layout.addWidget(self.lipThickness_value)
        parent_layout = QtWidgets.QHBoxLayout()
        parent_layout.addWidget(self.parent_label)
        parent_layout.addWidget(self.parent_lineEdit)
        parent_layout.addWidget(self.parent_button)
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.setContentsMargins(6, 1, 6, 2)
        options_layout.addLayout(lipThickness_layout)
        # options_layout.addLayout(offset_layout)
        options_layout.addLayout(parent_layout)
        self.options_group.setLayout(options_layout)

        # Name prefix
        namePrefix_layout = QtWidgets.QHBoxLayout()
        namePrefix_layout.setContentsMargins(1, 1, 1, 1)
        namePrefix_layout.addWidget(self.prefix_lineEdit)
        self.prefix_group.setLayout(namePrefix_layout)

        # Control Name Extension
        controlExtension_layout = QtWidgets.QHBoxLayout()
        controlExtension_layout.setContentsMargins(1, 1, 1, 1)
        controlExtension_layout.addWidget(self.control_lineEdit)
        self.control_group.setLayout(controlExtension_layout)

        # Main Layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self.prefix_group)
        main_layout.addWidget(self.control_group)
        main_layout.addWidget(self.geometryInput_group)
        main_layout.addWidget(self.options_group)
        main_layout.addWidget(self.joints_group)
        main_layout.addWidget(self.topoSkin_group)
        main_layout.addWidget(self.build_button)
        main_layout.addWidget(self.export_button)

        self.setLayout(main_layout)

    def create_connections(self):
        self.edgeloop_button.clicked.connect(partial(self.populate_edgeloop,
                                                     self.edgeloop_lineEdit))
        self.upVertex_button.clicked.connect(partial(self.populate_element,
                                                     self.upVertex_lineEdit,
                                                     "vertex"))
        self.lowVertex_button.clicked.connect(partial(self.populate_element,
                                                      self.lowVertex_lineEdit,
                                                      "vertex"))

        self.parent_button.clicked.connect(partial(self.populate_element,
                                                   self.parent_lineEdit))

        self.headJnt_button.clicked.connect(partial(self.populate_element,
                                                    self.headJnt_lineEdit,
                                                    "joint"))
        self.jawJnt_button.clicked.connect(partial(self.populate_element,
                                                   self.jawJnt_lineEdit,
                                                   "joint"))

        self.build_button.clicked.connect(self.buildRig)
        self.export_button.clicked.connect(self.exportDict)

    # SLOTS ##########################################################

    # TODO: create a checker to ensure that the vertex selected are part of
    # the main edgelopp
    def populate_element(self, lEdit, oType="transform"):
        if oType == "joint":
            oTypeInst = pm.nodetypes.Joint
        elif oType == "vertex":
            oTypeInst = pm.MeshVertex
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

    def populate_edgeloop(self, lineEdit):
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
                pm.displayWarning("Please select first the edge loop.")
            elif len(edgeList.split(",")) < 4:
                pm.displayWarning("The minimun edge count is 4")
            else:
                lineEdit.setText(edgeList)

        else:
            pm.displayWarning("Please select first the edge loop.")

    def populateDict(self):
        self.buildDict = {}
        self.buildDict["lips"] = [self.edgeloop_lineEdit.text(),
                                  self.upVertex_lineEdit.text(),
                                  self.lowVertex_lineEdit.text(),
                                  self.prefix_lineEdit.text(),
                                  self.lipThickness_value.value(),
                                  self.topSkin_check.isChecked(),
                                  self.rigidLoops_value.value(),
                                  self.falloffLoops_value.value(),
                                  self.headJnt_lineEdit.text(),
                                  self.jawJnt_lineEdit.text(),
                                  self.parent_lineEdit.text(),
                                  self.control_lineEdit.text()]

    def buildRig(self):
        self.populateDict()
        lipsRig(*self.buildDict["lips"])

    def exportDict(self):
        self.populateDict()

        data_string = json.dumps(self.buildDict, indent=4, sort_keys=True)
        filePath = pm.fileDialog2(
            fileMode=0,
            fileFilter='Lips Rigger Configuration .lips (*%s)' % ".lips")
        if not filePath:
            return
        if not isinstance(filePath, string_types):
            filePath = filePath[0]
        f = open(filePath, 'w')
        f.write(data_string)
        f.close()


# build lips from json file:
def lipsFromfile(path):
    buildDict = json.load(open(path))
    lipsRig(*buildDict["lips"])


def showLipRigUI(*args):
    gqt.showDialog(lipRigUI)


if __name__ == "__main__":
    showLipRigUI()
