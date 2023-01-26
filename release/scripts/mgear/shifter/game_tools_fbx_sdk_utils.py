import os

import maya.cmds as cmds

from mgear.core import pyFBX as pfbx


class FbxSdkGameToolsWrapper(object):

	def __init__(self, filename):
		self._filename = filename
		self._scene = None
		self._sdk_manager = None
		self._root_node = None
		self._scene_nodes = list()

		if pfbx.FBX_SDK:
			self._sdk_manager, self._scene = pfbx.FbxCommon.InitializeSdkObjects()
			pfbx.FbxCommon.LoadScene(self._sdk_manager, self._scene, filename)
			self._root_node = self._scene.GetRootNode()
			self._scene_nodes = self.get_scene_nodes()

	def close(self):
		if not pfbx.FBX_SDK or not self._sdk_manager:
			return

		self._sdk_manager.Destroy()

	def get_scene_nodes(self):

		if not pfbx.FBX_SDK:
			return list()

		def _get_scene_nodes(_node):
			self._scene_nodes.append(_node)
			for i in range(_node.GetChildCount()):
				_get_scene_nodes(_node.GetChild(i))

		self._scene_nodes = list()
		for i in range(self._root_node.GetChildCount()):
			_get_scene_nodes(self._root_node.GetChild(i))

		return self._scene_nodes

	def get_type_nodes(self, type):

		if not pfbx.FBX_SDK or not self._scene:
			return list()

		nodes = list()
		for i in range(self._scene.RootProperty.GetSrcObjectCount()):
			node = self._scene.RootProperty.GetSrcObject(i)
			if not node:
				continue
			if node.GetTypeName() == type:
				nodes.append(node)

		return nodes

	def get_meshes(self):
		return self.get_type_nodes('Mesh')

	def get_joints(self):
		return self.get_type_nodes('LimbNode')

	def cast_property(fbx_property):

		if not pfbx.FBX_SDK:
			return None

		unsupported_types = [
			fbx.eFbxUndefined,
			fbx.eFbxChar,
			fbx.eFbxUChar,
			fbx.eFbxShort,
			fbx.eFbxUShort,
			fbx.eFbxUInt,
			fbx.eFbxLongLong,
			fbx.eFbxHalfFloat,
			fbx.eFbxDouble4x4,
			fbx.eFbxEnum,
			fbx.eFbxTime,
			fbx.eFbxReference,
			fbx.eFbxBlob,
			fbx.eFbxDistance,
			fbx.eFbxDateTime,
			fbx.eFbxTypeCount,
		]

		casted_property = None

		# property is not supported or mapped yet
		property_type = fbx_property.GetPropertyDataType().GetType()
		if property_type in unsupported_types:
			return None

		if property_type == fbx.eFbxBool:
			casted_property = fbx.FbxPropertyBool1(fbx_property)
		elif property_type == fbx.eFbxDouble:
			casted_property = fbx.FbxPropertyDouble1(fbx_property)
		elif property_type == fbx.eFbxDouble2:
			casted_property = fbx.FbxPropertyDouble2(fbx_property)
		elif property_type == fbx.eFbxDouble3:
			casted_property = fbx.FbxPropertyDouble3(fbx_property)
		elif property_type == fbx.eFbxDouble4:
			casted_property = fbx.FbxPropertyDouble4(fbx_property)
		elif property_type == fbx.eFbxInt:
			casted_property = fbx.FbxPropertyInteger1(fbx_property)
		elif property_type == fbx.eFbxFloat:
			casted_property = fbx.FbxPropertyFloat1(fbx_property)
		elif property_type == fbx.eFbxString:
			casted_property = fbx.FbxPropertyString(fbx_property)
		else:
			raise ValueError(
				"Unknown property type: {0} {1}".format(
					property.GetPropertyDataType().GetName(), property_type
				)
			)

		return casted_property

	def get_property_value(self, fbx_property):
		casted_property = cast_property(fbx_property) if fbx_property and fbx_property.IsValid() else None
		return casted_property.Get() if casted_property else None

	def remove_non_exportable_nodes(self, no_export_tag='no_export'):

		nodes_to_delete = list()
		scene_nodes = self.get_scene_nodes()
		for node in scene_nodes:
			property_value = self.get_property_value(node.FindProperty(no_export_tag))
			if property_value is True:
				nodes_to_delete.append(node)
		for node_to_delete in nodes_to_delete:
			scene.DisconnectSrcObject(node_to_delete)
			scene.RemoveNode(node_to_delete)

		# force the update of the internal cache of scene nodes
		self.get_scene_nodes()

	def export_skeletal_mesh(self, mesh_name, hierarchy_joints):

		if not pfbx.FBX_SDK:
			cmds.warning('Export Skeletal Mesh functionality is only available if Python FBX SDK is available!')
			return None

		mesh_to_export = None
		meshes_to_delete = list()
		meshes_nodes = self.get_meshes()
		for mesh_node in meshes_nodes:
			if mesh_node.GetName() == mesh_name:
				mesh_to_export = mesh_node
			else:
				if mesh_node.GetName():
					meshes_to_delete.append(mesh_node)
		if not mesh_to_export:
			cmds.warning('No mesh with name "{}" to export found!'.format(mesh_name))
			return None

		# ensure hierarchy has no
		hierarchy = set(list(hierarchy_joints))
		skeleton_joints = list()
		joints_to_remove = list()
		scene_joints = self.get_joints()
		for scene_joint in scene_joints:
			if not scene_joint or scene_joint.GetName() not in hierarchy:
				if not scene_joint.GetName():
					continue
				joints_to_remove.append(scene_joint)
			else:
				skeleton_joints.append(scene_joint)
		if len(hierarchy) != len(skeleton_joints):
			cmds.warning('Joints does not match ({} / {})'.format(len(hierarchy), len(skeleton_joints)))
			return None

		for mesh_to_delete in meshes_to_delete:
			self._scene.DisconnectSrcObject(mesh_to_delete)
			self._scene.RemoveNode(mesh_to_delete)

		for joint_to_delete in joints_to_remove:
			self._scene.DisconnectSrcObject(joint_to_delete)
			self._scene.RemoveNode(joint_to_delete)

		save_path = os.path.join(os.path.dirname(self._filename), '{}.fbx'.format(mesh_name))
		pfbx.FbxCommon.SaveScene(self._sdk_manager, self._scene, save_path, 0)
