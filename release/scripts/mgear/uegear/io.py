#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains functions related with Maya Import/Export functionality for ueGear.
"""

from __future__ import print_function, division, absolute_import

import os

import maya.cmds as cmds

from mgear.core import pyFBX
from mgear.uegear import utils, log

logger = log.uegear_logger

__ASSETIO_VERSION__ = '0.0.0'

SETUP_PIVOT_LOC_NAME = 'loc_origin'
TAG_ATTR_NAME = 'ueGearAssetTag'

# ======================================================================================================================
# TAGS
# ======================================================================================================================


class TagTypes(object):
	"""
	Class that holds all available tag types.
	"""

	Skeleton = 'skeleton'
	StaticMesh = 'staticmesh'
	SkeletalMesh = 'skeletalmesh'
	Camera = 'camera'
	Alembic = 'alembic'
	MetahumanBody = 'metahumanbody'
	MetahumanFace = 'metahumanface'


def auto_tag(node=None, remove=False):
	"""
	Automatically tags given (or current selected nodes) so ueGear exporter can identify how to export the specific
	nodes.

	:param str or list(str) or None node: node/s to tag.
	:param bool remove: if True tag will be removed.
	"""

	nodes = utils.force_list(node or cmds.ls(sl=True))

	for node in nodes:
		found_skin_clusters = utils.get_skin_clusters_for_node(node)
		if found_skin_clusters and cmds.objectType(node) == 'joint':
			remove_tag(node) if remove else apply_tag(node, attribute_value=TagTypes.SkeletalMesh)
		else:
			shapes = cmds.listRelatives(node, shapes=True)
			if not shapes:
				continue
			first_shape = utils.get_first_in_list(shapes)
			if not first_shape:
				continue
			object_type = cmds.objectType(first_shape)
			if object_type == 'mesh':
				found_skin_clusters = utils.get_skin_clusters_for_node(first_shape)
				if found_skin_clusters:
					remove_tag(node) if remove else apply_tag(node, attribute_value=TagTypes.Skeleton)
				else:
					remove_tag(node) if remove else apply_tag(node, attribute_value=TagTypes.StaticMesh)
			elif object_type == 'camera':
				remove_tag(node) if remove else apply_tag(node, attribute_value=TagTypes.Camera)


def apply_tag(node=None, attribute_name=TAG_ATTR_NAME, attribute_value=''):
	"""
	Creates a new tag attribute with given value into given node/s (or selected nodes).

	:param str or list(str) or None node: nodes to apply tag to.
	:param str attribute_name: tag attribute value to use. By default, TAG_ATTR_NAME will be used.
	:param str attribute_value: value to set tag to.
	"""

	nodes = utils.force_list(node or cmds.ls(sl=True))
	attribute_value = str(attribute_value)
	for node in nodes:
		if not cmds.attributeQuery(attribute_name, node=node, exists=True):
			cmds.addAttr(node, longName=attribute_name, dataType='string')
		cmds.setAttr('{}.{}'.format(node, attribute_name), attribute_value, type='string')
		if attribute_value:
			logger.info('Tagged "{}.{}" as {}.'.format(node, attribute_name, attribute_value))
		else:
			logger.info('Tagged "{}.{}" as empty.'.format(node, attribute_name))


def remove_tag(node=None, attribute_name=''):

	nodes = utils.force_list(node or cmds.ls(sl=True))
	for node in nodes:
		if cmds.attributeQuery(attribute_name, node=node, exists=True):
			cmds.deleteAttr('{}.{}'.format(node, attribute_name))
			logger.info('Removed attribute {} from "{}"'.format(node, attribute_name))


def apply_alembic_tag(node=None, remove=False):
	"""
	Applies alembic tag to given node/s (or selected nodes).

	:param str or list(str) or None node: node/s to tag.
	:param bool remove: if True tag will be removed.
	"""

	remove_tag(node=node) if remove else apply_tag(node=node, attribute_value=TagTypes.Alembic)


def find_tagged_nodes(tag_name=TAG_ATTR_NAME, nodes=None):
	"""
	Returns a list with all nodes that are tagged with the given tag name and has a value set.

	:param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
	:param str or list(str) or None nodes: list of nodes to find tags of, if not given all nodes in the scene will be
		checked.
	:return: list of found tagged nodes.
	:rtype: list(str)
	"""

	found_tagged_nodes = list()
	nodes = utils.force_list(nodes or cmds.ls())
	for node in nodes:
		if not cmds.attributeQuery(tag_name, node=node, exists=True):
			continue
		if not cmds.getAttr('{}.{}'.format(node, TAG_ATTR_NAME)):
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


def find_tagged_node_attributes(tag_name=TAG_ATTR_NAME, nodes=None):
	"""
	Returns a list with all node attributes that are tagged with the given tag name and has a value set.

	:param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
	:param str or list(str) or None nodes: list of nodes to find tags of, if not given all nodes in the scene will be
		checked.
	:return: list of found tagged nodes.
	:rtype: list(str)
	"""

	found_tagged_node_attributes = list()
	nodes = utils.force_list(nodes or cmds.ls())
	for node in nodes:
		if not cmds.attributeQuery(tag_name, node=node, exists=True):
			continue
		if not cmds.getAttr('{}.{}'.format(node, TAG_ATTR_NAME)):
			continue
		found_tagged_node_attributes.append('{}.{}'.format(node, TAG_ATTR_NAME))

	return found_tagged_node_attributes


def find_tagged_selected_node_attributes(tag_name):
	"""
	Returns a list with all selected node attributes that are tagged with the given tag name and has a value set.

	:param str tag_name: name of the tag to search. By default, TAG_ATTR_NAME will be used.
	:return: list of found tagged nodes.
	:rtype: list(str)
	"""

	return find_tagged_node_attributes(nodes=cmds.ls(sl=True))

# ======================================================================================================================
# SKELETAL MESHES
# ======================================================================================================================


def export_skeleton(file_path='', skeleton_name='', skeleton_list='', output_file=''):

	logger.info('Writing out ueGear Skeleton JSON file...')

	data = {
		'version': __ASSETIO_VERSION__,
		'data': [
			{
				'outputFile': output_file,
				'joints': skeleton_list
			}
		]
	}
	out_file_path = '{}{}.json'.format(file_path, output_file)

	return utils.write_to_json_file(data, out_file_path, sort_keys=False)


# ======================================================================================================================
# ASSETS
# ======================================================================================================================


@utils.timer
@utils.viewport_off
@utils.keep_selection_decorator
def export_assets(tag_name=TAG_ATTR_NAME, nodes=None, check_assets=True):

	if check_assets:
		check_scene(tag_name=tag_name, nodes=nodes)

	objects_map = dict()
	tags = set()

	tagged_node_attributes = find_tagged_node_attributes(tag_name=tag_name, nodes=nodes)
	for tagged_node_attribute in tagged_node_attributes:
		tags.add(cmds.getAttr(tagged_node_attribute))
	tags = list(tags)

	for tag in tags:
		objects_map.setdefault(str(tag), list())

	for tagged_node_attribute in tagged_node_attributes:
		tagged_node = tagged_node_attribute.replace('.{}'.format(tag_name), '')
		objects_map[cmds.getAttr(tagged_node_attribute)].append(tagged_node)

	maya_file_path = cmds.file(query=True, sceneName=True)
	maya_file_name = os.path.basename(maya_file_path)
	output_path = os.path.join(os.path.dirname(maya_file_path), 'output')
	version_string = maya_file_name.split('_')[-1].split('.')[0]
	group_name = ''
	category = ''
	variant_override = ''
	scene_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-3]
	shot_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-2]
	is_shot = False if 'assets' in maya_file_path else True

	file_check_state = cmds.file(query=True, modified=True)
	if file_check_state:
		cmds.file(save=True)

	maya_file_path = cmds.file(query=True, sceneName=True)
	start_frame = int(cmds.playbackOptions(q=1, min=1))
	end_frame = int(cmds.playbackOptions(q=1, max=1))

	if not os.path.isdir(output_path):
		os.makedirs(output_path)
	if not os.path.isdir(output_path):
		logger.error('Was not possible to create export output directory: "{}"'.format(output_path))
		return False

	static_meshes = objects_map.get(TagTypes.StaticMesh, list())
	if static_meshes:
		for static_mesh in static_meshes:
			cmds.select(static_mesh)
			output_file = '{}.fbx'.format(static_mesh.replace(':', '_'))
			export_path = utils.clean_path(os.path.join(output_path, output_file))
			if not is_shot:
				pyFBX.FBXExportBakeComplexStart(v=True)
				pyFBX.FBXExportBakeComplexEnd(v=True)
				pyFBX.FBXExportFileVersion(v='FBX201400')
				pyFBX.FBXExportConstraints(v=False)
				pyFBX.FBXExportApplyConstantKeyReducer(v=False)
				pyFBX.FBXExportAxisConversionMethod('none')
				pyFBX.FBXExportCameras(v=False)
				pyFBX.FBXExportInAscii(v=True)
				pyFBX.FBXExportSkeletonDefinitions(v=True)
				pyFBX.FBXExportEmbeddedTextures(v=False)
				pyFBX.FBXExportAnimationOnly(v=False)
				pyFBX.FBXExportBakeComplexAnimation(v=True)
				pyFBX.FBXExportBakeComplexStep(v=True)
				pyFBX.FBXExportShapes(v=True)
				pyFBX.FBXExportSkins(v=True)
				pyFBX.FBXExportSmoothingGroups(v=True)
				pyFBX.FBXExportSmoothMesh(v=False)
				pyFBX.FBXExportTangents(v=False)
				pyFBX.FBXExportTriangulate(v=True)
				pyFBX.FBXExportInputConnections(v=False)
				pyFBX.FBXExport(f=export_path, s=True)
				logger.info('\nExported {}'.format(export_path))
		group_name = utils.get_first_in_list(cmds.listRelatives(objects_map[TagTypes.StaticMesh][0], p=True)) or ''
		category = utils.get_first_in_list(cmds.listRelatives(group_name, p=True)) or ''
		if ':' in group_name:
			group_name = group_name.split(':')[-1]
		export_assets_json(
			source_file=maya_file_path, file_path=output_path, output_file=group_name, file_type='fbx',
			version=version_string, category=category, group_name=group_name, tag_name=TagTypes.StaticMesh,
			nodes=static_meshes, start_frame=start_frame, end_frame=end_frame, is_shot=is_shot)

	for camera in objects_map.get(TagTypes.Camera, list()):
		camera_shape = utils.get_first_in_list(cmds.listRelatives(camera, shapes=True))
		if not camera_shape:
			logger.warning('Impossible to export camera: {} because it has no shapes')
			continue

		cmds.select(camera)
		output_file = '{}.fbx'.format(camera.replace(':', '_'))
		export_path = utils.clean_path(os.path.join(output_path, output_file))
		pyFBX.FBXExportCameras(v=True)
		pyFBX.FBXExportFileVersion(v='FBX201400')
		pyFBX.FBXExportBakeComplexAnimation(v=True)
		pyFBX.FBXExportBakeComplexStart(v=start_frame)
		pyFBX.FBXExportBakeComplexEnd(v=end_frame)
		pyFBX.FBXExportBakeComplexStep(v=True)
		pyFBX.FBXExportInputConnections(v=0)
		pyFBX.FBXExport(f=export_path, s=True)

		custom_params = {
			'aspectratio' : cmds.camera(camera_shape, q=True, aspectRatio=True),
			'cameraScale' : cmds.camera(camera_shape, q=True, cameraScale=True),
			'clippingPlanes' : cmds.camera(camera_shape, q=True, clippingPlanes=True),
			'farClipPlane' : cmds.camera(camera_shape, q=True, farClipPlane=True),
			'nearClipPlane' : cmds.camera(camera_shape, q=True, nearClipPlane=True),
			'focalLength' : cmds.camera(camera_shape, q=True, focalLength=True),
			'fStop' : cmds.camera(camera_shape, q=True, fStop=True),
			'horizontalFilmAperture' : cmds.camera(camera_shape, q=True, horizontalFilmAperture=True) * 25.4,
			'verticalFilmAperture' : cmds.camera(camera_shape, q=True, verticalFilmAperture=True) * 25.4,
			'lensSqueezeRatio' : cmds.camera(camera_shape, q=True, lensSqueezeRatio=True)
		}
		export_assets_json(
			source_file=maya_file_path, file_path=output_path, output_file=output_file.replace('.fbx', ''),
			file_type='fbx', version=version_string, tag_name=TagTypes.Camera, nodes=[camera], start_frame=start_frame,
			end_frame=end_frame, is_shot=is_shot, scene_string=scene_string, shot_string=shot_string,
			custom_params=custom_params)
		logger.info('\nExported {}'.format(export_path))

	for joint in objects_map.get(TagTypes.Skeleton, list()):
		pass

	for alembic in objects_map.get(TagTypes.Alembic, list()):
		pass

	logger.info('Asset export process completed successfully!')

	return True


def export_selected_assets(tag_name=TAG_ATTR_NAME, check_assets=True):

	return export_assets(tag_name=tag_name, nodes=cmds.ls(sl=True), check_assets=check_assets)


def export_assets_json(
		source_file='', output_file='', file_path='', file_type='', category='', group_name='', tag_name='', nodes=None,
		**kwargs):

	output_file_path = utils.clean_path('{}.json'.format(os.path.join(file_path, output_file)))
	fps_value = utils.get_frame_rate()
	is_shot = kwargs.get('is_shot', True)

	if is_shot:
		data = {
			'version': __ASSETIO_VERSION__,
			'data': [
				{

				}
			]
		}
	else:
		data = {
			'version': __ASSETIO_VERSION__,
			'data': [
				{
					'sourceFile': source_file,
					'outputFile': output_file,
					'filePath': file_path,
					'fileType': file_type,
					'category': category,
					'groupName': group_name,
					'tag': tag_name,
					'fps': fps_value,
					'nodes': nodes,
					'version': kwargs.get('version_string', ''),
					'skeletonType': kwargs.get('skeleton_type', 'custom'),
					'startFrame': kwargs.get('start_frame', 1),
					'endFrame': kwargs.get('end_frame', 1),
				}
			]
		}

	return utils.write_to_json_file(data, output_file_path, sort_keys=False)


# ======================================================================================================================
# LAYOUT
# ======================================================================================================================

@utils.timer
@utils.viewport_off
def export_layout_json(nodes=None, output_path=None):

	maya_file_path = cmds.file(query=True, sceneName=True)
	scene_file = os.path.basename(maya_file_path)
	if not output_path or not os.path.isdir(output_path):
		output_path = utils.clean_path(os.path.join(os.path.dirname(maya_file_path), 'output'))
	output_file = utils.clean_path(os.path.join(output_path, '{}_layout.json'.format(os.path.splitext(scene_file)[0])))

	if not os.path.isdir(output_path):
		os.makedirs(output_path)
	if not os.path.isdir(output_path):
		logger.error('Export directory does not exists: {}'.format(output_path))
		return False

	layout_map = dict()

	nodes = nodes or cmds.ls(sl=True)
	found_meshes = list()
	for node in nodes:
		if not utils.node_is_mesh(node):
			continue
		found_meshes.append(node)
	if not found_meshes:
		logger.warning('No layout meshes to export!')
		return False

	for mesh in found_meshes:
		translation_value, rotation_value, scale_value = utils.get_transforms_for_mesh_node(mesh)
		source_name_output = mesh.rsplit('_', 1)[0]
		if ':' in source_name_output:
			source_name_output = source_name_output.split(':')[-1]
		layout_map.setdefault(mesh, {
			'translation': translation_value,
			'rotation': rotation_value,
			'scale': scale_value,
			'sourceName': source_name_output
		})

	result = utils.write_to_json_file(layout_map, output_file)
	if not result:
		logger.error('Something went wrong while exporting layout JSON file')
	else:
		logger.info('Layout file exported successfully: {}'.format(output_file))

	return output_file if result else ''


# ======================================================================================================================
# HELPERS
# ======================================================================================================================


def check_scene(tag_name=TAG_ATTR_NAME, nodes=None):
	"""
	Checks scene for correct setup for Unreal export.

	:param str tag_name: name of the tag to check for. By default, TAG_ATTR_NAME will be used.
	:param str or list(str) or None nodes: list of nodes to check, if not given all nodes in the scene will be checked.
	:return: True if the scene check was successful; False otherwise.
	:rtype: bool
	"""

	objects_map = dict()

	maya_file_path = cmds.file(query=True, sceneName=True)

	if '/assets/' not in maya_file_path and '/scenes/' not in maya_file_path:
		logger.error('Please place this Maya file under either and assets or scenes folder')
		return False

	tagged_nodes_attributes_list = find_tagged_node_attributes(tag_name=tag_name, nodes=nodes)
	if not tagged_nodes_attributes_list:
		logger.warning('No objects tagged for ueGear to export.')
		return False

	tag_list = set()
	for tagged_node_attribute in tagged_nodes_attributes_list:
		tag_list.add(cmds.getAttr(tagged_node_attribute))
	tag_list = list(tag_list)

	for found_tag in tag_list:
		objects_map.setdefault(str(found_tag), list())

	for tagged_node_attribute in tagged_nodes_attributes_list:
		tagged_node = tagged_node_attribute.replace('.{}'.format(tag_name), '')
		objects_map[str(cmds.getAttr(tagged_node_attribute))].append(tagged_node)

	for static_mesh in objects_map.get(TagTypes.StaticMesh, list()):
		instances = utils.get_instances(static_mesh)
		if instances:
			logger.warning(
				'{} Static Mesh can be instance, but if they are instances before fixing pivots, will not be able to '
				'be fixed and can lead to unexpected transform offset within Unreal Engine.'.format(static_mesh))
			continue

		first_shape = utils.get_first_in_list(cmds.listRelatives(static_mesh, shapes=True)) or None
		if not first_shape or not cmds.objectType(first_shape) == 'mesh':
			logger.error('Static Mesh nodes must be mesh nodes. Please fix: "{}"'.format(static_mesh))
			continue

		if '/assets/' in maya_file_path:
			translation = cmds.xform(static_mesh, t=True, ws=True, query=True)
			rotation = cmds.xform(static_mesh, ro=True, ws=True, query=True)
			scale = cmds.xform(static_mesh, s=True, ws=True, query=True)
			if not translation == [0.0, 0.0, 0.0] or not rotation == [0.0, 0.0, 0.0] or not scale == [1.0, 1.0, 1.0]:
				logger.error('Static Meshes nodes must have zero transforms. Please zero out: "{}"'.format(
					static_mesh))
				continue

		category_name_group = None
		asset_name_group = utils.get_first_in_list(cmds.listRelatives(static_mesh, p=True) or list())
		if asset_name_group and cmds.objectType(asset_name_group) == 'transform':
			category_name_group = utils.get_first_in_list(cmds.listRelatives(asset_name_group, p=True) or list())
		if not asset_name_group or not category_name_group:
			logger.error(
				'Static Meshes must have a category group and an asset name group above them, for example: '
				'env/warehouse/<static_mesh>. Please fix: "{}"'.format(static_mesh))
			continue

	for joint in objects_map.get(TagTypes.Skeleton, list()):
		if not cmds.objectType(joint) == 'joint':
			logger.error('Skeleton tags must be on a joint. Please fix: "{}"'.format(joint))
			continue
		if cmds.listRelatives(joint, parent=True):
			logger.error(
				'Skeleton tags must be on top level (no parent) root joint on your hierarchy. '
				'Please fix: "{}"'.format(joint))
			continue

		mesh_list = list()
		found_skin_clusters = utils.get_skin_clusters_for_node(joint)
		for skin_cluster in found_skin_clusters:
			mesh_list.extend(utils.get_skin_cluster_meshes(skin_cluster))
		for skeletal_mesh in mesh_list:

			category_name_group = None
			asset_name_group = utils.get_first_in_list(cmds.listRelatives(skeletal_mesh, p=True) or list())
			if asset_name_group and cmds.objectType(asset_name_group) == 'transform':
				category_name_group = utils.get_first_in_list(cmds.listRelatives(asset_name_group, p=True) or list())
			if not asset_name_group or not category_name_group:
				logger.error(
					'Skeletal Meshes (skinned meshes) must have a category group and an asset name group above '
					'them, for example: env/warehouse/<static_mesh>. Please fix: "{}"'.format(skeletal_mesh))
				continue

	for camera in objects_map.get(TagTypes.Camera, list()):
		first_shape = utils.get_first_in_list(cmds.listRelatives(camera, shapes=True)) or None
		if not first_shape or not cmds.objectType(first_shape) == 'camera':
			logger.error('Camera tags should be on the actual camera object. Please fix: "{}"'.format(camera))
			continue

	logger.info('Scene check complete!')

	return True


@utils.keep_selection_decorator
def setup_geometry_pivot_for_unreal(node=None, move_to_origin=True):
	"""
	Moves the given nodes (or selected nodes if no nodes are given) to origin, freezes transforms and places the pivot
	at the origin of the scene.

	:param str or list(str) or None node: geometry node/s to setup pivots, so they can be exported into Unreal properly.
	:param bool move_to_origin: whether to move geometry to origin.
	"""

	nodes = utils.force_list(node or cmds.ls(sl=True))
	for node in nodes:
		instances = utils.get_instances(nodes=node)
		if not instances:
			previous_parent = None
			node = node.replace('|', '')
			if cmds.objExists(node):
				try:
					cmds.makeIdentity(node, apply=True, t=True, r=True, s=True)
				except Exception:
					logger.warning('Skipping freezing: "{}"'.format(node))
					continue
				shapes = cmds.listRelatives(node, shapes=True, fullPath=True)
				if shapes:
					object_type = cmds.objectType(shapes)
					if object_type == 'mesh':
						cmds.delete(node, constructionHistory=True)
						parent = utils.get_first_in_list(cmds.listRelatives(node, parent=True, fullPath=True) or list())
						if parent:
							previous_parent = parent
							cmds.parent(node, world=True)

						if not cmds.objExists(SETUP_PIVOT_LOC_NAME):
							cmds.spaceLocator(name=SETUP_PIVOT_LOC_NAME)

						cmds.xform(node, p=True, cp=True)
						bbox = cmds.exactWorldBoundingBox(node)
						bottom = [(bbox[0] + bbox[3])/2, bbox[1], (bbox[2] + bbox[5])/2]
						cmds.xform(node, piv=bottom, ws=True)

						current_locator = cmds.spaceLocator(name=node.replace('|', '_') + '_loc')[0]
						cmds.matchTransform(current_locator, node)

						current_offset_locator = cmds.spaceLocator(name=current_locator.replace('_loc', '_offset_loc'))[0]
						cmds.matchTransform(current_offset_locator, node)
						cmds.parent(node, current_locator)
						cmds.matchTransform(current_locator, SETUP_PIVOT_LOC_NAME)
						cmds.parent(node, world=True)
						cmds.makeIdentity(node, apply=True, t=True, r=True, s=True)
						cmds.parent(node, current_locator)

						if not move_to_origin:
							cmds.matchTransform(current_locator, current_offset_locator)

						if previous_parent:
							cmds.parent(node, previous_parent)
						else:
							cmds.parent(node, world=True)

						cmds.delete(current_locator)
						cmds.delete(current_offset_locator)
		else:
			logger.info(
				'Skipping fixing the pivot for "{}" because it is an instance which is not compatible with freezing '
				'transforms')

		if cmds.objExists(SETUP_PIVOT_LOC_NAME):
			cmds.delete(SETUP_PIVOT_LOC_NAME)
