import os

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
	export_path = utils.join_path(export_path, output_file)
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
	pyFBX.FBXExport(f=export_path, s=True)

	if os.path.isfile(export_path):
		logger.info('\nExported {}'.format(export_path))
		return export_path

	return ''





