"""Rigbits Rope rig creator"""

import pymel.core as pm

from mgear.core import applyop
from mgear import rigbits


def rope(DEF_nb=10,
         ropeName="rope",
         keepRatio=False,
         lvlType="transform",
         oSel=None):
    """Create rope rig based in 2 parallel curves.

    Args:
        DEF_nb (int): Number of deformer joints.
        ropeName (str): Name for the rope rig.
        keepRatio (bool): If True, the deformers will keep the length
            position when the curve is stretched.
    """
    if oSel and len(oSel) == 2 and isinstance(oSel, list):
        oCrv = oSel[0]
        if isinstance(oCrv, str):
            oCrv = pm.PyNode(oCrv)
        oCrvUpV = oSel[1]
        if isinstance(oCrvUpV, str):
            oCrvUpV = pm.PyNode(oCrvUpV)
    else:
        if len(pm.selected()) != 2:
            print("You need to select 2 nurbsCurve")
            return
        oCrv = pm.selected()[0]
        oCrvUpV = pm.selected()[1]
    if (oCrv.getShape().type() != "nurbsCurve"
            or oCrvUpV.getShape().type() != "nurbsCurve"):
        print("One of the selected objects is not of type: 'nurbsCurve'")
        print(oCrv.getShape().type())
        print(oCrvUpV.getShape().type())
        return
    if keepRatio:
        arclen_node = pm.arclen(oCrv, ch=True)
        alAttr = pm.getAttr(arclen_node + ".arcLength")
        muldiv_node = pm.createNode("multiplyDivide")
        pm.connectAttr(arclen_node + ".arcLength", muldiv_node + ".input1X")
        pm.setAttr(muldiv_node + ".input2X", alAttr)
        pm.setAttr(muldiv_node + ".operation", 2)
        pm.addAttr(oCrv, ln="length_ratio", k=True, w=True)
        pm.connectAttr(muldiv_node + ".outputX", oCrv + ".length_ratio")

    root = pm.PyNode(pm.createNode(lvlType, n=ropeName + "_root", ss=True))
    step = 1.000 / (DEF_nb - 1)
    i = 0.000
    shds = []
    for x in range(DEF_nb):

        oTransUpV = pm.PyNode(pm.createNode(
            lvlType, n=ropeName + str(x).zfill(3) + "_upv", p=root, ss=True))

        oTrans = pm.PyNode(pm.createNode(
            lvlType, n=ropeName + str(x).zfill(3) + "_lvl", p=root, ss=True))

        cnsUpv = applyop.pathCns(
            oTransUpV, oCrvUpV, cnsType=False, u=i, tangent=False)

        cns = applyop.pathCns(oTrans, oCrv, cnsType=False, u=i, tangent=False)

        if keepRatio:
            muldiv_node2 = pm.createNode("multiplyDivide")
            condition_node = pm.createNode("condition")
            pm.setAttr(muldiv_node2 + ".operation", 2)
            pm.setAttr(muldiv_node2 + ".input1X", i)
            pm.connectAttr(oCrv + ".length_ratio", muldiv_node2 + ".input2X")
            pm.connectAttr(muldiv_node2 + ".outputX",
                           condition_node + ".colorIfFalseR")
            pm.connectAttr(muldiv_node2 + ".outputX",
                           condition_node + ".secondTerm")
            pm.connectAttr(muldiv_node2 + ".input1X",
                           condition_node + ".colorIfTrueR")
            pm.connectAttr(muldiv_node2 + ".input1X",
                           condition_node + ".firstTerm")
            pm.setAttr(condition_node + ".operation", 4)

            pm.connectAttr(condition_node + ".outColorR", cnsUpv + ".uValue")
            pm.connectAttr(condition_node + ".outColorR", cns + ".uValue")

        cns.setAttr("worldUpType", 1)
        cns.setAttr("frontAxis", 0)
        cns.setAttr("upAxis", 1)

        pm.connectAttr(oTransUpV.attr("worldMatrix[0]"),
                       cns.attr("worldUpMatrix"))
        shd = rigbits.addJnt(oTrans)
        shds.append(shd[0])
        i += step

    return shds


def rope_UI(*args):
    """Rope tool UI"""

    if pm.window("mGear_rope_window", exists=True):
        pm.deleteUI("mGear_rope_window")

    window = pm.window("mGear_rope_window",
                       title="mGear rope rig generator",
                       w=350,
                       h=150,
                       mxb=False,
                       sizeable=False)

    pm.rowColumnLayout(numberOfColumns=2,
                       columnAttach=(1, 'right', 0),
                       columnWidth=[(1, 100), (2, 250)])

    pm.text("Nb of deformers: ")

    pm.intField("nbDeformers",
                annotation="number of deformers",
                w=50,
                value=10)

    pm.text(label="Keep position ")
    pm.checkBox("keepRatio", label=" (base on ratio) ")
    pm.text(label="Name: ")
    pm.textField("RopeName", text="Rope")

    pm.separator(h=10)
    pm.button(label="Build the rope!", w=150, h=50, command=build_rope)
    pm.separator(h=10)
    pm.separator(h=10)
    pm.separator(h=10)
    pm.text(label="Instructions:  Select ctl crv + upv crv", align="left")

    pm.showWindow(window)


def build_rope(*args):
    DEF_nb = pm.intField("nbDeformers", q=True, v=True)
    ropeName = pm.textField("RopeName", q=True, text=True)
    keepRatio = pm.checkBox("keepRatio", q=True, v=True)
    rope(DEF_nb, ropeName, keepRatio)
