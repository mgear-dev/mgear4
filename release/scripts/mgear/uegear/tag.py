#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains functions related with Maya tag functionality for ueGear.
"""

from __future__ import print_function, division, absolute_import

import maya.cmds as cmds
import maya.api.OpenMaya as OpenMaya

from mgear.uegear import utils, log

logger = log.uegear_logger

TAG_ASSET_GUID_ATTR_NAME = "ueGearAssetGuid"
TAG_ASSET_TYPE_ATTR_NAME = "ueGearAssetType"
TAG_ASSET_NAME_ATTR_NAME = "ueGearAssetName"
TAG_ASSET_PATH_ATTR_NAME = "ueGearAssetPath"
TAG_ACTOR_NAME_ATTR_NAME = "ueGearActorName"
ALL_TAGS_ATTR_NAMES = [
    TAG_ASSET_GUID_ATTR_NAME,
    TAG_ASSET_TYPE_ATTR_NAME,
    TAG_ASSET_NAME_ATTR_NAME,
    TAG_ASSET_PATH_ATTR_NAME,
    TAG_ACTOR_NAME_ATTR_NAME,
]


class TagTypes(object):
    """
    Class that holds all available tag types.
    """

    Skeleton = "skeleton"
    StaticMesh = "staticmesh"
    SkeletalMesh = "skeletalmesh"
    Camera = "camera"
    Alembic = "alembic"
    MetahumanBody = "metahumanbody"
    MetahumanFace = "metahumanface"
    Sequence = "sequence"


def auto_tag(node=None, remove=False):
    """
    Automatically tags given (or current selected nodes) so ueGear exporter can identify how to export the specific
    nodes.

    :param str or list(str) or None node: node/s to tag.
    :param bool remove: if True tag will be removed.
    """

    nodes = utils.force_list(node or cmds.ls(sl=True, long=True))

    for node in nodes:
        found_skin_clusters = utils.get_skin_clusters_for_node(node)
        if found_skin_clusters and cmds.objectType(node) == "joint":
            remove_tag(node) if remove else apply_tag(
                node, attribute_value=TagTypes.SkeletalMesh
            )
        else:
            shapes = cmds.listRelatives(node, fullPath=True, shapes=True)
            if not shapes:
                continue
            first_shape = utils.get_first_in_list(shapes)
            if not first_shape:
                continue
            object_type = cmds.objectType(first_shape)
            if object_type == "mesh":
                found_skin_clusters = utils.get_skin_clusters_for_node(
                    first_shape
                )
                if found_skin_clusters:
                    remove_tag(node) if remove else apply_tag(
                        node, attribute_value=TagTypes.Skeleton
                    )
                else:
                    remove_tag(node) if remove else apply_tag(
                        node, attribute_value=TagTypes.StaticMesh
                    )
            elif object_type == "camera":
                remove_tag(node) if remove else apply_tag(
                    node, attribute_value=TagTypes.Camera
                )


def apply_tag(
    node=None, attribute_name=TAG_ASSET_TYPE_ATTR_NAME, attribute_value=""
):
    """
    Creates a new tag attribute with given value into given node/s (or selected nodes).

    :param str or list(str) or None node: nodes to apply tag to.
    :param str attribute_name: tag attribute value to use. By default, TAG_ASSET_TYPE_ATTR_NAME will be used.
    :param str attribute_value: value to set tag to.
    """

    nodes = utils.force_list(node or cmds.ls(sl=True))
    attribute_value = str(attribute_value)

    for node in nodes:
        if not cmds.attributeQuery(attribute_name, node=node, exists=True):
            cmds.addAttr(node, longName=attribute_name, dataType="string")
        cmds.setAttr(
            "{}.{}".format(node, attribute_name),
            attribute_value,
            type="string",
        )
        if attribute_value:
            logger.info(
                'Tagged "{}.{}" as {}.'.format(
                    node, attribute_name, attribute_value
                )
            )
        else:
            logger.info(
                'Tagged "{}.{}" as empty.'.format(node, attribute_name)
            )


def remove_tag(node=None, attribute_name=TAG_ASSET_TYPE_ATTR_NAME):
    """
    Removes tag attribute from the given node.

    :param str or list(str) or None node: nodes to remove tag from.
    :param str attribute_name: tag attribute value to remove. By default, TAG_ASSET_TYPE_ATTR_NAME will be used.
    """

    nodes = utils.force_list(node or cmds.ls(sl=True))

    for node in nodes:
        if not cmds.attributeQuery(attribute_name, node=node, exists=True):
            continue
        cmds.deleteAttr("{}.{}".format(node, attribute_name))
        logger.info(
            'Removed attribute {} from "{}"'.format(attribute_name, node)
        )


def remove_all_tags(node=None):
    """
    Removes all ueGear tags from the given node.

    :param str or list(str) or None node: nodes to remove tags from.
    """

    nodes = utils.force_list(node or cmds.ls(sl=True))

    for attribute_name in ALL_TAGS_ATTR_NAMES:
        remove_tag(nodes, attribute_name=attribute_name)


def apply_alembic_tag(node=None, remove=False):
    """
    Applies alembic tag to given node/s (or selected nodes).

    :param str or list(str) or None node: node/s to tag.
    :param bool remove: if True tag will be removed.
    """

    remove_tag(node=node) if remove else apply_tag(
        node=node, attribute_value=TagTypes.Alembic
    )


def find_tagged_nodes(
    tag_name=TAG_ASSET_TYPE_ATTR_NAME, nodes=None, tag_value=None
):
    """
    Returns a list with all nodes that are tagged with the given tag name and has a value set.

    :param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
    :param str or list(str) or None nodes: list of nodes to find tags of, if not given all nodes in the scene will be
            checked.
    :param str tag_value: if given only tag with given value will be returned.
    :return: list of found tagged nodes.
    :rtype: list(str)
    """

    found_tagged_nodes = list()
    nodes = utils.force_list(nodes or cmds.ls())
    for node in nodes:
        if not cmds.attributeQuery(tag_name, node=node, exists=True):
            continue
        found_tag_value = cmds.getAttr("{}.{}".format(node, tag_name))
        if not found_tag_value or (
            tag_value is not None and found_tag_value != tag_value
        ):
            continue
        found_tagged_nodes.append(node)

    return found_tagged_nodes


def find_tagged_selected_nodes(tag_name):
    """
    Returns a list with all selected nodes that are tagged with the given tag name and has a value set.

    :param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
    :return: list of found tagged nodes.
    :rtype: list(str)
    """

    return find_tagged_nodes(nodes=cmds.ls(sl=True))


def find_tagged_node_attributes(tag_name=TAG_ASSET_TYPE_ATTR_NAME, nodes=None):
    """
    Returns a list with all node attributes that are tagged with the given tag name and has a value set.

    :param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
    :param str or list(str) or None nodes: list of nodes to find tags of, if not given all nodes in the scene will be
            checked.
    :return: list of found tagged nodes.
    :rtype: list(str)
    """

    found_tagged_node_attributes = list()
    nodes = utils.force_list(nodes or cmds.ls(long=True))
    for node in nodes:
        if not cmds.attributeQuery(tag_name, node=node, exists=True):
            continue
        if not cmds.getAttr("{}.{}".format(node, tag_name)):
            continue
        found_tagged_node_attributes.append("{}.{}".format(node, tag_name))

    return found_tagged_node_attributes


def find_tagged_selected_node_attributes(tag_name):
    """
    Returns a list with all selected node attributes that are tagged with the given tag name and has a value set.

    :param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
    :return: list of found tagged nodes.
    :rtype: list(str)
    """

    return find_tagged_node_attributes(nodes=cmds.ls(sl=True))


def tag_values(tag_name=TAG_ASSET_TYPE_ATTR_NAME, nodes=None):
    """
    Returns a list with all node attribute values that are tagged with the given tag name.

    :param str tag_name:name of the tag to search value of.
    :param str or list(str) nodes: list of nodes to find tags of, if not given all nodes in the scene will be checked.
    :return: list of tagged node values.
    :rtype: list(object)
    """

    found_tag_values = list()
    nodes = utils.force_list(nodes or cmds.ls(long=True))
    for node in nodes:
        if not cmds.attributeQuery(tag_name, node=node, exists=True):
            found_tag_values.append(None)
            continue
        found_tag_values.append(cmds.getAttr("{}.{}".format(node, tag_name)))

    return found_tag_values


def tag_match(dag_path, tag_value, tag):
    """
    Validates if the object specified by its dag path, has the same tag and value
    assigned to it.

    :param OpenMaya.DagPath dag_path: The object you want to validate has the
           following tag and data assigned.
    :param str tag_value: value assigned to the tag.
    :param str tag: tag to correlate with.
    :return: True if the object has matching tag and the values are the same.
    :rtype: bool
    """
    dag_node = OpenMaya.MFnDagNode(dag_path)
    attr = dag_node.attribute(tag)
    plug = dag_node.findPlug(attr, False)
    plug_value = plug.asString()
    return plug_value == tag_value
