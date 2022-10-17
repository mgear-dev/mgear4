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
        if pm.nodeType(obj.getShape()) in [
            "mesh",
            "nurbsSurface",
            "nurbsCurve",
        ]:
            blendShape = pm.listHistory(obj.getShape(), type="blendShape")[0]
    except Exception:
        blendShape = None

    return blendShape


def blendshape_foc(deformed_obj):
    """Move existing blendshape node to the front of chain

    Args:
        deformed_obj (PyNode): object with deformation history including a
                blendshape node
    """
    meshShape = deformed_obj.getShape()

    history = pm.listHistory(
        meshShape, gl=True, pdo=True, lf=True, f=False, il=2
    )
    blendShape_node = None
    deformers = []
    for h in history:
        object_type = pm.objectType(h)
        if object_type == "blendShape":
            blendShape_node = h
        else:
            deformers.append(h)
    if blendShape_node:
        # add blendshape node deformer
        deformers.append(blendShape_node)
        # last add the mesh shape
        deformers.append(meshShape)
        pm.reorderDeformers(*deformers)


def connectWithBlendshape(mesh, bst, wgt=1.0, ffoc=False):
    """Connect 2 geometries using blendshape node

    Args:
        mesh (PyNode): The Object to apply the blendshape target
        bst (PyNode): The Blendshape target
        wgt (float, optional): Description
        ffoc (bool, optional): Force Front of Chain. will move the blendshape node after creation

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
        if ffoc:
            foc = False
        else:
            foc = True
        bs = pm.blendShape(
            bst,
            mesh,
            name="_".join([mesh.name(), "blendShape"]),
            foc=foc,
            w=[(0, 1.0)],
        )
        if ffoc:
            blendshape_foc(mesh)

    return bs
