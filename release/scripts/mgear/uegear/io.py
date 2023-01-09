#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains functions related with Maya Import/Export functionality for ueGear.
"""

from __future__ import print_function, division, absolute_import

import os

import maya.mel as mel
import maya.cmds as cmds

from mgear.core import pyFBX
from mgear.uegear import utils, log, tag, ioutils

logger = log.uegear_logger

__ASSETIO_VERSION__ = '0.0.0'

SETUP_PIVOT_LOC_NAME = 'loc_origin'


# ======================================================================================================================
# ASSETS
# ======================================================================================================================

def exportable_assets(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None, asset_type=None):
	"""
	Returns a dictionary with all exportable assets stored based on tag asset type.

	:param str tag_name: name of the tag that exporter should use to check the asset type to export.
	:param list(str) nodes: list of nodes to check, if not given all scene nodes will be taken into consideration.
	:param str asset_type: optional asset type to look for.
	:return: assets map dictionary.
	:rtype: dict
	"""

	tags = set()
	objects_map = dict()

	tagged_node_attributes = tag.find_tagged_node_attributes(tag_name=tag_name, nodes=nodes)
	for tagged_node_attribute in tagged_node_attributes:
		tag_found = cmds.getAttr(tagged_node_attribute)
		if not tag_found or (asset_type and tag_found != asset_type):
			continue
		tags.add(tag_found)
	tags = list(tags)

	for found_tag in tags:
		objects_map.setdefault(str(found_tag), list())

	for tagged_node_attribute in tagged_node_attributes:
		tag_found = cmds.getAttr(tagged_node_attribute)
		if not tag_found or (asset_type and tag_found != asset_type):
			continue
		tagged_node = tagged_node_attribute.replace('.{}'.format(tag_name), '')
		objects_map[tag_found].append(tagged_node)

	return objects_map


@utils.timer
@utils.viewport_off
@utils.keep_selection_decorator
def export_assets(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None, check_assets=True):
	"""
	Exports nodes as assets based on the current tagged values.

	:param str tag_name: name of the tag that exporter should use to check the asset type to export.
	:param list(str) nodes: list of nodes to export, if not given all scene nodes will be taken into consideration.
	:param bool check_assets: whether a check scene should be done before exporting the assets.
	:return: True if the export operation was successful; False otherwise.
	:rtype: bool
	"""

	if check_assets:
		check_scene(tag_name=tag_name, nodes=nodes)

	utils.save_modified_scene()

	objects_map = exportable_assets(tag_name, nodes=nodes)
	if not objects_map:
		logger.warnign('No assets to export found!')
		return False

	static_meshes = objects_map.get(tag.TagTypes.StaticMesh, list())
	if static_meshes:
		export_static_meshes(tag_name=tag_name, nodes=static_meshes, check_assets=False)

	cameras = objects_map.get(tag.TagTypes.Camera, list())
	if cameras:
		export_cameras(tag_name=tag_name, nodes=cameras, check_assets=False)

	skeletons = objects_map.get(tag.TagTypes.Skeleton, list())
	if skeletons:
		export_skeletons(tag_name=tag_name, nodes=skeletons, check_assets=False)

	alembics = objects_map.get(tag.TagTypes.Alembic, list())
	if alembics:
		export_alembics(tag_name=tag_name, nodes=alembics, check_assets=False)

	logger.info('Asset export process completed successfully!')

	return True


def export_selected_assets(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, check_assets=True):
	"""
	Exports the selected nodes as assets based on the current tagged values.

	:param str tag_name: name of the tag that exporter should use to check the asset type to export.
	:param bool check_assets: whether a check scene should be done before exporting the assets.
	:return: True if the export operation was successful; False otherwise.
	:rtype: bool
	"""

	return export_assets(tag_name=tag_name, nodes=cmds.ls(sl=True), check_assets=check_assets)


def export_assets_json(
		source_file='', output_file='', file_path='', file_type='', category='', group_name='', tag_name='', nodes=None,
		start_frame=1, end_frame=1, is_shot=True, scene_string='', shot_string='', version_string='', **kwargs):

	output_file_path = utils.clean_path('{}.json'.format(os.path.join(file_path, output_file)))
	fps_value = utils.get_frame_rate()

	if is_shot:

		if cmds.referenceQuery(nodes[0], isNodeReferenced=True):
			root_path = source_file.split('/')
			scene_string = root_path[-3]
			shot_string = root_path[-2]
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
					'nodes': nodes,
					'version': version_string,
					'scene': scene_string,
					'shot': shot_string,
					'fps': fps_value,
					'startFrame': start_frame,
					'endFrame': end_frame,
					'variantOverride': kwargs.get('variant_override', ''),
					'customParams': kwargs.get('custom_params', dict())
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
					'version': version_string,
					'skeletonType': kwargs.get('skeleton_type', 'custom'),
					'startFrame': start_frame,
					'endFrame': end_frame,
				}
			]
		}

	return utils.write_to_json_file(data, output_file_path, sort_keys=False)


# ======================================================================================================================
# STATIC MESHES
# ======================================================================================================================

@utils.timer
@utils.viewport_off
@utils.keep_selection_decorator
def export_static_meshes(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None, check_assets=True):

	static_meshes = utils.force_list(nodes or exportable_assets(
		tag_name, asset_type=tag.TagTypes.StaticMesh).get(tag.TagTypes.StaticMesh, list()))
	if not static_meshes:
		logger.warning('No static meshes to export found!')
		return False

	if check_assets:
		result = check_scene(tag_name=tag_name, nodes=static_meshes)
		if not result:
			logger.warning('Scene check was not valid!')
			return False

	maya_file_path = utils.clean_path(cmds.file(query=True, sceneName=True))
	maya_file_name = os.path.basename(maya_file_path)
	output_path = utils.clean_path(os.path.join(os.path.dirname(maya_file_path), 'output'))
	version_string = maya_file_name.split('_')[-1].split('.')[0]
	start_frame = int(cmds.playbackOptions(q=1, min=1))
	end_frame = int(cmds.playbackOptions(q=1, max=1))

	if not os.path.isdir(output_path):
		os.makedirs(output_path)
	if not os.path.isdir(output_path):
		logger.error('Was not possible to create export output directory: "{}"'.format(output_path))
		return False

	for static_mesh in static_meshes:
		ioutils.export_static_mesh(output_path, static_mesh)
	group_name = utils.get_first_in_list(cmds.listRelatives(nodes[0], p=True)) or ''
	category = utils.get_first_in_list(cmds.listRelatives(group_name, p=True)) or ''
	if ':' in group_name:
		group_name = group_name.split(':')[-1]

	export_assets_json(
		source_file=maya_file_path, file_path=output_path, output_file=group_name, file_type='fbx',
		version=version_string, category=category, group_name=group_name, tag_name=tag.TagTypes.StaticMesh,
		nodes=nodes, start_frame=start_frame, end_frame=end_frame, is_shot=False)

	logger.info('\nStatic meshes exported {}'.format(output_path))

	return True


@utils.timer
@utils.viewport_off
@utils.keep_selection_decorator
def export_alembics(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None, check_assets=True):

	logger.info('Writing out ueGear Alembic JSON file...')

	alembics = utils.force_list(nodes or exportable_assets(
		tag_name, asset_type=tag.TagTypes.Alembic).get(tag.TagTypes.Alembic, list()))
	if not alembics:
		logger.warning('No alembic meshes to export found!')
		return False

	if check_assets:
		result = check_scene(tag_name=tag_name, nodes=alembics)
		if not result:
			logger.warning('Scene check was not valid!')
			return False

	maya_file_path = utils.clean_path(cmds.file(query=True, sceneName=True))
	maya_file_name = os.path.basename(maya_file_path)
	output_path = utils.clean_path(os.path.join(os.path.dirname(maya_file_path), 'output'))
	version_string = maya_file_name.split('_')[-1].split('.')[0]
	scene_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-3]
	shot_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-2]
	is_shot = False if 'assets' in maya_file_path else True
	start_frame = int(cmds.playbackOptions(q=1, min=1))
	end_frame = int(cmds.playbackOptions(q=1, max=1))

	if not os.path.isdir(output_path):
		os.makedirs(output_path)
	if not os.path.isdir(output_path):
		logger.error('Was not possible to create export output directory: "{}"'.format(output_path))
		return False

	if not cmds.pluginInfo('AbcExport', query=True, loaded=True):
		cmds.loadPlugin('AbcExport')
	if not cmds.pluginInfo('AbcExport', query=True, loaded=True):
		logger.warning('AbcExport Maya plugin is not available!')
		return False

	for alembic in alembics:
		root = '-root ' + alembic
		output_file = scene_string + shot_string + '_' + '{}.abc'.format(alembic.split(':')[0])
		alembic_export_command = '-frameRange ' + str(start_frame) + ' ' + str(end_frame) +' -uvWrite -worldSpace -attr material -dataFormat ogawa -writeFaceSets -stripNamespaces ' + root + ' -file ' + output_path + output_file
		logger.info('Alembic Export command: {}'.format(alembic_export_command))
		mel.eval("AbcExport -j \"" + alembic_export_command + "\"")
		logger.info('\nExported Alembic file: "{}"'.format(output_file))
		export_assets_json(
			source_file=maya_file_path, file_path=output_path, output_file=output_file.replace('.abc', ''), category='',
			file_type='abc', group_name=alembic, is_shot=is_shot, version_string=version_string, shot_string=shot_string,
			scene_string=scene_string, tag_name=tag.TagTypes.Alembic, nodes=[alembic], start_frame=start_frame,
			end_frame=end_frame
		)

	return True


# ======================================================================================================================
# SKELETAL MESHES
# ======================================================================================================================

@utils.timer
@utils.viewport_off
@utils.keep_selection_decorator
def export_skeletons(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None, check_assets=True):

	logger.info('Writing out ueGear Skeleton JSON file...')

	skeletons = utils.force_list(nodes or exportable_assets(
		tag_name, asset_type=tag.TagTypes.Skeleton).get(tag.TagTypes.Skeleton, list()))
	if not skeletons:
		logger.warning('No skeletons to export found!')
		return False

	if check_assets:
		result = check_scene(tag_name=tag_name, nodes=skeletons)
		if not result:
			logger.warning('Scene check was not valid!')
			return False

	maya_file_path = utils.clean_path(cmds.file(query=True, sceneName=True))
	maya_file_name = os.path.basename(maya_file_path)
	output_path = utils.clean_path(os.path.join(os.path.dirname(maya_file_path), 'output'))
	version_string = maya_file_name.split('_')[-1].split('.')[0]
	scene_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-3]
	shot_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-2]
	is_shot = False if 'assets' in maya_file_path else True
	start_frame = int(cmds.playbackOptions(q=1, min=1))
	end_frame = int(cmds.playbackOptions(q=1, max=1))

	if not os.path.isdir(output_path):
		os.makedirs(output_path)
	if not os.path.isdir(output_path):
		logger.error('Was not possible to create export output directory: "{}"'.format(output_path))
		return False

	for skeleton in skeletons:
		previous_parent = ''
		if not cmds.referenceQuery(skeleton, isNodeReferenced=True):
			parent_nodes = cmds.listRelatives(skeleton, p=True)
			if parent_nodes:
				previous_parent = parent_nodes[0]
				cmds.parent(skeleton, world=True)

		mesh_nodes = list()
		skin_cluster_nodes = utils.get_skin_clusters_for_node(skeleton)
		for skin_cluster in skin_cluster_nodes:
			mesh_nodes = mesh_nodes + utils.get_skin_cluster_meshes(skin_cluster)
		if not mesh_nodes:
			logger.warning('No skinned meshes found for given skeleton joint: {}'.format(skeleton))
			continue

		group_name = cmds.listRelatives(mesh_nodes[0], p=True)[0]
		category = cmds.listRelatives(group_name, p=True)[0]
		if ':' in group_name:
			group_name = group_name.split(':')[-1]
		if ':' in category:
			category = category.split(':')[-1]
		namespace_str = skeleton.split(':')[0] if ':' in skeleton else group_name

		if is_shot:
			output_file = scene_string + shot_string + '_' + namespace_str + '.fbx'
			pyFBX.FBXExportBakeComplexStart(v=start_frame)
			pyFBX.FBXExportBakeComplexEnd(v=end_frame)
		else:
			output_file = group_name + '.fbx'
			pyFBX.FBXExportBakeComplexStart(v=1)
			pyFBX.FBXExportBakeComplexEnd(v=1)

		export_path = utils.clean_path(os.path.join(output_path, output_file))

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

		skeleton_type = check_skeleton_type(skeleton)

		export_assets_json(
			source_file=maya_file_path, file_path=output_path, output_file=output_file.replace('.fbx', ''),
			category=category, file_type='fbx', group_name=group_name, is_shot=is_shot, version_string=version_string,
			shot_string=shot_string, scene_string=scene_string, tag_name=tag.TagTypes.Skeleton, nodes=[skeleton],
			skeleton_type=skeleton_type, start_frame=start_frame, end_frame=end_frame
		)

		if previous_parent and not cmds.referenceQuery(skeleton, isNodeReferenced=True):
			cmds.parent(skeleton, previous_parent)

	return True


# ======================================================================================================================
# CAMERAS
# ======================================================================================================================

@utils.timer
@utils.viewport_off
@utils.keep_selection_decorator
def export_cameras(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None, check_assets=True):

	cameras = utils.force_list(nodes or exportable_assets(
		tag_name, asset_type=tag.TagTypes.Camera).get(tag.TagTypes.Camera, list()))
	if not cameras:
		logger.warning('No cameras to export found!')
		return False

	if check_assets:
		result = check_scene(tag_name=tag_name, nodes=cameras)
		if not result:
			logger.warning('Scene check was not valid!')
			return False

	maya_file_path = utils.clean_path(cmds.file(query=True, sceneName=True))
	maya_file_name = os.path.basename(maya_file_path)
	output_path = utils.clean_path(os.path.join(os.path.dirname(maya_file_path), 'output'))
	version_string = maya_file_name.split('_')[-1].split('.')[0]
	scene_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-3]
	shot_string = '' if 'assets' in maya_file_path else maya_file_path.split('/')[-2]
	is_shot = False if 'assets' in maya_file_path else True
	start_frame = int(cmds.playbackOptions(q=1, min=1))
	end_frame = int(cmds.playbackOptions(q=1, max=1))

	if not os.path.isdir(output_path):
		os.makedirs(output_path)
	if not os.path.isdir(output_path):
		logger.error('Was not possible to create export output directory: "{}"'.format(output_path))
		return False

	for camera in cameras:
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
			'aspectratio': cmds.camera(camera_shape, q=True, aspectRatio=True),
			'cameraScale': cmds.camera(camera_shape, q=True, cameraScale=True),
			'clippingPlanes': cmds.camera(camera_shape, q=True, clippingPlanes=True),
			'farClipPlane': cmds.camera(camera_shape, q=True, farClipPlane=True),
			'nearClipPlane': cmds.camera(camera_shape, q=True, nearClipPlane=True),
			'focalLength': cmds.camera(camera_shape, q=True, focalLength=True),
			'fStop': cmds.camera(camera_shape, q=True, fStop=True),
			'horizontalFilmAperture': cmds.camera(camera_shape, q=True, horizontalFilmAperture=True) * 25.4,
			'verticalFilmAperture': cmds.camera(camera_shape, q=True, verticalFilmAperture=True) * 25.4,
			'lensSqueezeRatio': cmds.camera(camera_shape, q=True, lensSqueezeRatio=True)
		}
		export_assets_json(
			source_file=maya_file_path, file_path=output_path, output_file=output_file.replace('.fbx', ''),
			file_type='fbx', version=version_string, tag_name=tag.TagTypes.Camera, nodes=[camera], start_frame=start_frame,
			end_frame=end_frame, is_shot=is_shot, scene_string=scene_string, shot_string=shot_string,
			custom_params=custom_params)

		logger.info('\nCamera exported {}'.format(export_path))

	return True


# ======================================================================================================================
# LAYOUT
# ======================================================================================================================

@utils.timer
@utils.viewport_off
def export_layout_json(nodes=None, output_path=None):
	"""
	Exports an ueGear layout JSON file that can be later imported into Unreal Engine.

	:param str or list(str) or None nodes: list of nodes to include into the ueGear layout JSON file.
	:param str or None output_path: optional directory where ueGear layout JSON file will be exported into. If not
		given, output path will be retrieved based on the current opened Maya scene file.
	:return: True if the export layout JSON file operation was successful; False otherwise.
	:rtype :bool
	"""

	maya_file_path = utils.clean_path(cmds.file(query=True, sceneName=True))
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

	nodes = nodes or cmds.ls(sl=True, long=True)
	found_meshes = list()
	for node in nodes:
		if not utils.node_is_mesh(node):
			continue
		found_meshes.append(node)
	if not found_meshes:
		logger.warning('No layout meshes to export!')
		return False

	for mesh in found_meshes:
		short_mesh = mesh.split('|')[-1]
		translation_value, rotation_value, scale_value = utils.get_transforms_for_mesh_node(mesh)
		source_name_output = short_mesh.rsplit('_', 1)[0]
		if ':' in source_name_output:
			source_name_output = source_name_output.split(':')[-1]
		asset_name = tag.tag_values(tag_name=tag.TAG_ASSET_NAME_ATTR_NAME, nodes=[mesh])
		asset_path = tag.tag_values(tag_name=tag.TAG_ASSET_PATH_ATTR_NAME, nodes=[mesh])
		actor_name = tag.tag_values(tag_name=tag.TAG_ACTOR_NAME_ATTR_NAME, nodes=[mesh])
		layout_map.setdefault(short_mesh, {
			'translation': translation_value,
			'rotation': rotation_value,
			'scale': scale_value,
			'sourceName': source_name_output,
			'assetName': asset_name[0] or '',
			'assetPath': asset_path[0] or '',
			'actorName': actor_name[0] or ''
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

def check_scene(tag_name=tag.TAG_ASSET_TYPE_ATTR_NAME, nodes=None):
	"""
	Checks scene for correct setup for Unreal export.

	:param str tag_name: name of the tag to check for. By default, TAG_ASSET_TYPE_ATTR_NAME will be used.
	:param str or list(str) or None nodes: list of nodes to check, if not given all nodes in the scene will be checked.
	:return: True if the scene check was successful; False otherwise.
	:rtype: bool
	"""

	objects_map = dict()

	maya_file_path = cmds.file(query=True, sceneName=True)

	if '/assets/' not in maya_file_path and '/scenes/' not in maya_file_path:
		logger.error('Please place this Maya file under either and assets or scenes folder')
		return False

	tagged_nodes_attributes_list = tag.find_tagged_node_attributes(tag_name=tag_name, nodes=nodes)
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

	for static_mesh in objects_map.get(tag.TagTypes.StaticMesh, list()):
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

	for joint in objects_map.get(tag.TagTypes.Skeleton, list()):
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

	for camera in objects_map.get(tag.TagTypes.Camera, list()):
		first_shape = utils.get_first_in_list(cmds.listRelatives(camera, shapes=True)) or None
		if not first_shape or not cmds.objectType(first_shape) == 'camera':
			logger.error('Camera tags should be on the actual camera object. Please fix: "{}"'.format(camera))
			continue

	logger.info('Scene check complete!')

	return True


@utils.keep_selection_decorator
def check_skeleton_type(root_joint):

	namespace = root_joint.split(':')[0] + ':' if ':' in root_joint else ''

	# TODO: retrieve hierarchy without modifying the selection
	cmds.select(root_joint)
	cmds.select(hi=True)
	joint_list = cmds.ls(sl=True, type='joint')
	skeleton_definition_path = utils.join_path(os.path.dirname(os.path.realpath(__file__)).replace('\\', '/'), '/skeleton_definitions')
	skeleton_math = False
	skeleton_definition_file = ''

	if os.path.exists(skeleton_definition_path):
		skeleton_definition_files = list()
		for file in os.listdir(skeleton_definition_path):
			if file.endswith('.json'):
				skeleton_definition_files.append(file)
		exit_loop = False
		for skeleton_definition_file in skeleton_definition_files:
			if exit_loop:
				break
			json_data = utils.read_json_file(utils.join_path(skeleton_definition_path, skeleton_definition_file))
			skeleton_data = json_data.get('data', list())
			if not skeleton_data:
				continue
			skeleton_list = skeleton_data[0].get('joint_list', list())
			for joint in skeleton_list:
				if namespace + joint in joint_list:
					skeleton_math = True
				else:
					skeleton_math = False
					exit_loop = True
					break

	return skeleton_definition_file.replace('.json', '') if skeleton_math else 'custom'


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
