# -*- coding: utf-8 -*-

import json
import os
import re

import pymel.core as pm

from mgear.core import primitive
from mgear.core import attribute
from mgear.core.attribute import ParamDef2, enumParamDef


class Gimmick(object):
    GUIDE = "guide"
    BLEND = "Blend"
    SUPPORT = "Support"
    SLIDE = "Slide"
    GIMMICK_TYPE = (BLEND, SUPPORT, SLIDE)

    SETS = "rig_gimmick_grp"
    SIDE_LABEL = ("Center", "Left", "Right", "None")

    ATTR = dict(type="gimmickType", side="gimmickSide", parent="parentTarget")

    def convert_num_to_gimmickType(self, num):
        gimmickType = None
        if num == 0:
            gimmickType = self.BLEND
        elif num == 1:
            gimmickType = self.SUPPORT

        return gimmickType

    def getNameRulePattern(self, guide=None):
        guideNode = None
        if not guide:
            if not pm.objExists("guide.joint_name_rule"):
                pm.displayWarning("there's no joint_name_rule attr on the guide")
            guideNode = pm.PyNode(self.GUIDE)
        else:
            guideNode = guide

        nameRule = guideNode.attr("joint_name_rule").get()
        sideL = guideNode.attr("side_joint_left_name").get()
        sideR = guideNode.attr("side_joint_right_name").get()
        sideC = guideNode.attr("side_joint_center_name").get()
        sideAll = "|".join([sideL, sideR, sideC])
        jntExt = guideNode.attr("joint_name_ext").get()

        patternDict = dict(component="(?P<component>.*?)", side="(?P<side>{})".format(sideAll),
                           index="(?P<index>\d*)", description="(?P<description>.*?)",
                           extension="(?P<extension>{})".format(jntExt))

        pattern = nameRule.format(**patternDict)
        return pattern

    def getGimmickType(self, gType, joint=None, **kwargs):
        """Get gimmick type from joint node

        Args:
            joint ([type], optional): [pm.nodeType.Joint]. Defaults to None.
            type ([type], optional): ["blend" or "support"]. Defaults to None.

        Returns:
            [list]: [description]
        """
        gimmicks = {self.BLEND: {"Center": [], "Left": [], "Right": [], "None": []},
                    self.SUPPORT: {"Center": [], "Left": [], "Right": [], "None": []}}

        if not joint:
            nodes = pm.ls("*.{}".format(self.ATTR["type"]))
            if len(nodes) == 0:
                pm.displayWarning("There're no gimmick joint in this scene")
                return None

            for node in nodes:
                nodeName = node.split(".")[0]
                node = pm.PyNode(nodeName)

                if not node.hasAttr(self.ATTR["side"]):
                    pm.displayWarning("There're no side attribute on {}".format(node))
                    continue

                gtypeNum = node.attr(self.ATTR["type"]).get()
                gtype = self.convert_num_to_gimmickType(gtypeNum)

                if gtype is None:
                    continue

                sideLabel = node.attr(self.ATTR["side"]).get()
                if sideLabel == 0:
                    gimmicks[gtype]["Center"].append(nodeName)
                elif sideLabel == 1:
                    gimmicks[gtype]["Left"].append(nodeName)
                elif sideLabel == 2:
                    gimmicks[gtype]["Right"].append(nodeName)
                elif sideLabel == 3:
                    gimmicks[gtype]["None"].append(nodeName)

        return gimmicks[gType]

    def storeInfo(self, gimmickJnt, typeValue, joint=None, side=None, parent=None):
        gtype = enumParamDef(self.ATTR["type"], self.GIMMICK_TYPE, value=typeValue)
        gtype.create(gimmickJnt)

        if side is None:
            side = self.getSideLabel(joint)
        if parent is None:
            parent = ""

        sideParam = enumParamDef(self.ATTR["side"], self.SIDE_LABEL, value=side)
        sideParam.create(gimmickJnt)

        parentParam = ParamDef2(self.ATTR["parent"], "string", parent)
        parentParam.create(gimmickJnt)


class GimmickBuilder(Gimmick):

    def __init__(self):
        pass


class GimmickJoint(Gimmick):

    def __init__(self, joint=None, infType=None, **kwargs):
        self.infType = infType
        self.joint = self.setSourceJoint(joint)

        self.side = kwargs.get('side', kwargs.get('si', None))
        self.parent = kwargs.get('infParent', kwargs.get('if', None))
        self.multiply = kwargs.get('multiply', kwargs.get('multi', 2.0))

    def _convert_number(self, base_name):
        count = 0
        while True:
            name = base_name.replace('#', str(count + 1))
            if pm.objExists(name):
                count += 1
            else:
                break
        return name

    def getSideLabel(self, jnt, guide=None):
        if not guide:
            guide = self.GUIDE

        sideL = guide.attr("side_joint_left_name").get()
        sideR = guide.attr("side_joint_right_name").get()
        sideC = guide.attr("side_joint_center_name").get()

        sideInfo = {sideC: "Center",
                    sideL: "Left",
                    sideR: "Right",
                    "None": "None"}

        pattern = self.getNameRulePattern()
        match_result = re.match(pattern, jnt)
        if match_result:
            side = match_result.group("side")
        else:
            side = "None"
        return sideInfo.get(side)

    def swapSideName(self, name, guide=None):
        if not guide:
            guide = pm.PyNode(self.GUIDE)

        sideL = guide.attr("side_joint_left_name").get()
        sideR = guide.attr("side_joint_right_name").get()
        sideC = guide.attr("side_joint_center_name").get()
        pattern = self.getNameRulePattern()

        match_result = re.match(pattern, name)
        if not match_result:
            return

        index = match_result.group("index")
        
        swapName = []
        pat = re.compile("_(L|R|C)+\d")
        if match_result.group("side") == sideL:
            swapName.append(pat.sub("_{}{}".format(sideR, index), name))
        elif match_result.group("side") == sideR:
            swapName.append(pat.sub("_{}{}".format(sideL, index), name))
        elif match_result.group("side") == sideC:
            swapName.append(name)
        return swapName[0]

    def setSourceJoint(self, joint):
        jointList = []
        if joint is None:
            joints = pm.selected(type='joint')
            if len(joints) == 0:
                jointList = None
            else:
                jointList.extend(joints)

        elif isinstance(joint, str):
            jointList.append(joint)

        elif not isinstance(joint, pm.nodetypes.Joint):
            jnts = []
            for jnt in joint:
                jnts.append(pm.PyNode(jnt))
            jointList.extend(jnts)

        else:
            jointList.append(joint)
        return jointList

    def createGimmickBase(self, joint, sideName, infType):
        """Create a blend joint under the selected joint.
        """
        # get a series of joint-selected infomations
        rad = joint.getRadius()
        pos = joint.getTranslation(space="world")
        rot = joint.getRotation(space="world", quaternion=True)

        if infType == self.BLEND:
            # generates a specific name
            name = '{}_{}'.format(joint, infType.lower())

            # add a joint with pos selected target
            gimmickParent = joint.getParent()
            gimmickJnt = primitive.addJoint(None, name)
            gimmickJnt.setTranslation(pos, space="world")
            gimmickJnt.setOrientation(rot)
            gimmickJnt.setParent(gimmickParent)
            gimmickJnt.attr("overrideEnabled").set(1)
            gimmickJnt.attr("overrideColor").set(15)
            gimmickJnt.attr("radius").set(rad * self.multiply)

        elif infType == self.SUPPORT:
            # generates a specific name
            preName = joint.replace(self.BLEND.lower(), '{}#'.format(self.SUPPORT.lower()))
            name = self.__convert_number(preName)

            # add a joint with pos selected target
            gimmickJnt = primitive.addJoint(None, name)
            gimmickJnt.setTranslation(pos, space="world")
            gimmickJnt.setParent(joint)
            gimmickJnt.rotate.set(0, 0, 0)
            gimmickJnt.jointOrient.set(0, 0, 0)
            gimmickJnt.attr("overrideEnabled").set(1)
            gimmickJnt.attr("overrideColor").set(28)
            gimmickJnt.attr("radius").set(rad)
            gimmickParent = gimmickJnt.getParent()

        self.storeInfo(gimmickJnt,
                       infType,
                       joint.name(),
                       side=sideName,
                       parent=gimmickParent)

        return gimmickJnt

    def addGimmickToSets(self, gimmicks):
        # add the blend joint list to the specific sets
        setName = self.SETS

        pm.select(cl=True)
        if not pm.objExists(setName):
            pm.sets(n=setName)
            pm.sets("rig_sets_grp", add=setName)

        for gimmick in gimmicks:
            pm.sets(setName, add=gimmick.name())

    def select(self, gtype, side=None):
        gimmickDict = self.getGimmickType(gtype)
        if side:
            gimmickJnts = gimmickDict[side]
        else:
            gimmickJnts = gimmickDict.values()
        pm.select(gimmickJnts)
        return gimmickJnts


class GimmickBlend(GimmickJoint):
    TYPE = "Blend"

    def __init__(self, joint=None, side="Left", **kwargs):
        GimmickJoint.__init__(self,
                              joint=joint,
                              infType=self.TYPE,
                              side=side,
                              **kwargs)
        
        self.outlineColor = (0.25, 0.35, 1.0)
        self.overrideColor = 17

    def generateBase(self, jnt, parent):
        # get a series of joint-selected information
        rad = jnt.getRadius()
        pos = jnt.getTranslation(space="world")
        rot = jnt.getRotation(space="world", quaternion=True)

        # generates a specific name
        name = '{}_{}'.format(jnt, self.TYPE.lower())

        # add a joint with pos selected target
        gimmickJnt = primitive.addJoint(None, name)
        gimmickJnt.setTranslation(pos, space="world")
        gimmickJnt.setOrientation(rot)
        gimmickJnt.setParent(parent)
        gimmickJnt.attr("overrideEnabled").set(True)
        gimmickJnt.attr("useOutlinerColor").set(True)
        gimmickJnt.attr("outlinerColor").set(self.outlineColor)
        gimmickJnt.attr("overrideColor").set(self.overrideColor)
        gimmickJnt.attr("radius").set(rad * self.multiply)
        return gimmickJnt

    def create(self, joint=None, **kwargs):
        if not joint:
            joint = self.joint
        
        blend = kwargs.get('blend', kwargs.get('bl', 0.5))
        select = kwargs.get('select', kwargs.get('sl', False))
        sets = kwargs.get('set', kwargs.get('st', False))

        nodes = {}
        for jnt in joint:
            gimmickParent = jnt.getParent()
            blendJnt = self.generateBase(jnt, gimmickParent)
            
            self.storeInfo(blendJnt,
                           self.TYPE,
                           joint=jnt.name(),
                           side=self.side,
                           parent=gimmickParent)
            nodes[jnt] = blendJnt
        self.setup(blendJntDict=nodes)

        if sets:
            self.addGimmickToSets(nodes.values())
        
        if select:
            self.select(self.TYPE)    
        
        return nodes

    def setup(self, blendJntDict=None, **kwargs):
        blend = kwargs.get('blend', kwargs.get('bl', 0.5))
        compScale = kwargs.get('compScale', kwargs.get('cs', True))
        
        for jnt, blendJnt in blendJntDict.items():
            weight = "weight"
            blendJnt.attr("visibility").set(k=False, cb=False)
            if not blendJnt.hasAttr(weight):
                blendJnt.addAttr(weight, at="float", min=0, max=1, dv=0.5, k=False)
                blendJnt.attr(weight).set(cb=True)

            # create a pairBlend for dividing rotation of driver joint
            blendNode = pm.createNode("pairBlend")
            blendNode.rename("{}_pairBlend".format(blendJnt))
            blendNode.attr("rotInterpolation").set(1)
            blendNode.attr("weight").set(blend)
            blendJnt.attr("segmentScaleCompensate").set(compScale)

            # connection process
            blendJnt.weight >> blendNode.weight
            jnt.translate >> blendNode.inTranslate1
            jnt.translate >> blendNode.inTranslate2
            jnt.rotate >> blendNode.inRotate1

            for xyz in "XYZ":
                pm.connectAttr(blendNode.attr("outTranslate{}".format(xyz)),
                                blendJnt.attr("translate{}".format(xyz)))
                pm.connectAttr(blendNode.attr("outRotate{}".format(xyz)),
                                blendJnt.attr("rotate{}".format(xyz)))
                pm.connectAttr(jnt.attr("scale{}".format(xyz)),
                                blendJnt.attr("scale{}".format(xyz)))

    def mirror(self, side="Left", **kwargs):
        mbBool = kwargs.get('mirrorBehavior', kwargs.get('mb', True))
        mxyBool = kwargs.get('mirrorXY', kwargs.get('mxy', False))
        mxzBool = kwargs.get('mirrorXZ', kwargs.get('mxz', False))
        myzBool = kwargs.get('mirrorYZ', kwargs.get('myz', True))

        if not self.joint:
            self.joint = self.getGimmickType(self.TYPE)[side]

        nodes = {}
        for gi in self.joint:
            jnt, _ = gi.rsplit("_", 1)
            giNode = pm.PyNode(gi)
            giNode.setParent(world=True)
            
            # mirror blendJoints
            mirrorGi = pm.mirrorJoint(gi, mb=mbBool, mxy=mxyBool, mxz=mxzBool, myz=myzBool)
            giNode.setParent(giNode.attr(self.ATTR["parent"]).get())
            mirrorGiNode = pm.PyNode(mirrorGi[0])
            mirrorGiNode.rename(self.swapSideName(gi))
            mirrorGiNode.attr(self.ATTR["side"]).set(2)
            mirrorGiNode.attr("useOutlinerColor").set(True)
            mirrorGiNode.attr("outlinerColor").set(self.outlineColor)
            mirrorParent = self.swapSideName(mirrorGiNode.attr(self.ATTR["parent"]).get())
            mirrorGiNode.attr(self.ATTR["parent"]).set(mirrorParent)
            mirrorGiNode.setParent(mirrorParent)
            
            # mirror supportJoints
            sidePair = zip(giNode.getChildren(), mirrorGiNode.getChildren())
            for left, right in sidePair:
                if not left or not right:
                    continue
                right.rename(self.swapSideName(left.name()))
                right.attr(self.ATTR["side"]).set(2)
                mirrorParent = self.swapSideName(left.attr(self.ATTR["parent"]).get())
                right.attr(self.ATTR["parent"]).set(mirrorParent)
            nodes[pm.PyNode(self.swapSideName(jnt))] = mirrorGiNode
        self.setup(blendJntDict=nodes)
        pm.select(cl=True)


class GimmickSupport(GimmickJoint):
    TYPE = "Support"

    def __init__(self, joint=None, side=None, **kwargs):
        if joint is None:
            joint = pm.selected()
            
        if side is None:
            side = "Left"
        
        GimmickJoint.__init__(self,
                              joint=joint,
                              infType=self.TYPE,
                              side=side,
                              **kwargs)
        
        self.outlineColor = (0.4, 0.6, 0.6)
        self.overrideColor = 17

    def generateBase(self, jnt):
        rad = jnt.getRadius()
        pos = jnt.getTranslation(space="world")
        rot = jnt.getRotation(space="world", quaternion=True)
        
        # generates a specific name
        preName = jnt.replace(self.BLEND.lower(), '{}#'.format(self.SUPPORT.lower()))
        name = self._convert_number(preName)

        # add a joint with pos selected target
        gimmickJnt = primitive.addJoint(None, name)
        gimmickJnt.setTranslation(pos, space="world")
        gimmickJnt.setParent(jnt)
        gimmickJnt.rotate.set(0, 0, 0)
        gimmickJnt.jointOrient.set(0, 0, 0)
        gimmickJnt.attr("overrideEnabled").set(True)
        gimmickJnt.attr("useOutlinerColor").set(True)
        gimmickJnt.attr("outlinerColor").set(self.outlineColor)
        gimmickJnt.attr("overrideColor").set(self.overrideColor)
        gimmickJnt.attr("radius").set(rad / self.multiply)
        return gimmickJnt

    def create(self):
        self.setSourceJoint(self.joint)
        
        gimmickJnts = []
        for jnt in self.joint:
            bindJnt = self.generateBase(jnt)

            self.storeInfo(bindJnt,
                           self.TYPE,
                           joint=jnt.name(),
                           side=self.side,
                           parent=jnt.name())
            gimmickJnts.append(bindJnt)
        
        self.addGimmickToSets(gimmickJnts)
        pm.select(gimmickJnts)

    def setup(self):
        pass
    
    def mirror(self, side="Left", gimmick=None, **kwargs):
        mbBool = kwargs.get('mirrorBehavior', kwargs.get('mb', True))
        mxyBool = kwargs.get('mirrorXY', kwargs.get('mxy', False))
        mxzBool = kwargs.get('mirrorXZ', kwargs.get('mxz', False))
        myzBool = kwargs.get('mirrorYZ', kwargs.get('myz', True))

        if not gimmick:
            gimmick = self.getGimmickType(self.TYPE)[side]

        nodes = {}
        for gi in gimmick:
            jnt, gtype = gi.rsplit("_", 1)
            giNode = pm.PyNode(gi)
            giNode.setParent(world=True)
            
            mirrorName = "{}_{}".format(self.swapSideName(jnt), gtype)
            mirrorGi = pm.mirrorJoint(gi, mb=mbBool, mxy=mxyBool, mxz=mxzBool, myz=myzBool)
            mirrorGiNode = pm.PyNode(mirrorGi[0])
            mirrorGiNode.rename(mirrorName)
            mirrorGiNode.attr(self.ATTR["side"]).set(2)
            mirrorParent = self.swapSideName(mirrorGiNode.attr(self.ATTR["parent"]).get())
            mirrorGiNode.attr(self.ATTR["parent"]).set(mirrorParent)
            mirrorGiNode.setParent(mirrorParent)

            parent = giNode.attr(self.ATTR["parent"]).get()
            giNode.setParent(parent)
            nodes[pm.PyNode(self.swapSideName(jnt))] = mirrorGiNode


class GimmickSlide(GimmickJoint):
    TYPE = "Slide"

    def __init__(self, joint=None, side=None):
        self.joint = joint
        self.side = side

        self.element = {}

    def generateBase(self):
        startPoint = pm.createNode("transform")
        endPoint = pm.createNode("transform")
        guide = pm.curve(d=1)
        slideJnt = pm.createNode("joint")
        guideShape = guide[0].getShape()

        startPoint.rename("{}_startPoint".format(self.joint))
        endPoint.rename("{}_endPoint".format(self.joint))
        guide.rename("{}_guideCurve".format(self.joint))
        slideJnt.rename("{}_slideJnt".format(self.joint))

        attribute.lockAttribute(guide, attributes=["t", "r", "s", "vis"])
        guideShape.attr("lineWidth").set(3)
        guide.attr("template").set(True)

        slide = self.TYPE.lower()
        attribute.lockAttribute(slideJnt, attributes=["t", "r", "s", "vis"])
        slideJnt.addAttr(slide, at="float", min=0, max=1, dv=0.5, k=False)
        slideJnt.attr(slide).set(cb=True)
        slideJnt.attr("overrideEnabled").set(1)
        slideJnt.attr("overrideColor").set(28)

    def create(self):
        for jnt in self.joint:
            base = self.createGimmickBase(jnt, self.side, self.SLIDE)
            guideShape = base["guide"].getShape()
            driven = base["inf"].getParent()

            # create a pairBlend for dividing rotation of driver joint
            decStart = pm.createNode("decomposeMatrix")
            decEnd = pm.createNode("decomposeMatrix")
            vectorMinus = pm.createNode("plusMinusAverage")
            vectorPlus = pm.createNode("plusMinusAverage")
            vectorMult = pm.createNode("multiplyDivide")
            vectorInvMult = pm.createNode("multiplyDivide")
            output = pm.createNode("plusMinusAverage")

            # put -1 to vectorInverseMultply
            vectorInvMult.attr("input2X").set(-1)
            vectorInvMult.attr("input2Y").set(-1)
            vectorInvMult.attr("input2Z").set(-1)

            # rename to a proper name
            decStart.rename("{}_decomposeMatrix".format(base[0]))
            decEnd.rename("{}_decomposeMatrix".format(base[1]))
            vectorMinus.rename("{}_vectorMinus".format(base[0]))
            vectorPlus.rename("{}_vectorPlus".format(base[0]))
            vectorMult.rename("{}_envelope".format(base[0]))
            vectorInvMult.rename("{}_inverse".format(base[0]))
            output.rename("{}_output".format(base[0]))

            # connection for slide setup
            base["start"].attr("worldMatrix[0]") >> decStart.attr("inputMatrix")
            base["end"].attr("worldMatrix[0]") >> decEnd.attr("inputMatrix")
            decStart.attr("outputTranslate") >> guideShape.attr("controlPoints[0]")
            decEnd.attr("outputTranslate") >> guideShape.attr("controlPoints[1]")

            guideShape.attr("controlPoint[0]") >> vectorMinus.attr("input3D.input3D[1]")
            guideShape.attr["controlPoint[0]"] >> vectorPlus.attr["input3D.input3D[1]"]
            guideShape.attr("controlPoint[1]") >> vectorMinus.attr("input3D.input3D[0]")
            vectorMinus.attr("output3D") >> vectorMult.attr("input1")
            vectorMinus.attr("output3D") >> vectorPlus.attr("input3D.input3D[0]")

            base["guide"].attr("slide") >> vectorMult.attr("input2.input2X")
            base["guide"].attr("slide") >> vectorMult.attr("input2.input2Y")
            base["guide"].attr("slide") >> vectorMult.attr("input2.input2Z")

            vectorMult.attr["output"] >> vectorInvMult.attr["input1"]
            output.attr["output3D"] >> driven.attr["translate"]


class GimmickJointIO(Gimmick):
    """docstring for GimmickJointIO."""

    def __init__(self, filePath=None):
        self.filePath = filePath

    def getGimmickPath(self):
        workspace = pm.Workspace()
        projectPath = workspace.getPath()
        gimmickPath = os.path.join(projectPath, 'data', 'gimmick')

        if not os.path.exists(gimmickPath):
            os.makedirs(gimmickPath)
        return gimmickPath

    def fileDialog(self, startDir=None, mode=0):
        """prompt dialog for either import/export from a UI

        Args:
            startDir (str): A directory to start from
            mode (int, optional): 1: import or 0: export

        Returns:
            str: path selected by user
        """
        if not startDir:
            startDir = self.getGimmickPath()

        fPath = pm.fileDialog2(fileMode=mode,
                               startingDirectory=startDir,
                               fileFilter="(*.json)")
        if fPath:
            fPath = fPath[0]
        return fPath

    def __getColor(self, jnt, colorType):
        """Get the color from shape node

        Args:
            node (TYPE): shape

        Returns:
            TYPE: Description
        """
        if not jnt:
            return False

        color = None

        if colorType == "jnt":
            if jnt.overrideRGBColors.get():
                color = jnt.overrideColorRGB.get()
            else:
                color = jnt.overrideColor.get()
        elif colorType == "outline":
            color = jnt.outlinerColor.get()

        return color

    def __importData(self):
        """Return the contents of a json file. Expecting, but not limited to,
        a dictionary.

        Returns:
            dict: contents of json file, expected dict
        """
        try:
            with open(self.filePath, "r") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(e)
            return None

    def __exportData(self, data):
        """export data, dict, to filepath provided

        Args:
            data (dict): expected dict, not limited to
            filePath (string): path to output json file
        """
        try:
            with open(self.filePath, "w") as json_file:
                json.dump(data, json_file, sort_keys=True, indent=4)

            msg = "Gimmick-joint data exported: {}"
            pm.displayInfo(msg.format(self.filePath))

        except Exception as e:
            print(e)

    def importGimmickJoint(self):
        """import gimmick joints from file, using the assoiciated module type to recreate

        Returns:
            n/a: n/a
        """
        if not self.filePath:
            self.filePath = self.fileDialog(mode=1)

        data = self.__importData()
        if data is None:
            return

        for name, info in data[self.BLEND].items():
            # add a joint with pos selected target
            gimmickJnt = primitive.addJoint(None, name)
            gimmickJnt.setTranslation(info["translate"])
            gimmickJnt.setOrientation(info["rotate"])
            gimmickJnt.setParent(info["parent"])
            gimmickJnt.setRadius(info["jointSize"])
            gimmickJnt.attr("overrideEnabled").set(1)
            gimmickJnt.overrideColor.set(info["jointColor"])
            gimmickJnt.attr("useOutlinerColor").set(True)
            gimmickJnt.attr("outlinerColor").set(info["outlineColor"])
            gimmickJnt.attr("segmentScaleCompensate").set(True)

            weight = "weight"
            gimmickJnt.attr("visibility").set(k=False, cb=False)
            gimmickJnt.addAttr(weight, at="float", min=0, max=1, dv=0.5, k=False)
            gimmickJnt.attr(weight).set(info["weightValue"], cb=True)

            # create a pairBlend for dividing rotation of driver joint
            blendNode = pm.createNode("pairBlend")
            blendNode.rename("{}_pairBlend".format(gimmickJnt))
            blendNode.attr("rotInterpolation").set(1)

            # connection process
            drive = pm.PyNode(info["drive"])
            gimmickJnt.weight >> blendNode.weight
            drive.translate >> blendNode.inTranslate1
            drive.translate >> blendNode.inTranslate2
            drive.rotate >> blendNode.inRotate1

            for xyz in "XYZ":
                pm.connectAttr(blendNode.attr("outTranslate{}".format(xyz)),
                               gimmickJnt.attr("translate{}".format(xyz)))
                pm.connectAttr(blendNode.attr("outRotate{}".format(xyz)),
                               gimmickJnt.attr("rotate{}".format(xyz)))
                pm.connectAttr(drive.attr("scale{}".format(xyz)),
                               gimmickJnt.attr("scale{}".format(xyz)))

            self.storeInfo(gimmickJnt,
                           info["gimmickType"],
                           side=info["gimmickSide"],
                           parent=info["parent"])

        for name, info in data[self.SUPPORT].items():
            # add a joint with pos selected target
            gimmickJnt = primitive.addJoint(None, name)
            gimmickJnt.setTranslation(info["translate"])
            gimmickJnt.setOrientation(info["rotate"])
            gimmickJnt.setParent(info["parent"])
            gimmickJnt.setRadius(info["jointSize"])
            gimmickJnt.attr("overrideEnabled").set(1)
            gimmickJnt.attr("useOutlinerColor").set(True)
            gimmickJnt.attr("outlinerColor").set(info["outlineColor"])
            gimmickJnt.overrideColor.set(info["jointColor"])
            gimmickJnt.attr("visibility").set(k=False, cb=False)

            self.storeInfo(gimmickJnt,
                           info["gimmickType"],
                           side=info["gimmickSide"],
                           parent=info["parent"])

        pm.select(cl=True)

    def exportGimmickJoint(self, nodes=None, select=False):
        """Exports the desired gimmick joints to the filepath provided

        Args:
            nodes (list): of gimmickJoints
        """
        allInfo = {self.SUPPORT: {}, self.BLEND: {}}

        if not nodes:
            nodes = []
            for side in self.SIDE_LABEL:
                blend = self.getGimmickType(self.BLEND)[side]
                nodes.extend(blend)

            for side in self.SIDE_LABEL:
                support = self.getGimmickType(self.SUPPORT)[side]
                nodes.extend(support)

        if not nodes and select:
            nodes = pm.selected()
            if not nodes:
                msg = "Please select one or more objects"
                pm.displayWarning(msg)
                return False

        for node in nodes:
            node = pm.PyNode(node)
            gtypeNum = node.attr(self.ATTR["type"]).get()
            gtype = self.convert_num_to_gimmickType(gtypeNum)

            gInfo = {"parent": node.getParent().name(),
                     "gimmickType": node.attr(self.ATTR["type"]).get(),
                     "gimmickSide": node.attr(self.ATTR["side"]).get(),
                     "translate": node.getTranslation(space="world").tolist(),
                     "rotate": node.getRotation(space="world", quaternion=True).tolist(),
                     "jointSize": node.getRadius(),
                     "jointColor": self.__getColor(node, "jnt"),
                     "outlineColor": self.__getColor(node, "outline")}

            if gtype == self.BLEND:
                pb = node.sources(type="pairBlend")[0]
                drive = pb.attr("inTranslate1").listConnections()[0].name()
                gInfo["drive"] = drive
                gInfo["weightValue"] = node.attr("weight").get()

            gInfoAll = {node.name(): gInfo}
            allInfo[gtype].update(gInfoAll)

        if not self.filePath:
            self.filePath = self.fileDialog(mode=0)

        self.__exportData(allInfo)
