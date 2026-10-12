import mgear.pymaya as pm
import maya.OpenMaya as om

from mgear.core import applyop

##################
# Helper functions
##################
namePrefix = "pCns"


def setName(name, side="C", idx=None):
    namesList = [namePrefix, side, name]
    if idx is not None:
        namesList[1] = side + str(idx)
    name = "_".join(namesList)
    return name


def getDagPath(node=None):
    sel = om.MSelectionList()
    sel.add(node)
    d = om.MDagPath()
    sel.getDagPath(0, d)
    return d


def getLocalOffset(parent, child):
    parentWorldMatrix = getDagPath(parent).inclusiveMatrix()
    childWorldMatrix = getDagPath(child).inclusiveMatrix()
    return childWorldMatrix * parentWorldMatrix.inverse()


def decomposeMatrixConnect(node=None,
                           child=None,
                           transform='srt'):
    if node and child:
        dm_node = pm.createNode('decomposeMatrix',
                                name=setName(child + "_decompMatrix"))
        pm.connectAttr(node + ".matrixSum",
                       dm_node + ".inputMatrix")
        if 't' in transform:
            pm.connectAttr(dm_node + ".outputTranslate",
                           child.attr("translate"), f=True)
        if 'r' in transform:
            pm.connectAttr(dm_node + ".outputRotate",
                           child.attr("rotate"), f=True)
        if 's' in transform:
            pm.connectAttr(dm_node + ".outputScale",
                           child.attr("scale"), f=True)


def matrixConstraint(parent=None, child=None, transform="srt", offset=False):
    """Create constraint based on Maya Matrix node.

    Kept for backward compatibility, see
    :func:`mgear.core.applyop.matrix_constraint`.
    """
    if parent and child:
        return pm.PyNode(applyop.matrix_constraint(parent, child, transform, offset))


# the last one is the child
def matrixBlendConstraint(
    parent=None,  # should be a list
    child=None,
    weights=None,  # should be a list
    transform="rt",
    offset=False,
    host=None,
):
    """Create a blend constraint based on a Maya wtAddMatrix node.

    Kept for backward compatibility, see
    :func:`mgear.core.applyop.matrix_blend_constraint`.
    """
    if parent and child:
        if not isinstance(parent, (list,)):
            pm.displayWarning(
                "matrixBlendConstraint [parent] variable should be a list."
            )
            return
        if weights and len(weights) != len(parent):
            pm.displayWarning("weights list should be equal to parents list.")
            return
        names = [setName(str(p).split("|")[-1] + "_wtWeight") for p in parent]
        return pm.PyNode(
            applyop.matrix_blend_constraint(
                parent,
                child,
                weights or None,
                transform,
                offset,
                host=host,
                weight_names=names,
            )
        )
