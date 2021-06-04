"""Rigbits blendshapes utilities and tools"""

import pymel.core as pm
from .six import string_types


def getBlendShape(obj):
    """Get the blendshape node of an object.

    Args:
        obj (PyNode): The object with the blendshape node

    Returns:
        PyNode: The blendshape node
    """
    if isinstance(obj, string_types):
        obj = pm.PyNode(obj)

    try:
        if (pm.nodeType(obj.getShape())
                in ["mesh", "nurbsSurface", "nurbsCurve"]):
            blendShape = pm.listHistory(obj.getShape(), type="blendShape")[0]
    except Exception:
        blendShape = None

    return blendShape


def connectWithBlendshape(mesh, bst, wgt=1.0):
    """Connect 2 geometries using blendshape node

    Args:
        mesh (PyNode): The Object to apply the blendshape target
        bst (PyNode): The Blendshape target
        wgt (float, optional): Description

    Returns:
        PyNode: The blenshape node
    """
    if isinstance(mesh, string_types):
        mesh = pm.PyNode(mesh)
    if isinstance(bst, string_types):
        bst = pm.PyNode(bst)
    bsnode = getBlendShape(mesh)
    if bsnode:
        wc = pm.blendShape(bsnode, q=True, wc=True)
        pm.blendShape(bsnode, edit=True, t=(mesh, wc, bst, 1.0))
        bsnode.attr(bst.name()).set(wgt)
        bs = bsnode
    else:
        bs = pm.blendShape(bst,
                           mesh,
                           name="_".join([mesh.name(), "blendShape"]),
                           foc=True,
                           w=[(0, 1.0)])

    return bs
