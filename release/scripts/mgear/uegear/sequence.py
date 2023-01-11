#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains functions related with ueGear sequences.
"""

from __future__ import print_function, division, absolute_import

import os
import math

import maya.cmds as cmds

from mgear.uegear import log, utils, tag

PREVIS_STAGE = 'previs'
LAYOUT_STAGE = 'layout'
ANIMATION_STAGE = 'animation'
SEQUENCE_STAGES = [PREVIS_STAGE, LAYOUT_STAGE, ANIMATION_STAGE]
SEQUENCE_DIRECTORIES = ['mocap', 'assets', 'audio', 'video', 'reference']

logger = log.uegear_logger


def get_sequence_node(get_only_first=True, as_sequence_node=True):
	"""
	Returns all sequence nodes within current scene.

	:param bool get_only_first: whether to return only the first sequence node found.
	:param bool as_sequence_node: whether to return the Maya node names or UeGearSequenceNode instances.
	:return: list of sequence node names.
	:rtype: list(str) or str or list(UeGearSequenceNode) or UeGearSequenceNode
	"""

	found_sequence_nodes = list()
	transform_nodes = cmds.ls(type='transform')
	for transform_node in transform_nodes:
		if not cmds.attributeQuery('isSequence', node=transform_node, exists=True):
			continue
		is_sequence = cmds.getAttr('{}.isSequence'.format(transform_node))
		if is_sequence:
			if get_only_first:
				return transform_node
			found_sequence_nodes.append(transform_node)

	return found_sequence_nodes


def create_sequence_node_instance_from_maya_node(node):
	"""
	Crates a new UeGearSequenceNode from the given Maya node.

	:param str node: Maya node name.
	:return: newly created sequence node instance.
	:rtype: UeGearSequenceNode or None
	"""

	if not node or cmds.objExists(node):
		return None

	is_sequence = cmds.getAttr('{}.isSequence'.format(node))
	if not is_sequence:
		logger.warning('Given Maya node: {} is not a sequence node!'.format(node))
		return None

	sequence_directory = cmds.getAttr('{}.sequenceDirectory'.format(node))
	sequence_name = cmds.getAttr('{}.sequenceName'.format(node))
	version = cmds.getAttr('{}.versionNumber'.format(node))
	sequence_stage = cmds.getAttr('{}.stage'.format(node))
	is_shot = cmds.getAttr('{}.isShotFile'.format(node))
	shot_number = cmds.getAttr('{}.shotNumber'.format(node))
	scene_name = cmds.getAttr('{}.sceneName'.format(node))
	notes = cmds.getAttr('{}.notes'.format(node))
	sequence_path = utils.clean_path(os.path.join(sequence_directory, sequence_name))
	sequence_node = UeGearSequenceNode(
		name=sequence_name, path=sequence_path, is_shot=is_shot, version=version, stage=sequence_stage, notes=notes,
		scene_name=scene_name, shot_number=shot_number)

	return sequence_node


def get_sequence_node_instance(
		sequence_name, sequence_directory, shot_number=0, sequence_stage=LAYOUT_STAGE, is_scene_file=False, scene_name='',
		notes=''):
	"""
	Creates a new valid sequence node instance.

	:param str sequence_name: three letter sequence code.
	:param int shot_number: shot number.
	:param str sequence_directory: directory where sequence file should be located.
	:param bool is_scene_file: whether is shot file or scene file.
	:param str scene_name: name of the scene. Only applies if is_scene_file argument is True.
	:param str sequence_stage: type of sequence stage ('previs', 'layout' or 'animation').
	:param str notes: extra sequence notes.
	:return: new sequence node instance.
	:rtype: UeGearSequenceNode or None
	"""

	if len(sequence_name) < 3 or not sequence_stage or sequence_stage not in SEQUENCE_STAGES:
		logger.warning('Sequence name length must be lower than 3 and sequence must defined a stage')
		return None

	if is_scene_file and not scene_name:
		logger.warning('A Sequence scene file must defined a scene name')
		return None

	if not is_scene_file and sequence_stage == ANIMATION_STAGE and shot_number == 0:
		logger.warning('Animation sequence shot file must define a shot number greater than 0')
		return None

	is_shot = False if is_scene_file else True
	scene_name = '_'.join(scene_name.split())
	sequence_path = utils.clean_path(os.path.join(sequence_directory, sequence_name))
	notes = notes or 'Start File'
	sequence_node = UeGearSequenceNode(
		name=sequence_name, path=sequence_path, is_shot=is_shot, version=1, stage=sequence_stage, notes=notes,
		scene_name=scene_name, shot_number=shot_number)

	return sequence_node


def create_sequence(
		sequence_name, sequence_directory, shot_number=0, sequence_stage=LAYOUT_STAGE, is_scene_file=False, scene_name='',
		notes='', delete_existing_sequences=True):
	"""
	Creates a new sequence.

	:param str sequence_name: three letter sequence code.
	:param int shot_number: shot number.
	:param str sequence_directory: directory where sequence file should be located.
	:param bool is_scene_file: whether is shot file or scene file.
	:param str scene_name: name of the scene. Only applies if is_scene_file argument is True.
	:param str sequence_stage: type of sequence stage ('previs', 'layout' or 'animation').
	:param str notes: extra sequence notes.
	:param bool delete_existing_sequences: whether existing sequence node should be deleted.
	:return: sequence node instance.
	:rtype: UeGearSequenceNode or None
	"""

	sequence_node = get_sequence_node_instance(
		sequence_name=sequence_name, shot_number=shot_number, sequence_directory=sequence_directory,
		sequence_stage=sequence_stage, is_scene_file=is_scene_file, scene_name=scene_name, notes=notes)
	if not sequence_node:
		logger.error('Was not possible to create a new sequence')
		return None

	if delete_existing_sequences:
		delete_sequence_nodes()

	sequence_node.create()

	return sequence_node


def add_sequence_attributes(
		node, sequence_directory='', sequence_name='', shot_number=0, scene_name='', version_number=0,
		is_shot_file=False, stage='', notes=''):
	"""
	Adds sequence attributes to given Maya node.

	:param str node: Maya node name to add attributes into.
	:param str sequence_directory: directory of the sequence.
	:param str sequence_name: name of the sequence.
	:param int shot_number: shot number.
	:param str scene_name: name of the sequence scene.
	:param int version_number: sequence version.
	:param bool is_shot_file: whether file is a shot or scene file.
	:param str stage: sequence stage.
	:param str notes: optional extra sequence notes.
	:return: True if the sequence attributes were added successfully; False otherwise.
	:rtype: bool
	"""

	if not node or not cmds.objExists(node):
		return False

	cmds.addAttr(node, ln='isSequence', at='bool', k=True)
	cmds.addAttr(node, ln='sequenceDirectory', dt='string', k=True)
	cmds.addAttr(node, ln='sequenceName', dt='string', k=True)
	stages = ':'.join(SEQUENCE_STAGES)
	cmds.addAttr(node, ln='stage', at='enum', en=stages, k=True)
	cmds.addAttr(node, ln='isShotFile', at='bool', k=False)
	cmds.addAttr(node, ln='shotNumber', at='short', k=True)
	cmds.addAttr(node, ln='sceneName', dt='string', k=True)
	cmds.addAttr(node, ln='versionNumber', at='short', k=True)
	cmds.addAttr(node, ln='notes', dt='string', k=True)
	for axis in 'xyz':
		for channel in 'trs':
			cmds.setAttr('{}.{}{}'.format(node, channel, axis), k=False, cb=False, l=True)
	cmds.setAttr('{}.visibility'.format(node), k=False, cb=False, l=True)

	cmds.setAttr('{}.isSequence'.format(node), True)
	cmds.setAttr('{}.sequenceDirectory'.format(node), sequence_directory, type='string')
	cmds.setAttr('{}.sequenceName'.format(node), sequence_name, type='string')
	cmds.setAttr('{}.shotNumber'.format(node), shot_number)
	cmds.setAttr('{}.sceneName'.format(node), scene_name, type='string')
	cmds.setAttr('{}.versionNumber'.format(node), version_number)
	cmds.setAttr('{}.isShotFile'.format(node), is_shot_file)
	cmds.setAttr('{}.stage'.format(node), SEQUENCE_STAGES.index(stage))
	cmds.setAttr('{}.notes'.format(node), notes, type='string')

	lock_sequence_node_attributes(node)

	return True


def lock_sequence_node_attributes(node):
	"""
	Locks the sequence related attributes of the given Maya node.

	:param str node: Maya node whose sequence related attributes we want to lock.
	"""

	cmds.setAttr('{}.isSequence'.format(node), l=True)
	cmds.setAttr('{}.sequenceDirectory'.format(node), l=True)
	cmds.setAttr('{}.sequenceName'.format(node), l=True)
	cmds.setAttr('{}.stage'.format(node), l=True)
	cmds.setAttr('{}.shotNumber'.format(node), l=True)
	cmds.setAttr('{}.sceneName'.format(node), l=True)
	cmds.setAttr('{}.isShotFile'.format(node), l=True)
	cmds.setAttr('{}.versionNumber'.format(node), l=True)
	cmds.setAttr('{}.notes'.format(node), l=True)


def unlock_sequence_node_attributes(node):
	"""
	Locks the sequence related attributes of the given Maya node.

	:param str node: Maya node whose sequence related attributes we want to lock.
	"""

	cmds.setAttr('{}.isSequence'.format(node), l=False)
	cmds.setAttr('{}.sequenceDirectory'.format(node), l=False)
	cmds.setAttr('{}.sequenceName'.format(node), l=False)
	cmds.setAttr('{}.stage'.format(node), l=False)
	cmds.setAttr('{}.shotNumber'.format(node), l=False)
	cmds.setAttr('{}.sceneName'.format(node), l=False)
	cmds.setAttr('{}.isShotFile'.format(node), l=False)
	cmds.setAttr('{}.versionNumber'.format(node), l=False)
	cmds.setAttr('{}.notes'.format(node), l=False)


def delete_sequence_nodes():
	"""
	Deletes all sequence nodes found within current scene.

	:return: True if, at least, one sequence node was deleted; False otherwise.
	:rtype: bool
	"""

	sequence_nodes = tag.find_tagged_nodes(tag_value=tag.TagTypes.Sequence)
	for sequence_node in sequence_nodes:
		cmds.lockNode(sequence_node, l=False)
		cmds.delete(sequence_node)

	return True if sequence_nodes else False


def create_sequence_initial_folder_structure(sequence_directory):
	"""
	Creates initial sequence folder structure within given directory.

	:param str sequence_directory: absolute directory path where initial folder structure will be created.
	"""

	for directory_name in SEQUENCE_DIRECTORIES:
		utils.ensure_folder_exists(directory_name)


def get_sequence_save_directory(sequence_directory, is_shot, shot_number, stage, scene_name):
	"""
	Returns directory where sequence file should be stored.

	:param str sequence_directory: root directory for sequences.
	:param bool is_shot: whether sequence file is a shot or scene file.
	:param int shot_number: shot number.
	:param str stage: sequence stage.
	:param str scene_name: name of the scene.
	:return: sequence save absolute directory.
	:rtype: str
	"""

	if is_shot:
		if shot_number != 0:
			shots_directory = os.path.join(sequence_directory, 'shots')
			utils.ensure_folder_exists(shots_directory)
			shot_directory = os.path.join(shots_directory, '{0:0=3d}'.format(shot_number))
			utils.ensure_folder_exists(shot_directory)
			stage_directory = os.path.join(shot_directory, stage)
			utils.ensure_folder_exists(stage_directory)
		else:
			stage_directory = os.path.join(sequence_directory, stage)
	else:
		scenes_directory = os.path.join(sequence_directory, 'scenes')
		utils.ensure_folder_exists(scenes_directory)
		scene_directory = os.path.join(scenes_directory, scene_name)
		utils.ensure_folder_exists(scene_directory)
		stage_directory = os.path.join(scenes_directory, stage)

	utils.ensure_folder_exists(stage_directory)

	return stage_directory


def get_sequence_version_number(directory):
	"""
	Returns the new sequence version based on the sequences files located within given directory.

	:param str directory: directory where sequence files are located.
	:return: new sequence version.
	:rtype: str
	"""

	sequence_files = os.listdir(directory)
	file_versions = list()

	for sequence_file in sequence_files:
		file_no_ext = os.path.splitext(sequence_file)[0]
		version_number = file_no_ext[-3:]
		if version_number.isnumeric():
			file_versions.append(int(version_number))

	latest_version_number = max(file_versions) if file_versions else 0

	return '{0:0=3d}'.format(latest_version_number + 1)


def update_sequence_node_version(node, version):
	"""
	Updates the sequence version number of the given Maya node.

	:param str node: Maya node whose sequence version number we want to update.
	:param int version: sequence version.
	:return: True if the sequence node version was updated; False otherwise.
	:rtype: bool
	"""

	if not node or not cmds.objExists(node) or not cmds.attributeQuery('versionNumber', node=node, exists=True):
		return False

	is_locked = cmds.lockNode(node, query=True)[0]
	cmds.lockNode(node, l=False)
	cmds.setAttr("{}.versionNumber".format(node), l=False)
	cmds.setAttr("{}.versionNumber".format(node), int(version))
	cmds.setAttr("{}.versionNumber".format(node), l=True)
	if is_locked:
		cmds.lockNode(node, l=True)

	return True


def save_sequence_file(directory, sequence_name, stage, version, is_shot, shot_number, scene_name):

	if not is_shot:
		save_as = '{}_{}_{}_v{}'.format(sequence_name, scene_name, stage, '{0:0=3d}'.format(version))
	else:
		if shot_number == 0:
			save_as = '{}_{}_v{}'.format(sequence_name, stage, '{0:0=3d}'.format(version))
		else:
			save_as = '{}_shot_{}_{}_v{}'.format(
				sequence_name, '{0:0=3d}'.format(shot_number), stage, '{0:0=3d}'.format(version))

	new_file_name = os.path.join(directory, save_as)
	cmds.file(rename=new_file_name)
	cmds.file(save=True, type='mayaAscii', f=True)
	logger.info('Sequence file saved: "{}"'.format(new_file_name))


def save_new_sequence_version(
		node, sequence_directory, sequence_name, sequence_version, sequence_stage, is_shot, shot_number, scene_name):

	sequence_path = utils.clean_path(os.path.join(sequence_directory, sequence_name))
	if not os.path.exists(sequence_path):
		create_sequence_initial_folder_structure(sequence_path)

	save_directory = get_sequence_save_directory(
		sequence_directory=sequence_path, is_shot=is_shot, shot_number=shot_number, stage=sequence_stage,
		scene_name=scene_name)
	save_version = get_sequence_version_number(save_directory)

	update_sequence_node_version(node, int(save_version))

	if cmds.attributeQuery('notes', node=node, exists=True):
		notes = cmds.getAttr('{}.notes'.format(node))
		if int(save_version) > 1 and notes == 'Start File':
			cmds.setAttr('{}.notes'.format(node), '', type='string')

	save_sequence_file(
		save_directory, sequence_name=sequence_name, stage=sequence_stage, version=sequence_version, is_shot=is_shot,
		shot_number=shot_number, scene_name=scene_name)

	return True


def handle_shot_namespace_conflict(name):

	if not cmds.namespace(ex=name):
		return

	name_number = 1 + len([x for x in map(str, cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)) if 'tempName' in x])
	temp_name = 't{}_tempName_{}'.format(name_number, name)
	cmds.namespace(ren=[name, temp_name])
	associated_shots = [x for x in cmds.ls(type='shot') if name in cmds.shot(x, q=True, cc=True)]
	if associated_shots:
		cmds.shot(associated_shots[0], e=True, sn=temp_name)


def get_shot_sequence_start_time():
	shots = cmds.ls(type='shot')
	last_shot_end = int(max([cmds.shot(s, set=True, q=True) for s in shots])) if shots else 0

	return last_shot_end


def get_new_shot_number():
	cam_names = [c[-3:] for c in cmds.namespaceInfo(listOnlyNamespaces=True) if 'shot' in c]
	latest_camera_number = 10
	if cam_names:
		latest_camera = max(cam_names)
		latest_camera_number = 10+(math.floor(int(latest_camera[-3:])/10)*10)
	camera_number = "{0:0=3d}".format(latest_camera_number)

	return camera_number


def create_default_shot_camera(name='ref_cam', namespace=None):

	shot_camera_shape = cmds.createNode('camera', name=name)
	shot_camera = cmds.listRelatives(shot_camera_shape, parent=True)[0]

	cmds.setAttr('{}.focalLength'.format(shot_camera_shape), 35.00)
	cmds.setAttr('{}.cameraScale'.format(shot_camera_shape), 1.0)

	print(shot_camera)

	return shot_camera


def get_shot_reference_camera(sequence_name, camera_path=None, shot_number=0):

	if shot_number != 0:
		handle_shot_namespace_conflict('{:0=3d}'.format(shot_number))

	camera_name = get_new_shot_number()
	camera_namespace = '{}_shot_{}'.format(sequence_name, camera_name)
	if camera_path and os.path.isfile(camera_path):
		camera_reference = cmds.file(camera_path, r=True, type='mayaAscii', ns=camera_namespace)
		cam = [c for c in cmds.referenceQuery(camera_reference, nodes=True) if cmds.objectType(c, isType='transform')][0]
	else:
		shot_camera_shape = cmds.createNode('camera', name='ref_cam')
		cam = cmds.listRelatives(shot_camera_shape, parent=True)[0]

	group_shot_camera(cam)

	return cam


def group_shot_camera(cam):
	if not cmds.objExists('cameras_grp'):
		cmds.group(name='cameras_grp', em=True)
	cmds.parent(cam, 'cameras_grp')


def create_shot(shot_name, camera_name, start_frame, end_frame):

	sequence_start_time = get_shot_sequence_start_time()
	_shot_name = 'shot_{}'.format(camera_name)
	new_shot = cmds.shot(_shot_name, st=start_frame, et=end_frame, sst=sequence_start_time, cc=camera_name)
	cmds.shot(new_shot, e=True, shotName=shot_name)
	cmds.sequenceManager(ct=sequence_start_time)
	cmds.shotTrack(ret=True)

	return new_shot


def create_sequence_shot(camera_path, sequence_node=None):

	sequence_node = sequence_node or get_sequence_node()
	if not sequence_node:
		logger.warning('No sequence node found within current scene!')
		return None

	shot = None
	if sequence_node.is_shot:
		shot_number = int(get_new_shot_number())
		start = cmds.playbackOptions(query=True, minTime=True)
		end = cmds.playbackOptions(query=True, maxTime=True)
		camera = get_shot_reference_camera(camera_path, sequence_node.name, shot_number)
		shot = UeGearShot(
			sequence_node=sequence_node, number=shot_number, start=start, end=end, camera=camera,
			stage=sequence_node.stage, version=sequence_node.version)
		shot.create()
	else:
		get_shot_reference_camera(camera_path, sequence_node.name)

	return shot


class UeGearSequenceNode(object):
	"""
	Class that wraps a Maya node that holds sequence related data.

	:param str name: name of the sequence.
	:param str path: path where sequence file should be located.
	:param bool is_shot:
	:param int version:
	:param str stage:
	:param str notes:
	:param str scene_name:
	:param int shot_number:
	"""

	def __init__(self, name, path, is_shot, version, stage, notes=None, scene_name=None, shot_number=None):
		super(UeGearSequenceNode, self).__init__()

		# Internal data, use property getters to access node data.
		self._name = name
		self._path = path
		self._is_shot = is_shot
		self._version = version
		self._stage = stage
		self._notes = notes
		self._scene_name = scene_name
		self._shot_number = shot_number
		self._node = None

	@property
	def node_name(self):
		"""
		Returns the name of the wrapped Maya node.

		:return: node name.
		:rtype: str
		"""

		return '{}_sequence_node'.format(self._name)

	@property
	def path(self):
		"""
		Returns the directory where sequence file should be located.

		:return: absolute path to sequence file directory.
		:rtype: str
		"""

		return self._get_sequence_attribute('sequenceDirectory', default=self._is_shot)

	@property
	def name(self):
		"""
		Returns the name of the sequence.

		:return: sequence name.
		:rtype: str
		"""

		return self._get_sequence_attribute('sequenceName', default=self._name)

	@property
	def is_shot(self):
		"""
		Returns whether the sequence file is a shot file or scene file.

		:return: True if sequence is a shot file; False otherwise.
		:rtype: bool
		"""

		return self._get_sequence_attribute('isShotFile', default=self._is_shot)

	@property
	def version(self):
		"""
		Returns the sequence version number as string.

		:return: sequence version.
		:rtype: str
		"""

		return self._get_sequence_attribute('versionNumber', default=self._version)

	@property
	def stage(self):
		"""
		Returns sequence stage.

		:return: sequence stage.
		:rtype: str
		"""

		return self._get_sequence_attribute('stage', default=self._stage)

	@property
	def notes(self):
		"""
		Returns optional sequence notes.

		:return: sequence notes.
		:rtype: str
		"""

		return self._get_sequence_attribute('notes', default=self._notes)

	@property
	def scene_name(self):
		"""
		Returns sequence scene name.

		:return: scene name.
		:rtype: str
		"""

		return self._get_sequence_attribute('sceneName', default=self._scene_name)

	@property
	def shot_number(self):
		"""
		Returns sequence shot number.

		:return: shot number.
		:rtype: int
		"""

		return self._get_sequence_attribute('shotNumber', default=self._shot_number)

	def create(self):
		"""
		Creates new sequence Maya node and wraps within this instance.

		:return: newly created wrapped Maya node name.
		:rtype: str
		"""

		self._node = cmds.group(name=self.node_name, empty=True)
		add_sequence_attributes(
			self._node, sequence_name=self._name, sequence_directory=self._path, shot_number=self._shot_number,
			scene_name=self._scene_name, version_number=self._version, is_shot_file=self._is_shot, stage=self._stage,
			notes=self._notes)
		cmds.lockNode(self._node)

		return self._node

	def _get_sequence_attribute(self, attribute_name, default=None):
		"""
		Internal function that returns sequence attribute of the wrapped Maya node.

		:param str attribute_name: name of the sequence attribute to retrieve.
		:param any default: default value if attribute was not found.
		:return: sequence attribute value.
		:rtype: any
		"""

		if self._node and cmds.objExists(self._node) and cmds.attributeQuery(attribute_name, node=self._node, ex=True):
			return cmds.getAttr('{}.{}'.format(self._node, attribute_name))

		return default


class UeGearShot(object):
	"""
	Class that holds information of a shot and allows to link a shot with a sequence node.
	"""

	def __init__(self, sequence_node, number, start, end, camera, stage, version, omit=False, chars=None, props=None):
		super(UeGearShot, self).__init__()

		self._sequence_node = sequence_node
		self._number = number
		self._name = '{}_shot_{:0>3}'.format(self._sequence_node.name, self._number)
		self._camera = camera
		self._start = start
		self._end = end
		self._stage = stage
		self._version = version
		self._omit = omit
		self._chars = chars
		self._props = props
		self._node = None

	def create(self):

		self._node = create_shot(
			shot_name=self._name, camera_name=self._camera, start_frame=self._start, end_frame=self._end)
