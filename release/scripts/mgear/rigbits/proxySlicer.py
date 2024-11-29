"""Rigbits proxy mesh slicer"""

import datetime

import pymel.core as pm

import mgear

from mgear.core import applyop, node, transform


def slice(parent=False, oSel=False, *args):
    """Create a proxy geometry from a skinned object"""

    startTime = datetime.datetime.now()
    print(oSel)
    if not oSel:
        oSel = pm.selected()[0]
        print("----")
        print(oSel)

    oColl = pm.skinCluster(oSel, query=True, influence=True)
    oFaces = oSel.faces
    nFaces = oSel.numFaces()

    faceGroups = []
    for x in oColl:
        faceGroups.append([])
    sCluster = pm.listConnections(oSel.getShape(), type="skinCluster")
    print(sCluster)
    sCName = sCluster[0].name()
    for iFace in range(nFaces):
        faceVtx = oFaces[iFace].getVertices()
        oSum = False
        for iVtx in faceVtx:
            values = pm.skinPercent(sCName, oSel.vtx[iVtx], q=True, v=True)
            if oSum:
                oSum = [L + l for L, l in zip(oSum, values)]
            else:
                oSum = values

        print("adding face: " \
              + str(iFace) \
              + " to group in: " \
              + str(oColl[oSum.index(max(oSum))]))

        faceGroups[oSum.index(max(oSum))].append(iFace)

    original = oSel
    if not parent:
        try:
            parentGroup = pm.PyNode("ProxyGeo")
        except TypeError:
            parentGroup = pm.createNode("transform", n="ProxyGeo")
    try:
        proxySet = pm.PyNode("rig_proxyGeo_grp")
    except TypeError:
        proxySet = pm.sets(name="rig_proxyGeo_grp", em=True)

    for boneList in faceGroups:

        if len(boneList):
            newObj = pm.duplicate(
                original,
                rr=True,
                name=oColl[faceGroups.index(boneList)] + "_Proxy")

            for trans in ["tx",
                          "ty",
                          "tz",
                          "rx",
                          "ry",
                          "rz",
                          "sx",
                          "sy",
                          "sz"]:

                pm.setAttr(newObj[0].name() + "." + trans, lock=0)

            c = list(newObj[0].faces)

            for index in reversed(boneList):

                c.pop(index)

            pm.delete(c)
            if parent:
                pm.parent(newObj,
                          pm.PyNode(oColl[faceGroups.index(boneList)]),
                          a=True)
            else:
                pm.parent(newObj, parentGroup, a=True)
                dummyCopy = pm.duplicate(newObj[0])[0]
                pm.delete(newObj[0].listRelatives(c=True))

                transform.matchWorldTransform(
                    pm.PyNode(oColl[faceGroups.index(boneList)]), newObj[0])

                pm.parent(dummyCopy.listRelatives(c=True)[0],
                          newObj[0],
                          shape=True)

                pm.delete(dummyCopy)

                pm.rename(newObj[0].listRelatives(c=True)[0],
                          newObj[0].name() + "_offset")

                o_multiplayer = pm.PyNode(oColl[faceGroups.index(boneList)])
                mulmat_node = applyop.gear_mulmatrix_op(
                    o_multiplayer.name() + ".worldMatrix",
                    newObj[0].name() + ".parentInverseMatrix")

                outPlug = mulmat_node + ".output"
                dm_node = node.createDecomposeMatrixNode(outPlug)

                pm.connectAttr(dm_node + ".outputTranslate",
                               newObj[0].name() + ".t")
                pm.connectAttr(dm_node + ".outputRotate",
                               newObj[0].name() + ".r")
                pm.connectAttr(dm_node + ".outputScale",
                               newObj[0].name() + ".s")

            print("Creating proxy for: {}".format(
                str(oColl[faceGroups.index(boneList)])))

            pm.sets(proxySet, add=newObj)

    endTime = datetime.datetime.now()
    finalTime = endTime - startTime
    mgear.log("=============== Slicing for: %s finish ======= [ %s  ] ==="
              "===" % (oSel.name(), str(finalTime)))
