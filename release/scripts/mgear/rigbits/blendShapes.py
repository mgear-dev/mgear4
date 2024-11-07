"""Rigbits blendshapes utilities and tools"""

import mgear.pymaya as pm
from mgear.core import deformer
from .six import string_types


def getDeformerNode(obj, lv=2, dtype="blendShape"):
    """Get the blendshape node of an object.

    Args:
        obj (PyNode): The object with the blendshape node
     lv (int, optional): Levels deep to traverse
        dtype (str, optional): deformer node type

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
            deformer_node = pm.listHistory(obj.getShape(), type=dtype, lv=lv)[
                0
            ]
    except Exception:
        deformer_node = None

    return deformer_node


def getBlendShape(obj, lv=2):
    """Get the blendshape node of an object.

    Args:
     obj (PyNode): The object with the blendshape node
     lv (int, optional): Levels deep to traverse

    Returns:
     PyNode: The blendshape node
    """
    return getDeformerNode(obj, lv=lv)


def getMorph(obj, lv=2):
    """Get the morph node of an object.

    Args:
        obj (PyNode): The object with the blendshape node
        lv (int, optional): Levels deep to traverse

    Returns:
        PyNode: The blendshape node
    """
    return getDeformerNode(obj, lv=lv, dtype="morph")


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
    history = deformer.filter_deformers(history)
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


def morph_foc(deformed_obj, morph_deformer):
    """Move existing morph node to the front of chain

    Args:
        deformed_obj (PyNode): object with deformation history including a
                morph node
    """
    meshShape = deformed_obj.getShape()

    history = pm.listHistory(
        meshShape, gl=True, pdo=True, lf=True, f=False, il=2
    )
    history = deformer.filter_deformers(history)

    # remove the first one that is the new morph
    history_check = history[1:]

    # Insert the new element before the blendShape or at the end of the list
    insert_index = len(history_check)
    start_slice = -2
    for i, element in enumerate(history_check):
        if isinstance(element, pm.nodetypes.BlendShape):
            insert_index = i
            start_slice = -3
            break

    history_check.insert(insert_index, morph_deformer)

    # last add the mesh shape
    result = history_check[start_slice:]
    if len(result) > 1:
        result.append(meshShape)
        pm.reorderDeformers(*result)


def connectWithMorph(mesh, bst, wgt=1.0, ffoc=True):
    """Connect 2 geometries using morph node

    Args:
        mesh (PyNode): The Object to apply the blendshape target
        bst (PyNode): The Blendshape target
        wgt (float, optional): envelope weight
        ffoc (bool, optional): Force Front of Chain. will move the morph
                node after creation

    Returns:
        PyNode: The blenshape node
    """
    if isinstance(mesh, string_types):
        mesh = pm.PyNode(mesh)
    if isinstance(bst, string_types):
        bst = pm.PyNode(bst)
    morph_deformer = pm.deformer(mesh, type="morph")[0]
    pm.rename(morph_deformer, mesh.name() + "_morph")
    # relative modde
    morph_deformer.morphMode.set(1)
    pm.connectAttr(bst.worldMesh[0], morph_deformer.morphTarget[0], force=True)
    if ffoc:
        morph_foc(mesh, morph_deformer)
    return morph_deformer
