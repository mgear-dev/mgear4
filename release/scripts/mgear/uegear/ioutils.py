#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains import and export utility functions.
"""

from __future__ import print_function, division, absolute_import

import os
import shutil

import maya.cmds as cmds

from mgear.core import pyFBX
from mgear.uegear import utils, log

logger = log.uegear_logger


@utils.keep_selection_decorator
def export_static_mesh(export_path, static_mesh, file_name=None):

	cmds.select(static_mesh)
	output_file = file_name
	if not file_name:
		output_file = '{}.fbx'.format(static_mesh.replace(':', '_').split('|')[-1])
	if not output_file.endswith('.fbx'):
		output_file = output_file + '.fbx'
	final_export_path = utils.join_path(export_path, output_file)

	# if FBX already exists, to make the export process safer, we export the FBX using a temporal name, so we only
	# overwrite the original FBX if the FBX export was completed successfully.
	export_path = final_export_path
	if os.path.isfile(final_export_path):
		_export_file_name = os.path.basename(final_export_path)
		_file_name, _file_extension = os.path.splitext(_export_file_name)
		export_path = utils.join_path(os.path.dirname(final_export_path), '{}_uegear_temp{}'.format(_file_name, _file_extension))

	pyFBX.FBXExportBakeComplexStart(v=1)
	pyFBX.FBXExportBakeComplexEnd(v=1)
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

	valid_export = True
	try:
		pyFBX.FBXExport(f=export_path, s=True)
	except RuntimeError as exc:
		logger.error('Something went wrong while exporting FBX in following path: "{}" | {}'.format(export_path, exc))
		valid_export = False

	if not valid_export or not os.path.isfile(export_path):
		logger.warning('Was not possible to export FBX!')
		return ''

	if export_path != final_export_path:
		shutil.move(export_path, final_export_path)
		if not os.path.isfile(final_export_path):
			logger.error('Something went wrong while renaming exported FBX file from "{}" to "{}"'.format(
				export_path, final_export_path))
			return ''

	logger.info('Exported {}'.format(final_export_path))
	return final_export_path
