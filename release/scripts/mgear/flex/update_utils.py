
""" flex.update_utils

flex.update_utils module contains some simple methods that work as utilities
for the flex update process

:module: flex.update_utils
"""

# imports
from maya import OpenMaya
from maya import cmds
from maya import mel

from mgear.flex import logger
from mgear.flex.attributes import BLENDSHAPE_TARGET
from mgear.flex.decorators import timer
from mgear.flex.query import get_dependency_node
from mgear.flex.query import get_prefix_less_name
from mgear.flex.query import get_shape_orig
from mgear.flex.query import get_shape_type_attributes
from mgear.flex.query import get_temp_folder
from mgear.flex.query import is_matching_type


def add_attribute(source, target, attribute_name):
    """ Adds the given attribute to the given object

    .. note:: This is a generic method to **addAttr** all type of attributes
              inside Maya. Using the getAddAttrCmd from the MFnAttribute class
              allows avoiding to create one method for each type of attribute
              inside Maya as the addAttr command will differ depending on the
              attribute type and data.

    :param source: the maya source node
    :type source: str

    :param target: the maya target node
    :type target: str

    :param attribute_name: the attribute name to add in the given element
    :type attribute_name: str
    """

    # check if attribute already exists on target
    if cmds.objExists("{}.{}".format(target, attribute_name)):
        return

    logger.info("Adding {} attribute on {}".format(attribute_name, target))

    # gets the given attribute_name plug attribute
    m_depend_node = get_dependency_node(source)
    m_attribute = m_depend_node.findPlug(attribute_name).attribute()

    # gets the addAttr command from the MFnAttribute function
    fn_attr = OpenMaya.MFnAttribute(m_attribute)
    add_attr_cmd = fn_attr.getAddAttrCmd()[1:-1]

    # creates the attribute on the target
    mel.eval("{} {}".format(add_attr_cmd, target))


def clean_uvs_sets(shape):
    """ Deletes all uv sets besides map1

    This is used to be able to update target shapes with whatever the source
    shape has. This is only relevant for mesh shape types.

    :param shape: The Maya shape node
    :type shape: string
    """

    # check if shape is not a mesh type node
    if cmds.objectType(shape) != "mesh":
        return

    logger.debug("Cleaning uv sets on {}".format(shape))

    # gets uvs indices
    uvs_idx = cmds.getAttr("{}.uvSet".format(shape), multiIndices=True)

    # deletes the extra indices
    for idx in uvs_idx:
        if idx:
            cmds.setAttr("{}.uvSet[{}]".format(shape, idx), lock=False)
            cmds.removeMultiInstance("{}.uvSet[{}]".format(shape, idx))


def copy_blendshape_node(node, target):
    """ Copies the given blendshape node into the given target shape

    :param node: blendshape node
    :type node: str

    :param target: target shape node
    :type target: str

    :return: copied blenshape node
    :rtype: str
    """

    logger.debug("Copying blendshape node {} to {}".format(node, target))

    # get blendshape targets indices
    targets_idx = cmds.getAttr("{}.weight".format(node), multiIndices=True)

    # skip node if no targets where found
    if not targets_idx:
        return

    # list for ignored targets (when they are live connected)
    ignore = []

    # creates blendshape deformer node on target
    node_copy = cmds.deformer(target, type="blendShape", name="flex_copy_{}"
                              .format(node))[0]

    # loop on blendshape targets indices
    for idx in targets_idx:
        # input target group attribute
        attr_name = (BLENDSHAPE_TARGET.format(node, idx))

        # blendshape target name
        target_name = cmds.aliasAttr("{}.weight[{}]".format(node, idx),
                                     query=True)

        # checks for empty target
        if not cmds.getAttr(attr_name, multiIndices=True):
            continue

        # loop on actual targets and in-between targets
        for target in cmds.getAttr(attr_name, multiIndices=True):
            # target attribute name
            target_attr = "{}[{}]".format(attr_name, target)

            # checks for incoming connections on the geometry target
            if cmds.listConnections("{}.inputGeomTarget".format(target_attr),
                                    destination=False):

                logger.warning("{} can't be updated because it is a live "
                               "target".format(target_name))
                ignore.append(idx)
                continue

            # updates node copy target
            destination = target_attr.replace(target_attr.split(".")[0],
                                              node_copy)
            cmds.connectAttr(target_attr, destination, force=True)
            cmds.disconnectAttr(target_attr, destination)

        # skips updating target name if this was a life target
        if idx in ignore:
            continue

        # forces the weight attribute to be shown on the blendshape node
        cmds.setAttr("{}.weight[{}]".format(node_copy, idx), 0)

        # updates blendshape node attribute name
        if target_name:
            cmds.aliasAttr(target_name, "{}.weight[{}]"
                           .format(node_copy, idx))

    # gets targets on copied node to see if there is any node with zero target
    idx = cmds.getAttr("{}.weight".format(node_copy), multiIndices=True)
    if not idx:
        cmds.delete(node_copy)
        return

    return node_copy


def copy_map1_name(source, target):
    """ Copies the name of the uvSet at index zero (map1) to match it

    :param source: maya shape node
    :type source: str

    :param target: maya shape node
    :type target: str
    """

    if not is_matching_type(source, target):
        return

    source_uv_name = cmds.getAttr("{}.uvSet[0].uvSetName".format(source))

    try:
        cmds.setAttr("{}.uvSet[0].uvSetName".format(target), source_uv_name,
                     type="string")
    except RuntimeError:
        logger.debug("{} doesn't not have uvs, skipping udpate map1 name"
                     .format(target))
        return


@timer
def copy_cluster_weights(shape, weight_file, method="bilinear"):
    """ Copy cluster weights to the given shape from the given weight files

    :param shape: the shape node name containing the cluster deformers
    :type shape: str

    :param weight_file: containing the deformers and weight filter names
    :type weight_file: dict

    :param method: method type that should be used when updating the weights
    :type method: str
    """

    # gets the temporary folder path
    temp_path = get_temp_folder()
    short_name = get_prefix_less_name(shape)

    for node in weight_file:
        if not weight_file[node]:
            continue
        cmds.deformerWeights(weight_file[node], im=True, shape=short_name,
                             deformer=node, path=temp_path, method=method,
                             vertexConnections=True)


@timer
def copy_skin_weights(source_skin, target_skin):
    """ Copy skin weights from the given source skin cluster node to the target

    This function is isolated in order to extend research on faster methods
    to transfer skin weights from one node to another.

    :param source_skin: the source skin cluster node name
    :type source_skin: str

    :param target_skin: the target skin cluster node name
    :type target_skin: str
    """

    # gets the shape back from the source_skin and target_skin
    # need to do this as providing the sourceSkin and destinationSkin arguments
    # to the copySkinWeights command does not update correctly the shapes

    source_shape = cmds.ls(cmds.listHistory("{}.outputGeometry".format(
                           source_skin), pdo=False, future=True), dag=True,
                           noIntermediate=True)
    target_shape = cmds.ls(cmds.listHistory(
                           "{}.outputGeometry".format(target_skin),
                           pdo=False, future=True), dag=True,
                           noIntermediate=True)

    # checks if source and target shapes list are bigger than 1
    if len(source_shape) > 1:
        source_shape = source_shape[0]
    if len(target_shape) > 1:
        target_shape = target_shape[0]

    cmds.select(source_shape, target_shape)

    # copy skin command
    cmds.copySkinWeights(surfaceAssociation="closestPoint", noMirror=True,
                         influenceAssociation=("label",
                                               "closestJoint",
                                               "oneToOne"))

    # forces refresh
    cmds.refresh()


@timer
def create_blendshapes_backup(source, target, nodes):
    """ Creates an updated backup for the given blendshapes nodes on source

    .. important:: This method does not work as the other source/target type
                   of methods in flex. The source is the current geometry
                   before topology update containing the blendshape nodes.
                   We use it in order to create a wrap to the newer target
                   geometry topology.

    :param source: current shape node
    :type source: str

    :param target: new shape node
    :type target: str

    :return: backup blendshape nodes
    :rtype: list
    """

    logger.debug("Creating blendshapes backup")

    # gets simpler shape name
    shape_name = get_prefix_less_name(target)

    # get attributes types
    attrs = get_shape_type_attributes(target)

    # creates source duplicate
    intermediate = get_shape_orig(source)[0]
    source_duplicate = create_duplicate(intermediate, "{}_flex_bs_sourceShape"
                                        .format(shape_name))

    # first loops to create a clean copy of the blendshape nodes
    nodes_copy = []
    for node in nodes:
        duplicate = copy_blendshape_node(node, source_duplicate)
        if duplicate:
            nodes_copy.append(duplicate)

    # creates wrapped target shape
    warp_target = create_duplicate(target, "{}_flex_bs_warpShape"
                                   .format(shape_name))

    # wraps the duplicate to the source
    create_wrap(source_duplicate, warp_target)

    # creates blendshape target shape
    target_duplicate = create_duplicate(target, "{}_flex_bs_targetShape"
                                        .format(shape_name))

    return_nodes = []

    # loops on the blendshape nodes
    for node in nodes_copy:
        # creates transfer blendshape
        transfer_node = cmds.deformer(target_duplicate, type="blendShape",
                                      name="flex_transfer_{}".format(node))[0]

        # get blendshape targets indices. We skip verification because at this
        # stage the copied blendshapes nodes will always have targets
        targets_idx = cmds.getAttr("{}.weight".format(node), multiIndices=True)

        # loop on blendshape targets indices
        for idx in targets_idx or []:
            # input target group attribute
            attr_name = (BLENDSHAPE_TARGET.format(node, idx))

            # blendshape target name
            target_name = cmds.aliasAttr("{}.weight[{}]".format(node, idx),
                                         query=True)

            # loop on actual targets and in-between targets
            for target in cmds.getAttr(attr_name, multiIndices=True):

                # gets and sets the blendshape weight value
                weight = float((target - 5000) / 1000.0)
                cmds.setAttr("{}.weight[{}]".format(node, idx), weight)

                # geometry target attribute
                geometry_target_attr = "{}[{}].inputGeomTarget".format(
                    attr_name, target)

                shape_target = geometry_target_attr.replace(
                    geometry_target_attr.split(".")[0], transfer_node)

                # updates the target
                cmds.connectAttr("{}.{}".format(warp_target, attrs["output"]),
                                 shape_target, force=True)

                cmds.disconnectAttr("{}.{}"
                                    .format(warp_target, attrs["output"]),
                                    shape_target)

                cmds.setAttr("{}.weight[{}]".format(node, idx), 0)

            cmds.setAttr("{}.weight[{}]".format(transfer_node, idx), 0)

            if target_name:
                cmds.aliasAttr(target_name, "{}.weight[{}]".format(
                    transfer_node, idx))

        # adds blendshape node to nodes to return
        return_nodes.append("{}".format(transfer_node))

    # deletes backup process shapes
    cmds.delete(cmds.listRelatives(source_duplicate, parent=True),
                cmds.listRelatives(warp_target, parent=True))

    # forces refresh
    cmds.refresh()

    return return_nodes


def create_clusters_backup(shape, nodes):
    """ Generates weight files for the given cluster nodes in the given shape

    :param shape: the shape node name containing the cluster deformers nodes
    :type shape: str

    :param nodes: the cluster nodes
    :type nodes: list

    :return: cluster weight files names
    :rtype: dict
    """

    logger.info("Creating cluster weights backup for {}".format(nodes))

    # gets the temp folder path
    temp_path = get_temp_folder()

    # prefix less shape name
    shape = get_prefix_less_name(shape)

    # dict for weights files
    weight_files = {}

    for node in nodes:
        # If there is not weights creating the deformer maps is useless
        try:
            cmds.getAttr("{}.weightList[0].weights".format(node))
        except RuntimeError:
            weight_files[node] = None
            continue
        # Creates the weight map if weights are found on shape points
        cmds.deformerWeights('{}_{}.xml'.format(shape, node), export=True,
                             vertexConnections=True, weightPrecision=5,
                             shape=shape, deformer=node, path=temp_path)
        weight_files[node] = '{}_{}.xml'.format(shape, node)

    return weight_files


def create_deformers_backups(source, target, shape_orig, deformers):
    """ Handles creating the correct backup shapes for the given deformers

    :param source: the shape containing the new shape
    :type source: str

    :param target: the shape containing the deformers
    :type target: str

    :param shape_orig: the intermediate shape from the target shape
    :type shape_orig: str

    :param deformers: deformers used on target
    :type deformers: dict

    :return: deformers backups nodes created
    :rtype: list, list
    """

    # declare return values
    bs_nodes = []
    skin_nodes = []
    cluster_nodes = []

    # creates blendshapes nodes backup
    if len(deformers["blendShape"]):
        bs_nodes = create_blendshapes_backup(target, source,
                                             deformers["blendShape"])

    # creates skincluster nodes backup
    if len(deformers["skinCluster"]):
        skin_nodes = create_skincluster_backup(shape_orig,
                                               deformers["skinCluster"][0])
    # creates clusters nodes backup
    if len(deformers["cluster"]):
        cluster_nodes = create_clusters_backup(target, deformers["cluster"])

    return bs_nodes, skin_nodes, cluster_nodes


def create_duplicate(shape, duplicate_name):
    """ Creates a shape node duplicate

    :param shape: the shape node to duplicate
    :type shape: str

    :param name: the name for the duplicate
    :type name: str

    :return: the duplicated shape node
    :rtype: str
    """

    logger.debug("Creating shape duplicate for {}".format(shape))
    shape_holder = cmds.createNode(cmds.objectType(shape),
                                   name="{}Shape".format(duplicate_name))
    cmds.rename(shape_holder, "{}".format(shape_holder))
    update_shape(shape, shape_holder)

    return shape_holder


@timer
def create_skincluster_backup(shape, skin_node):
    """ Creates a skinning backup object

    :param shape: the shape node you want to duplicate (should use orig shape)
    :type shape: str

    :param skin_node: the given shape skin cluster node
    :type skin_node: str

    :return: the skin cluster node backup
    :rtype: str
    """

    logger.info("Creating skin backup for {}".format(skin_node))

    # gets the skin cluster influences
    influences = cmds.listConnections("{}.matrix".format(skin_node))

    # creates a duplicate shape of the given shape
    holder_name = "{}_flex_skin_shape_holder".format(
        get_prefix_less_name(shape))
    shape_duplicate = create_duplicate(shape, holder_name)

    # creates new skin cluster node on duplicate
    skin_holder = cmds.skinCluster(influences, shape_duplicate, bindMethod=0,
                                   obeyMaxInfluences=False, skinMethod=0,
                                   weightDistribution=0, normalizeWeights=1,
                                   removeUnusedInfluence=False, name="{}_SKN"
                                   .format(holder_name))

    # copy the given skin node weights to back up shape
    copy_skin_weights(skin_node, skin_holder[0])

    return ["{}".format(skin_holder[0])]


def create_wrap(source, target, intermediate=None):
    """ Creates a wrap deformer on the target by using source as driver

    :param source: the maya source node
    :type source: str

    :param target: the maya target node
    :type target: str

    :param intermediate: the intermediate shape to use on the warp node
    :type intermediate: str

    :return: wrap node
    :rtype: str
    """

    logger.debug("Creating wrap deformer for {} using {}".format(target,
                                                                 source))

    # creates the deformer
    target_type = cmds.objectType(target)
    wrap_node = cmds.deformer(target, type="wrap", name="flex_warp")[0]
    cmds.setAttr("{}.exclusiveBind".format(wrap_node), 1)
    cmds.setAttr("{}.autoWeightThreshold".format(wrap_node), 1)
    cmds.setAttr("{}.dropoff[0]".format(wrap_node), 4.0)

    # sets settings for nurbs type shapes
    if target_type == "nurbsSurface" or target_type == "nurbsCurve":
        cmds.setAttr("{}.nurbsSamples[0]".format(wrap_node), 10)
    # sets settings for mesh type shapes
    else:
        cmds.setAttr("{}.inflType[0]".format(wrap_node), 2)

    # gets attributes types for the given target
    attrs = get_shape_type_attributes(target)

    # filters intermediate shape
    intermediate_shape = filter_shape_orig(source, intermediate)

    # connects the wrap node to the source
    cmds.connectAttr("{}.{}".format(intermediate_shape, attrs["output_world"]),
                     "{}.basePoints[0]".format(wrap_node), force=True)
    cmds.connectAttr("{}.{}".format(source, attrs["output"]),
                     "{}.driverPoints[0]".format(wrap_node), force=True)
    cmds.connectAttr("{}.worldMatrix[0]".format(target),
                     "{}.geomMatrix".format(wrap_node), force=True)

    return wrap_node


def delete_transform_from_nodes(nodes):
    """ Deletes the dag object transform node found from the given nodes

    :param shape: nodes names
    :type shape: list
    """

    for node in nodes:
        try:
            shape = [x for x in cmds.listHistory(node, future=True)
                     if x not in cmds.listHistory(node, future=True, pdo=True)]
            transform = cmds.listRelatives(shape, parent=True)
            cmds.delete(transform)
        except ValueError:
            return


def filter_shape_orig(shape, intermediate):
    """ Filters whether the intermediate shape provided should be used or not

    if an intermediate isn't provided then

    :param shape: the shape node name
    :type shape: str

    :param intermediate: the intermediate shape name
    :type intermediate: str

    :return: the valid intermediate shape
    :rtype: str
    """

    # gets source intermediate shape if any
    orig = get_shape_orig(shape)

    # return the orig shape if no intermediate was provided and one is found
    if not intermediate and orig:
        return orig[0]

    # return the provided intermediate shape
    elif intermediate:
        return intermediate

    # return the shape if no intermediate was given and no orig shape was found
    else:
        return shape


def set_deformer_off(deformer):
    """ Set envelope attribute to **0** on the given deformer

    :param deformer: deformer node
    :type deformer: str
    """

    # sets attribute to zero
    try:
        cmds.setAttr("{}.envelope".format(deformer), 0)

    # if connections are found on the attribute then mute node is used
    except RuntimeError:
        mute_node = cmds.mute("{}.envelope".format(deformer), force=True)[0]
        cmds.setAttr("{}.hold".format(mute_node), 0)


def set_deformer_on(deformer):
    """ Set envelope attribute to **1** on the given deformer

    :param deformer: deformer node
    :type deformer: str
    """

    # sets attribute to zero
    try:
        cmds.setAttr("{}.envelope".format(deformer), 1)

    # if connections are found on the attribute then mute node is removed
    except RuntimeError:
        cmds.mute("{}.envelope".format(deformer), disable=True, force=True)


def set_deformer_state(deformers, enable):
    """ Set envelope attribute to one on the given deformers dictionary

    :param deformers: dict containing the deformers set by type
    :type deformers: type

    :param enable: on or off state for the given deformers
    :type enable: bool
    """

    logger.debug("Setting deformers {} envelop enable to: {}"
                 .format(deformers, enable))

    # Loop of the deformer dict and set state
    for deformer_type in deformers:
        for i in deformers[deformer_type] or []:
            if enable:
                set_deformer_on(i)
                continue
            set_deformer_off(i)


def update_shape(source, target):
    """ Connect the shape output from source to the input shape on target

    :param source: maya shape node
    :type source: str

    :param target: maya shape node
    :type target: str
    """

    # clean uvs on mesh nodes
    clean_uvs_sets(target)

    # get attributes names
    attributes = get_shape_type_attributes(source)

    logger.debug("Updating shape: {} using --> {}".format(target, source))

    # updates the shape
    cmds.connectAttr("{}.{}".format(source, attributes["output"]),
                     "{}.{}".format(target, attributes["input"]),
                     force=True)

    # forces shape evaluation to achieve the update
    cmds.dgeval("{}.{}".format(target, attributes["output"]))

    # finish shape update
    cmds.disconnectAttr("{}.{}".format(source, attributes["output"]),
                        "{}.{}".format(target, attributes["input"]))
