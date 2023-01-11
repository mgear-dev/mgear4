#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains all commands available for ueGear
"""

from __future__ import print_function, division, absolute_import

import os
import tempfile

import maya.cmds as cmds

from mgear.uegear import log, utils, tag, bridge, io, ioutils

logger = log.uegear_logger


def import_selected_assets_from_unreal():
	"""
	Imports current selected Content Browser Unreal assets into the Maya scene.

	:return: True if import selected assets from Unreal operation was successful; False otherwise.
	:rtype: bool
	"""

	uegear_bridge = bridge.UeGearBridge()

	# export FBX file into a temporal folder
	temp_folder = tempfile.gettempdir()
	asset_export_datas = uegear_bridge.execute(
		'export_selected_assets', parameters={'directory': temp_folder}).get('ReturnValue', list())
	if not asset_export_datas:
		logger.warning('Was not possible to export selected assets from Unreal')
		return False

	for asset_export_data in asset_export_datas:

		# import asset from FBX file
		fbx_file = asset_export_data.get('fbx_file', None)
		if not fbx_file or not os.path.isfile(fbx_file):
			logger.warning('No FBX file found for asset data: {}'.format(asset_export_data))
			continue
		logger.info('Importing Asset from FBX file: "{}"'.format(fbx_file))
		imported_nodes = utils.import_fbx(fbx_file)

		# tag imported transform nodes from FBX
		transform_nodes = cmds.ls(imported_nodes, type='transform')
		for transform_node in transform_nodes:
			asset_type = asset_export_data.get('asset_type', '')
			asset_name = asset_export_data.get('name', '')
			asset_path = asset_export_data.get('path', '')
			if asset_type:
				tag.apply_tag(transform_node, tag.TAG_ASSET_TYPE_ATTR_NAME, asset_type)
			else:
				tag.auto_tag(transform_node)
			if asset_name:
				tag.apply_tag(transform_node, tag.TAG_ASSET_NAME_ATTR_NAME, asset_name)
			if asset_path:
				tag.apply_tag(transform_node, tag.TAG_ASSET_PATH_ATTR_NAME, asset_path)

	return True


def export_selected_assets_to_unreal(export_directory=None, export_in_original_path=True):
	"""
	Exports current selected assets in Maya scene into Unreal Engine Content Browser.

	:return: True if export selected assets to Unreal operation was successful; False otherwise.
	:rtype: bool
	"""

	# TODO: For now, only static meshes are exported into Unreal
	# TODO: Add support for Skeletal Meshes (Skinned Meshes)

	uegear_bridge = bridge.UeGearBridge()

	temp_folder = tempfile.gettempdir()

	# retrieve a dictionary with the assets that can be exported.
	nodes_to_export = cmds.ls(sl=True, long=True)
	objects_map = io.exportable_assets(nodes=nodes_to_export)
	if not objects_map:
		logger.warning('No exportable assets found in nodes to export: "{}"'.format(nodes_to_export))
		return False

	# retrieve the static meshes nodes to export as assets into Unreal Engine
	static_meshes = objects_map.get(tag.TagTypes.StaticMesh, list())
	if not static_meshes:
		logger.warning('No static meshes to update')
		return False

	# Retrieve current Unreal Engine project directory
	content_path = uegear_bridge.execute('project_content_directory').get('ReturnValue', '')
	if not content_path or not os.path.isdir(content_path):
		logger.warning('Was not possible to retrieve current Unreal project content path')
		return False

	for static_mesh in static_meshes:
		asset_path = tag.tag_values(tag_name=tag.TAG_ASSET_PATH_ATTR_NAME, nodes=[static_mesh])
		asset_path = asset_path[0] if asset_path else ''
		asset_exists = uegear_bridge.execute(
			'does_asset_exist', parameters={'asset_path': asset_path}).get('ReturnValue', False)

		if not asset_exists:
			# TODO: If the asset does not exists, we should import the asset as a new one into Unreal
			logger.warning('Asset "{}" does not exists within current Unreal Project!'.format(asset_path))
			continue
		else:
			# Verify .uasset file for the asset exists within current Unreal Engine project directory
			asset_file_name = os.path.basename(asset_path).split('.')[0]
			uasset_file_name = asset_file_name + '.uasset'
			content_uasset_path = utils.join_path(
				content_path, os.path.dirname(asset_path).replace('/Game/', '/'), uasset_file_name)
			if not os.path.isfile(content_uasset_path):
				logger.warning('.uasset file was not found: "{}"'.format(content_uasset_path))
				continue

			export_file_name = '{}.fbx'.format(asset_file_name)

			if not export_directory and export_in_original_path:
				# We try to retrieve the export path from the metadata of the Asset within Unreal Engine project
				asset_export_path = uegear_bridge.execute(
					'asset_export_path', parameters={'asset_path': asset_path}).get('ReturnValue', '')
				export_file_name = '{}.fbx'.format(os.path.basename(asset_export_path).split('.')[0])
			else:
				if not export_directory:
					asset_export_path = utils.join_path(temp_folder, export_file_name)
				else:
					asset_export_path = utils.join_path(export_directory, export_file_name)

			# if it is not possible to find/create the original FBX export path we export the asset into a temp folder
			if export_directory or export_in_original_path:
				asset_export_directory = os.path.dirname(asset_export_path)
				if not os.path.isdir(asset_export_directory):
					logger.info('Export directory does not exist, trying to create it: {}'.format(asset_export_directory))
					result = utils.create_folder(asset_export_directory)
					if not result:
						logger.warning(
							'Was not possible to create original export path: "{}" | temp folder will be used instead...'.format(
								asset_export_directory))
						asset_export_path = utils.join_path(temp_folder, '{}.fbx'.format(asset_file_name))
			asset_export_directory = os.path.dirname(asset_export_path)

			# export FBX file into disk
			fbx_file_path = ioutils.export_static_mesh(asset_export_directory, static_mesh, file_name=export_file_name)
			if not os.path.isfile(fbx_file_path):
				logger.warning('Something went wrong while exporting asset FBX file: "{}"'.format(fbx_file_path))
				continue

			# TODO: Import options should be retrieved from the .uasset file located in Unreal
			import_options = {'destination_name': asset_file_name, 'replace_existing': True, 'save': False}
			result = uegear_bridge.execute(
				'import_static_mesh', parameters={
					'fbx_file': fbx_file_path,
					'import_path': os.path.dirname(content_uasset_path),
					'import_options': str(import_options)
				}).get('ReturnValue', False)
			if not result:
				logger.warning('Was not possible to export asset: {}. Please check Unreal Engine Output Log'.format(static_mesh))
				continue

	return True
