""" flex.query

flex.query module contains a collection of functions useful for the analyze
and update functions of Flex

:module: flex.query
"""

# import
from __future__ import absolute_import
import math
from maya import OpenMaya
from maya import cmds
import os
import tempfile
from mgear.flex import logger  # @UnusedImport
from mgear.flex.decorators import timer  # @UnusedImport


def get_clean_matching_shapes(source, target):
    """ Returns the prefix-less found shapes under the given groups

    :param source: source group containing shapes in Maya
    :type source: string

    :param target: target group containing shapes in Maya
    :type target: string

    :return: The matching target shapes names without prefix
    :rtype: dict, dict
    """

    # gets all shapes on source and target
    source_shapes = get_shapes_from_group(source)
    target_shapes = get_shapes_from_group(target)

    # gets prefix-less shapes
    sources_dict = get_prefix_less_dict(source_shapes)
    targets_dict = get_prefix_less_dict(target_shapes)

    return sources_dict, targets_dict


def get_deformers(shape):
    """ Returns a dict with each deformer found on the given shape

    :param shape: the shape node name
    :type shape: str

    :return: the deformers found on shape sorted by type
    :rtype: dict
    """

    # gets all deformers used the target shape
    deformers_list = cmds.findDeformers(shape)
    deformers = {"skinCluster": [], "blendShape": [], "cluster": []}

    # filter the deformers by type
    for deformer in deformers_list:
        if cmds.objectType(deformer) == "skinCluster":
            deformers["skinCluster"].append(deformer)
        if cmds.objectType(deformer) == "blendShape":
            deformers["blendShape"].append(deformer)
        if cmds.objectType(deformer) == "cluster":
                    deformers["cluster"].append(deformer)

    return deformers


def get_dependency_node(element):
    """ Returns a Maya MFnDependencyNode from the given element

    :param element: Maya node to return a dependency node class object
    :type element: string

    :return: the element in a Maya MFnDependencyNode object
    :rtype: MFnDependencyNode
    """

    # adds the elements into an maya selection list
    m_selectin_list = OpenMaya.MSelectionList()
    m_selectin_list.add(element)

    # creates an MObject
    m_object = OpenMaya.MObject()

    # gets the MObject from the list
    m_selectin_list.getDependNode(0, m_object)

    return OpenMaya.MFnDependencyNode(m_object)


def get_matching_shapes(source_shapes, target_shapes):
    """ Returns the matching shapes

    This Function will return a dict that contains the target matching shape
    name from the source.

    :param source_shapes: sources dictionary containing prefix-less shapes
    :type source_shapes: dict

    :param target: targets dictionary containing prefix-less shapes
    :type target: dict

    :return: The matching target shapes names
    :rtype: dict

    .. note:: This function is the core idea of how Flex finds matching shapes
              from a source group to the target. Because Flex is not part of a
              specific studio pipeline this matching is **shapes name based**.
              Because some studios might bring the source scene into the rig
              scene as a reference or as an import we cover those two cases.

              Using this dict is the fastest way (so far found) to deal with
              a huge amount of names. Finding the matching names on a scene
              with more than 2000 shapes takes 0.0009... seconds.
    """

    # returns matching shapes
    return dict([(source_shapes[s], target_shapes[s])
                 for s in source_shapes
                 if s in target_shapes])


def get_matching_shapes_from_group(source, target):
    """ Returns the matching shapes on the given groups

    :param source: source group containing shapes in Maya
    :type source: string

    :param target: target group containing shapes in Maya
    :type target: string

    :return: The matching target shapes names
    :rtype: dict
    """

    # gets prefix-less shapes
    sources_dict, targets_dict = get_clean_matching_shapes(source, target)

    return get_matching_shapes(sources_dict, targets_dict)


def get_missing_shapes(source_shapes, target_shapes):
    """ Returns the missing shapes

    This Function will return a dict that contains the missing shape
    found on the target.

    :param source_shapes: sources dictionary containing prefix-less shapes
    :type source_shapes: dict

    :param target: targets dictionary containing prefix-less shapes
    :type target: dict

    :return: The missing target shapes names
    :rtype: dict
    """

    # returns matching shapes
    return dict([(source_shapes[s], s)
                 for s in source_shapes
                 if s not in target_shapes])


def get_missing_shapes_from_group(source, target):
    """ Returns the missing shapes from the given source and target group

    :param source: source group containing shapes in Maya
    :type source: string

    :param target: source group containing shapes in Maya
    :type target: string

    :return: The missing target shapes names
    :rtype: dict
    """

    # gets prefix-less shapes
    sources_dict, targets_dict = get_clean_matching_shapes(source, target)

    return get_missing_shapes(sources_dict, targets_dict)


def get_parent(element):
    """ Returns the first parent found for the given element

    :param element: A Maya dag node
    :type element: string
    """

    return cmds.listRelatives(element, parent=True, fullPath=True,
                              type="transform")


def get_prefix_less_name(element):
    """ Returns a prefix-less name

    :param elements: element top use on the search
    :type elements: str

    :return: The prefix-less name
    :rtype: str
    """

    return element.split("|")[-1].split(":")[-1]


def get_prefix_less_dict(elements):
    """ Returns a dict containing each element with a stripped prefix

    This Function will return a dict that contains each element resulting on
    the element without the found prefix

    :param elements: List of all your shapes
    :type elements: list

    :return: The matching prefix-less elements
    :rtype: dict

    .. note:: Because Flex is not part of a specific studio pipeline we cover
              two different ways to bring the source shapes inside your rig.
              You can either import the source group with the meshes or use
              a Maya reference. This function will strip the prefix whether
              your object is part of a namespace or a double name getting a
              full path naming.
    """

    return dict([(n.split("|")[-1].split(":")[-1], n) for n in elements])


def get_resources_path():
    """ Gets the directory path to the resources files
    """

    file_dir = os.path.dirname(__file__)

    if "\\" in file_dir:
        file_dir = file_dir.replace("\\", "/")

    return "{}/resources".format(file_dir)


def get_shape_orig(shape):
    """ Finds the orig (intermediate shape) on the given shape

    :param shape: maya shape node
    :type shape: str

    :return: the found orig shape
    :rtype: str

    .. note:: There are several ways of searching for the orig shape in Maya.
              Here we query it by first getting the given shape history on the
              component type attribute (inMesh, create..) then filtering on
              the result the same shape type. There might be more optimised
              and stable ways of doing this.
    """

    # gets attributes names
    attributes = get_shape_type_attributes(shape)

    orig_shapes = []
    {orig_shapes.append(n) for n in (cmds.ls(cmds.listHistory(
        "{}.{}".format(shape, attributes["input"])),
        type=cmds.objectType(shape))) if n != shape}

    if len(orig_shapes) == 0:
        orig_shapes = None

    return orig_shapes


def get_shape_type_attributes(shape):
    """ Returns a dict with the attributes names depending on the shape type

    This function returns the points, output, input and axes attributes for
    the corresponding shape type. Mesh type of nodes will be set as default
    but nurbs surfaces and nurbs curves are supported too.

    on mesh nodes: points = pnts
                   output = outMesh
                   input = inMesh
                   p_axes = (pntx, pnty, pntz)

    on nurbs nodes: points = controlPoints
                    output = local
                    input = create
                    p_axes = (xValue, yValue, zValue)

    :param shape: maya shape node
    :type shape: str

    :return: corresponding attributes names
    :rtype: dict
    """

    # declares the dict
    shape_attributes = dict()

    # set the default values for a mesh node type
    shape_attributes["points"] = "pnts"
    shape_attributes["input"] = "{}".format(cmds.listHistory(
        shape, query=True, historyAttr=True)[0].split(".")[-1])
    shape_attributes["output"] = "{}".format(cmds.listHistory(
        shape, query=True, futureLocalAttr=True)[0].split(".")[-1])
    shape_attributes["output_world"] = "{}".format(cmds.listHistory(
        shape, query=True, futureWorldAttr=True)[0].split(".")[-1])
    shape_attributes["p_axes"] = ("pntx", "pnty", "pntz")

    if cmds.objectType(shape) == "nurbsSurface" or (cmds.objectType(shape) ==
                                                    "nurbsCurve"):

        # set the default values for a nurbs node type
        shape_attributes["points"] = "controlPoints"
        shape_attributes["p_axes"] = ("xValue", "yValue", "zValue")

    return shape_attributes


def get_shapes_from_group(group):
    """ Gets all object shapes existing inside the given group

    :param group: maya transform node
    :type group: str

    :return: list of shapes objects
    :rtype: list str
    """

    shapes = []

    # gets shapes inside the given group
    shapes.extend(cmds.ls(group, dagObjects=True, noIntermediate=True,
                          exactType=("mesh")) or [])

    shapes.extend(cmds.ls(group, dagObjects=True, noIntermediate=True,
                          exactType=("nurbsCurve")) or [])

    shapes.extend(cmds.ls(group, dagObjects=True, noIntermediate=True,
                          exactType=("nurbsSurface"))or [])

    if not shapes:
        raise ValueError("No shape(s) found under the given group: '{}'"
                         .format(group))

    return shapes


def get_temp_folder():
    """ Returns the user temporary folder in a Maya friendly matter

    :return: temp folder path
    :rtype: str
    """

    return tempfile.gettempdir().replace('\\', '/')


def get_transform_selection():
    """ Gets the current dag object selection

    Returns the first selected dag object on a current selection that is a
    transform node

    :return: the first element of the current maya selection
    :rtype: str
    """

    selection = cmds.ls(selection=True, dagObjects=True, type='transform',
                        flatten=True, allPaths=True)

    if len(selection) >= 1:
        selection = selection[0]

    return selection or None


def get_vertice_count(shape):
    """ Returns the number of vertices for the given shape

    :param shape: The maya shape node
    :type shape: string

    :return: The number of vertices found on shape
    :rtype: int
    """

    return len(cmds.ls("{}.{}[*]".format(shape, get_shape_type_attributes(
        shape)["points"]), flatten=True))


def is_lock_attribute(element, attribute):
    """ Returns if the given attribute on the element is locked

    :param element: Maya node name
    :type element: string

    :param attribute: Maya attribute name. Must exist
    :type attribute: string

    :return: if attribute is locked
    :rtype: bool
    """

    return cmds.getAttr("{}.{}".format(element, attribute), lock=True)


def is_matching_bouding_box(source, target, tolerance=0.05):
    """ Checks if the source and target shape have the same bounding box

    :param source: source shape node
    :type source: string

    :param target: target shape node
    :type target: string

    :param tolerance: difference tolerance allowed. Default 0.001
    :type tolerance: float

    :return: If source and target matches their bounding box
    :rtype: bool
    """

    # gets orig shape if deformed shape
    orig_shape = get_shape_orig(target)

    if orig_shape:
        target = orig_shape[0]

    # get min bounding box vectors
    src_min = cmds.getAttr("{}.boundingBoxMin".format(source))[0]
    tgt_min = cmds.getAttr("{}.boundingBoxMin".format(target))[0]

    # get max bounding box vectors
    src_max = cmds.getAttr("{}.boundingBoxMax".format(source))[0]
    tgt_max = cmds.getAttr("{}.boundingBoxMax".format(target))[0]

    # vectors length
    src_min_mag = math.sqrt(sum(v ** 2 for v in src_min))
    tgt_min_mag = math.sqrt(sum(v ** 2 for v in tgt_min))
    src_max_mag = math.sqrt(sum(v ** 2 for v in src_max))
    tgt_max_mag = math.sqrt(sum(v ** 2 for v in tgt_max))

    if abs(tgt_min_mag - src_min_mag) > tolerance:
        return False
    elif abs(tgt_max_mag - src_max_mag) > tolerance:
        return False
    else:
        return True


def is_matching_count(source, target):
    """ Checks if the source and target shape have the same amount of vertices

    :param source: source shape node
    :type source: string

    :param target: target shape node
    :type target: string

    :return: If source and target matches vertices count or not
    :rtype: bool
    """

    if get_vertice_count(source) == get_vertice_count(target):
        return True
    else:
        return False


def is_matching_type(source, target):
    """ Checks if the source and target shape type matches

    :param source: source shape node
    :type source: string

    :param target: target shape node
    :type target: string

    :return: If source and target matches or not
    :rtype: bool
    """

    if cmds.objectType(source) == cmds.objectType(target):
        return True
    else:
        return False


def is_maya_batch():
    """ Returns if the current session is a Maya batch session or not

    :return: if Maya is on batch mode or not
    :rtype: bool
    """

    return cmds.about(batch=True)


def is_valid_group(group):
    """ Checks if group is valid

    Simply checks if the given group exists in the current Maya session and if
    it is a valid transform group.

    :param group: a maya transform node
    :type group: str

    :return: If the group is valid
    :rtype: bool
    """

    if not cmds.objExists(group):
        return False

    if cmds.objectType(group) != 'transform':
        return False

    return True


def lock_unlock_attribute(element, attribute, state):
    """ Unlocks the given attribute on the given element

    :param element: Maya node name
    :type element: string

    :param attribute: Maya attribute name. Must exist
    :type attribute: string

    :param state: If we should lock or unlock
    :type state: bool

    :return: If the setting was successful or not
    :rtype: bool
    """

    try:
        cmds.setAttr("{}.{}".format(element, attribute), lock=state)
        return True
    except RuntimeError:
        return False
