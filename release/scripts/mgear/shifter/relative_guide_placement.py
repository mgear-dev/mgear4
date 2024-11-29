"""
Given a universal mesh, record the placements of guide nodes as it relative to
universal mesh. And then repoisition guides to that relative position should
the universal mesh change from character to character.

from mgear.shifter import relativeGuidePlacement
reload(relativeGuidePlacement)

Execute the following chunk to record initial placement ----------------------
relativeGuidePlacement.exportGuidePlacement(filepath="Y:/tmp/exampleFile.json",
                                            skip_strings=["hair"])


Load new universal guide mesh with new proportions

Execute the following lines to move the guides to their new position ---------
relativeGuidePlacement.importGuidePlacement(filepath="Y:/tmp/exampleFile.json")

Attributes:
    GUIDE_ROOT (str): name of the root guide node
    SKIP_CONTAINS (list): nodes to skip if they contain the string
    SKIP_CRAWL_NODES (list): nodes to skip crawling hierarchy
    SKIP_NODETYPES (list): skip the query of certain node types
    SKIP_PLACEMENT_NODES (TYPE): nodes to skip updating their positions
    SKIP_SUFFIX (list): skip if node ends with
    UNIVERSAL_MESH_NAME (str): default name of the universal mesh
"""
# python
import json
import math

# dcc
import maya.cmds as mc
import pymel.core as pm
import maya.OpenMaya as om

# mgear
from mgear.core import utils
from mgear.core import vector
from mgear.core import transform
from mgear.core import meshNavigation


# constants -------------------------------------------------------------------

# Designate the root of the hierarchy to crawl
GUIDE_ROOT = "guide"


# Nodes to avoid checking the hierarchy
DEFAULT_SKIP_CRAWL_NODES = ("controllers_org",
                            "spineUI_C0_root",
                            "faceUI_C0_root",
                            "legUI_R0_root",
                            "armUI_L0_root",
                            "legUI_L0_root",
                            "armUI_R0_root")

# nodes that will not have their positions updated
DEFAULT_SKIP_PLACEMENT_NODES = ("controllers_org",
                                "global_C0_root",
                                "spineUI_C0_root",
                                "faceUI_C0_root",
                                "legUI_R0_root",
                                "armUI_L0_root",
                                "legUI_L0_root",
                                "armUI_R0_root")


try:
    SKIP_CRAWL_NODES
    SKIP_PLACEMENT_NODES
except NameError:
    SKIP_CRAWL_NODES = list(DEFAULT_SKIP_CRAWL_NODES)
    SKIP_PLACEMENT_NODES = list(DEFAULT_SKIP_PLACEMENT_NODES)


# skip the node if it even contains the characters in the list
# eg SKIP_CONTAINS = ["hair"]
SKIP_CONTAINS = []

# Avoid nodes of a specified suffix
SKIP_SUFFIX = ["sizeRef", "crv", "crvRef", "blade"]

# Types of nodes to avoid
SKIP_NODETYPES = ["aimConstraint", "pointConstraint", "parentConstraint"]

UNIVERSAL_MESH_NAME = "skin_geo_setup"


# general functions -----------------------------------------------------------

def crawlHierarchy(parentNode,
                   ordered_hierarchy,
                   skip_crawl_nodes,
                   skip_strings=None):
    """recursive function to crawl a hierarchy of nodes to return decendents

    Args:
        parentNode (str): node to query
        ordered_hierarchy (str): list to continuesly pass itself
        skip_crawl_nodes (list): nodes to skip crawl
    """
    if not skip_strings:
        skip_strings = []
    for node in mc.listRelatives(parentNode, type="transform") or []:
        if node in skip_crawl_nodes or node in ordered_hierarchy:
            continue
        if node.endswith(tuple(SKIP_SUFFIX)):
            continue
        if mc.objectType(node) in SKIP_NODETYPES:
            continue
        if [True for skip_str in skip_strings
                if skip_str.lower() in node.lower()]:
            continue
        ordered_hierarchy.append(node)
        crawlHierarchy(node,
                       ordered_hierarchy,
                       skip_crawl_nodes,
                       skip_strings=skip_strings)


def getPostionFromLoop(vertList):
    """Get the center position from the list of edge ids provided

    Args:
        vertList (list): list of edge ids

    Returns:
        list: of translate XYZ, world space
    """
    bb = mc.exactWorldBoundingBox(vertList)
    pos = ((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2)
    return pos


def getVertMatrix(closestVert):
    """create a matrix from the closestVert and the normals of the surrounding
    faces for later comparison

    Args:
        node (str): guide node to query
        closestVert (str): closest vert to guide

    Returns:
        list: of matrices
    """
    closestVert = pm.PyNode(closestVert)
    faces = closestVert.connectedFaces()
    normalVector = faces.getNormal("world")
    pm.select(faces)
    faces_str = mc.ls(sl=True, fl=True)
    pm.select(cl=True)
    face_pos = pm.dt.Vector(getPostionFromLoop(faces_str))
    normal_rot = getOrient([normalVector.x, normalVector.y, normalVector.z],
                           [0, 1, 0],
                           ro=0)
    orig_ref_matrix = pm.dt.TransformationMatrix()
    orig_ref_matrix.setTranslation(face_pos, pm.dt.Space.kWorld)
    orig_ref_matrix.setRotation(normal_rot)

    return orig_ref_matrix


def getOrient(normal, tangent, ro=0):
    """convert normal direction into euler rotations

    Args:
        normal (list): of nomel values
        ro (int, optional): rotate order

    Returns:
        list: of euler rotations
    """
    kRotateOrders = [om.MEulerRotation.kXYZ, om.MEulerRotation.kYZX,
                     om.MEulerRotation.kZXY, om.MEulerRotation.kXZY,
                     om.MEulerRotation.kYXZ, om.MEulerRotation.kZYX, ]
    cross = [normal[1] * tangent[2] - normal[2] * tangent[1],
             normal[2] * tangent[0] - normal[0] * tangent[2],
             normal[0] * tangent[1] - normal[1] * tangent[0]]
    tMatrix = normal + [0] + tangent + [0] + cross + [0, 0, 0, 0, 1]
    mMatrix = om.MMatrix()
    om.MScriptUtil.createMatrixFromList(tMatrix, mMatrix)
    tmMatrix = om.MTransformationMatrix(mMatrix)
    rotate = tmMatrix.eulerRotation().reorder(kRotateOrders[ro])
    RAD_to_DEG = (180 / math.pi)
    return [rotate[0] * RAD_to_DEG,
            rotate[1] * RAD_to_DEG,
            rotate[2] * RAD_to_DEG]


def getRepositionMatrix(node_matrix,
                        orig_ref_matrix,
                        mr_orig_ref_matrix,
                        closestVerts):
    """Get the delta matrix from the original position and multiply by the
    new vert position. Add the rotations from the face normals.

    Args:
        node_matrix (pm.dt.Matrix): matrix of the guide
        orig_ref_matrix (pm.dt.Matrix): matrix from the original vert position
        closestVerts (str): name of the closest vert

    Returns:
        mmatrix: matrix of the new offset position, worldSpace
    """
    current_vert = pm.PyNode(closestVerts[0])
    mr_current_vert = pm.PyNode(closestVerts[1])
    current_length = vector.getDistance(current_vert.getPosition("world"),
                                        mr_current_vert.getPosition("world"))

    orig_length = vector.getDistance(orig_ref_matrix.translate,
                                     mr_orig_ref_matrix.translate)
    orig_center = vector.linearlyInterpolate(orig_ref_matrix.translate,
                                             mr_orig_ref_matrix.translate)
    orig_center_matrix = pm.dt.Matrix()
    # orig_center_matrix.setTranslation(orig_center, pm.dt.Space.kWorld)
    orig_center_matrix = transform.setMatrixPosition(
        orig_center_matrix, orig_center)

    current_center = vector.linearlyInterpolate(
        current_vert.getPosition("world"),
        mr_current_vert.getPosition("world"))

    length_percentage = 1
    if current_length != 0 or orig_length != 0:
        length_percentage = current_length / orig_length
    # refPosition_matrix = pm.dt.TransformationMatrix()
    refPosition_matrix = pm.dt.Matrix()
    # refPosition_matrix.setTranslation(current_center, pm.dt.Space.kWorld)
    refPosition_matrix = transform.setMatrixPosition(
        refPosition_matrix, current_center)
    deltaMatrix = node_matrix * orig_center_matrix.inverse()
    deltaMatrix = deltaMatrix * length_percentage
    deltaMatrix = transform.setMatrixScale(deltaMatrix)
    refPosition_matrix = deltaMatrix * refPosition_matrix

    return refPosition_matrix


def getRepositionMatrixSingleRef(node_matrix,
                                 orig_ref_matrix,
                                 mr_orig_ref_matrix,
                                 closestVerts):
    """Get the delta matrix from the original position and multiply by the
    new vert position. Add the rotations from the face normals.

    Args:
        node_matrix (pm.dt.Matrix): matrix of the guide
        orig_ref_matrix (pm.dt.Matrix): matrix from the original vert position
        closestVerts (str): name of the closest vert

    Returns:
        mmatrix: matrix of the new offset position, worldSpace
    """
    closestVerts = pm.PyNode(closestVerts[0])
    faces = closestVerts.connectedFaces()
    normalVector = faces.getNormal("world")
    pm.select(faces)
    faces_str = mc.ls(sl=True, fl=True)
    pm.select(cl=True)
    face_pos = pm.dt.Vector(getPostionFromLoop(faces_str))
    normal_rot = getOrient([normalVector.x, normalVector.y, normalVector.z],
                           [0, 1, 0],
                           ro=0)
    refPosition_matrix = pm.dt.TransformationMatrix()
    refPosition_matrix.setTranslation(face_pos, pm.dt.Space.kWorld)
    refPosition_matrix.setRotation(normal_rot)

    deltaMatrix = node_matrix * orig_ref_matrix.inverse()
    refPosition_matrix = deltaMatrix * refPosition_matrix

    return refPosition_matrix


@utils.viewport_off
@utils.one_undo
def getGuideRelativeDictionaryLegacy(mesh, guideOrder):
    """create a dictionary of guide:[[shape.vtx[int]], relativeMatrix]

    Args:
        mesh (string): name of the mesh
        guideOrder (list): the order to query the guide hierarchy

    Returns:
        dictionary: create a dictionary of guide:[[edgeIDs], relativeMatrix]
    """
    relativeGuide_dict = {}
    mesh = pm.PyNode(mesh)
    for guide in guideOrder:
        guide = pm.PyNode(guide)
        # slow function A
        clst_vert = meshNavigation.getClosestVertexFromTransform(mesh, guide)
        vertexIds = [clst_vert.name()]
        # slow function B
        orig_ref_matrix = getVertMatrix(clst_vert.name())
        #  --------------------------------------------------------------------
        a_mat = guide.getMatrix(worldSpace=True)

        mm = ((orig_ref_matrix - a_mat) * -1) + a_mat
        pos = mm[3][:3]

        mr_vert = meshNavigation.getClosestVertexFromTransform(mesh, pos)
        mr_orig_ref_matrix = getVertMatrix(mr_vert.name())
        vertexIds.append(mr_vert.name())

        node_matrix = guide.getMatrix(worldSpace=True)
        relativeGuide_dict[guide.name()] = [vertexIds,
                                            node_matrix.get(),
                                            orig_ref_matrix.get(),
                                            mr_orig_ref_matrix.get()]
    mc.select(cl=True)
    return relativeGuide_dict


@utils.viewport_off
@utils.one_undo
def yieldGuideRelativeDictionary(mesh, guideOrder, relativeGuide_dict):
    """create a dictionary of guide:[[shape.vtx[int]], relativeMatrix]

    Args:
        mesh (string): name of the mesh
        guideOrder (list): the order to query the guide hierarchy

    Returns:
        dictionary: create a dictionary of guide:[[edgeIDs], relativeMatrix]
    """
    for guide in guideOrder:
        guide = pm.PyNode(guide)
        # slow function A
        clst_vert = meshNavigation.getClosestVertexFromTransform(mesh, guide)
        vertexIds = [clst_vert.name()]
        # slow function B
        orig_ref_matrix = getVertMatrix(clst_vert.name())
        #  --------------------------------------------------------------------
        a_mat = guide.getMatrix(worldSpace=True)

        mm = ((orig_ref_matrix - a_mat) * -1) + a_mat
        pos = mm[3][:3]

        mr_vert = meshNavigation.getClosestVertexFromTransform(mesh, pos)
        mr_orig_ref_matrix = getVertMatrix(mr_vert.name())
        vertexIds.append(mr_vert.name())

        node_matrix = guide.getMatrix(worldSpace=True)
        relativeGuide_dict[guide.name()] = [vertexIds,
                                            node_matrix.get(),
                                            orig_ref_matrix.get(),
                                            mr_orig_ref_matrix.get()]
        yield relativeGuide_dict


@utils.viewport_off
@utils.one_undo
def getGuideRelativeDictionary(mesh, guideOrder):
    """create a dictionary of guide:[[shape.vtx[int]], relativeMatrix]

    Args:
        mesh (string): name of the mesh
        guideOrder (list): the order to query the guide hierarchy

    Returns:
        dictionary: create a dictionary of guide:[[edgeIDs], relativeMatrix]
    """
    relativeGuide_dict = {}
    mesh = pm.PyNode(mesh)
    for result in yieldGuideRelativeDictionary(
            mesh, guideOrder, relativeGuide_dict):
        pass
    return relativeGuide_dict


@utils.viewport_off
@utils.one_undo
def updateGuidePlacementLegacy(guideOrder, guideDictionary):
    """update the guides based on new universal mesh, in the provided order

    Args:
        guideOrder (list): of the hierarchy to crawl
        guideDictionary (dictionary): dict of the guide:edge, matrix position
    """
    for guide in guideOrder:
        if guide not in guideDictionary or not mc.objExists(guide):
            continue
        elif guide in SKIP_PLACEMENT_NODES:
            continue
        (vertexIds,
         node_matrix,
         orig_ref_matrix,
         mr_orig_ref_matrix) = guideDictionary[guide]

        guideNode = pm.PyNode(guide)
        repoMatrix = getRepositionMatrix(pm.dt.Matrix(node_matrix),
                                         pm.dt.Matrix(orig_ref_matrix),
                                         pm.dt.Matrix(mr_orig_ref_matrix),
                                         vertexIds)
        guideNode.setMatrix(repoMatrix, worldSpace=True, preserve=True)


@utils.viewport_off
@utils.one_undo
def yieldUpdateGuidePlacement(guideOrder, guideDictionary):
    """update the guides based on new universal mesh, in the provided order

    Args:
        guideOrder (list): of the hierarchy to crawl
        guideDictionary (dictionary): dict of the guide:edge, matrix position
    """
    for guide in guideOrder:
        if guide not in guideDictionary or not mc.objExists(guide):
            continue
        elif guide in SKIP_PLACEMENT_NODES:
            continue
        (vertexIds,
         node_matrix,
         orig_ref_matrix,
         mr_orig_ref_matrix) = guideDictionary[guide]

        repoMatrix = getRepositionMatrix(pm.dt.Matrix(node_matrix),
                                         pm.dt.Matrix(orig_ref_matrix),
                                         pm.dt.Matrix(mr_orig_ref_matrix),
                                         vertexIds)
        yield repoMatrix


@utils.viewport_off
@utils.one_undo
def updateGuidePlacement(guideOrder, guideDictionary, reset_scale=False):
    """update the guides based on new universal mesh, in the provided order

    Args:
        guideOrder (list): of the hierarchy to crawl
        guideDictionary (dictionary): dict of the guide:edge, matrix position
    """
    updateGen = yieldUpdateGuidePlacement(guideOrder, guideDictionary)
    for guide in guideOrder:
        if guide not in guideDictionary or not mc.objExists(guide):
            continue
        elif guide in SKIP_PLACEMENT_NODES:
            continue
        guideNode = pm.PyNode(guide)
        scl = guideNode.getScale()
        repoMatrix = next(updateGen)
        guideNode.setMatrix(repoMatrix, worldSpace=True, preserve=True)
        if reset_scale:
            guideNode.setScale([1, 1, 1])
        else:
            guideNode.setScale(scl)
        yield True


# ==============================================================================
# Data export, still testing
# ==============================================================================
def _importData(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(e)


def _exportData(data, filepath):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, sort_keys=False, indent=4)
    except Exception as e:
        print(e)


def exportGuidePlacement(filepath=None,
                         reference_mesh=UNIVERSAL_MESH_NAME,
                         root_node=GUIDE_ROOT,
                         skip_crawl_nodes=SKIP_CRAWL_NODES,
                         skip_strings=[]):
    """Export the position of the supplied root node to a file.

    Args:
        filepath (str, optional): path to export too
        reference_mesh (str, optional): mesh to query verts
        root_node (str, optional): name of node to query against
        skip_crawl_nodes (list, optional): of nodes not to crawl
        skip_strings (list, optional): strings to check to skip node

    Returns:
        list: dict, list, str
    """
    if filepath is None:
        filepath = pm.fileDialog2(fileMode=0,
                                  startingDirectory="/",
                                  fileFilter="Export position(*.json)")
        if filepath:
            filepath = filepath[0]
    (relativeGuide_dict,
     ordered_hierarchy) = recordInitialGuidePlacement(
        reference_mesh=reference_mesh,
        root_node=root_node,
        skip_crawl_nodes=skip_crawl_nodes,
        skip_strings=skip_strings)
    data = {}
    data["relativeGuide_dict"] = relativeGuide_dict
    data["ordered_hierarchy"] = ordered_hierarchy
    _exportData(data, filepath)
    print("Guide position exported: {}".format(filepath))
    return relativeGuide_dict, ordered_hierarchy, filepath


@utils.one_undo
def importGuidePlacement(filepath):
    """import the position from the provided file

    Args:
        filepath (str): file to the json
        referenceMesh (str, optional): name of mesh to compare against
    """
    data = _importData(filepath)
    updateGuidePlacement(data["ordered_hierarchy"], data["relativeGuide_dict"])
    return data["relativeGuide_dict"], data["ordered_hierarchy"]


def recordInitialGuidePlacement(reference_mesh=UNIVERSAL_MESH_NAME,
                                root_node=GUIDE_ROOT,
                                skip_crawl_nodes=SKIP_CRAWL_NODES,
                                skip_strings=None):
    """convenience function for retrieving a dict of position

    Args:
        reference_mesh (str, optional): the mesh to query against
        root_node (str, optional): root node to crawl
        skip_crawl_nodes (list, optional): of nodes to avoid
        skip_strings (list, optional): of strings to check if skip

    Returns:
        dict, list: dict of positions, list of ordered nodes
    """
    ordered_hierarchy = []
    relativeGuide_dict = {}
    crawlHierarchy(root_node,
                   ordered_hierarchy,
                   skip_crawl_nodes,
                   skip_strings=skip_strings)
    relativeGuide_dict = getGuideRelativeDictionary(reference_mesh,
                                                    ordered_hierarchy)
    return relativeGuide_dict, ordered_hierarchy
