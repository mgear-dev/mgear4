#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains ueGear utility related functions.
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import time
import stat
import math
import json
import platform
from functools import wraps

import maya.mel as mel
import maya.cmds as cmds
import maya.api.OpenMaya as OpenMaya

from mgear.uegear import log

logger = log.uegear_logger

SEPARATOR = '/'
BAD_SEPARATOR = '\\'
PATH_SEPARATOR = '//'
SERVER_PREFIX = '\\'
RELATIVE_PATH_PREFIX = './'
BAD_RELATIVE_PATH_PREFIX = '../'
WEB_PREFIX = 'https://'

# we use one separator depending if we are working on Windows (nt) or other operative system
NATIVE_SEPARATOR = (SEPARATOR, BAD_SEPARATOR)[os.name == 'nt']


class Platform(object):
	"""
	Class that store nice names for the different Python supported OS platforms.
	"""

	Windows = 'Windows'
	Linux = 'Linux'
	Mac = 'MacOS'


def is_python2():
	"""
	Returns whether current version is Python 2

	:return: bool
	"""

	return sys.version_info[0] == 2


def is_python3():
	"""
	Returns whether current version is Python 3

	:return: bool
	"""

	return sys.version_info[0] == 3


def get_sys_platform():
	"""
	Returns the OS system platform current Python session runs on.

	:return: OS platform.
	:rtype: str
	"""

	if sys.platform.startswith('java'):
		os_name = platform.java_ver()[3][0]
		# "Windows XP", "Windows 7", etc.
		if os_name.startswith('Windows'):
			system = 'win32'
		# "Mac OS X", etc.
		elif os.name.startswith('Mac'):
			system = 'darwin'
		# "Linux", "SunOS", "FreeBSD", etc.
		else:
			system = 'linux2'
	else:
		system = sys.platform

	return system


def get_platform():
	"""
	Returns the Platform current Python session runs on.

	:return: OS platform.
	:rtype: Platform
	"""

	system_platform = get_sys_platform()

	pl = Platform.Windows
	if 'linux' in system_platform:
		pl = Platform.Linux
	elif system_platform == 'darwin':
		pl = Platform.Mac

	return pl


def is_windows():
	"""
	Check to see if current platform is Windows.

	:return: True if the current platform is Windows; False otherwise.
	:rtype: bool
	"""

	current_platform = get_platform()
	return current_platform == Platform.Windows


def force_list(var):
	"""
	Returns the given variable as list.

	:param object var: object we want to convert to list
	:return: object as list.
	:rtype: list(object)
	"""

	if var is None:
		return list()

	if type(var) is not list:
		if type(var) in [tuple]:
			var = list(var)
		else:
			var = [var]

	return var


def get_index_in_list(list_arg, index, default=None):
	"""
	Returns the item at given index. If item does not exist, returns default value.

	:param list(any) list_arg: list of objects to get from.
	:param int index: index to get object at.
	:param any default: any value to return as default.
	:return: any
	"""

	return list_arg[index] if list_arg and len(list_arg) > abs(index) else default


def get_first_in_list(list_arg, default=None):
	"""
	Returns the first element of the list. If list is empty, returns default value.

	:param list(any) list_arg: An empty or not empty list.
	:param any default: If list is empty, something to return.
	:return: Returns the first element of the list.  If list is empty, returns default value.
	:rtype: any
	"""

	return get_index_in_list(list_arg, 0, default=default)


def get_last_in_list(list_arg, default=None):
	"""
	Returns the last element of the list. If list is empty, returns default value.

	:param list(any) list_arg: An empty or not empty list.
	:param any default: If list is empty, something to return.
	:return: Returns the last element of the list.  If list is empty, returns default value.
	:rtype: any
	"""

	return get_index_in_list(list_arg, -1, default=default)


def safe_delete_file(file_path):
	"""
	Tries to safe delete given file path from disk.
	"""

	if not file_path or not os.path.isfile(file_path):
		return

	try:
		get_permission(file_path)
	except Exception:
		pass
	try:
		os.remove(file_path)
	except Exception:
		pass


def get_permission(directory):
	"""
	Returns the current permission level for the given directory.

	:param str directory: OS directory (file or folder) we want to retrieve permissions of.
	:return: True if the given directory permissions could be retrieved; False otherwise.
	:rtype: bool
	"""

	if directory.endswith('.pyc'):
		return False

	if os.access(directory, os.R_OK | os.W_OK | os.X_OK):
		return True

	permission = False
	try:
		permission = oct(os.stat(directory)[stat.ST_MODE])[-3:]
	except Exception:
		pass
	if not permission:
		return False

	permission = int(permission)

	if is_windows():
		if permission < 666:
			try:
				os.chmod(directory, 0o777)
				return True
			except Exception:
				logger.warning('was not possible to gran permission on: "{}"'.format(directory))
				return False
		else:
			return True

	if permission < 775:
		try:
			os.chmod(directory, 0o777)
		except Exception:
			logger.warning('was not possible to gran permission on: "{}"'.format(directory))
			return False
		return True
	elif permission >= 755:
		return True

	try:
		os.chmod(directory, 0o777)
		return True
	except Exception:
		return False


def touch_path(path, remove=False):
	"""
	Function that makes sure the file or directory is valid to use. This will mark files as writable, and validate the
	directory exists to write to if the file does not exist.

	:param str path: full path to a given file or directory.
	:param bool remove: whether the file should be removed if it exists.
	"""

	directory_path = os.path.dirname(path)
	if os.path.exists(directory_path):
		if os.path.isfile(path):
			os.chmod(path, stat.S_IWRITE)
			if remove:
				os.remove(path)
				time.sleep(.002)
	else:
		os.makedirs(directory_path)


def normalize_path(path):
	"""
	Normalizes a path to make sure that path only contains forward slashes.

	:param str path: path to normalize.
	:return: normalized path
	:rtype: str
	"""

	path = path.replace(BAD_SEPARATOR, SEPARATOR).replace(PATH_SEPARATOR, SEPARATOR)

	if is_python2():
		try:
			path = unicode(path.replace(r'\\', r'\\\\'), 'unicode_escape').encode('utf-8')
		except TypeError:
			path = path.replace(r'\\', r'\\\\').encode('utf-8')

	return path.rstrip('/')


def clean_path(path):
	"""
	Cleans a path. Useful to resolve problems with slashes

	:param str path: path we want to clean
	:return: clean path
	:rtype: str
	"""

	if not path:
		return ''

	# convert '~' Unix character to user's home directory
	path = os.path.expanduser(str(path))

	# Remove spaces from path and fixed bad slashes
	path = normalize_path(path.strip())

	# fix server paths
	is_server_path = path.startswith(SERVER_PREFIX)
	while SERVER_PREFIX in path:
		path = path.replace(SERVER_PREFIX, PATH_SEPARATOR)
	if is_server_path:
		path = PATH_SEPARATOR + path

	# fix web paths
	if not path.find(WEB_PREFIX) > -1:
		path = path.replace(PATH_SEPARATOR, SEPARATOR)

	# make sure drive letter is capitalized
	drive, tail = os.path.splitdrive(path)
	if drive:
		path = path[0].upper() + path[1:]

	return path


def write_to_json_file(data, filename, **kwargs):
	"""
	Writes data to JSON file.

	:param dict, data: data to store into JSON file.
	:param str filename: name of the JSON file we want to store data into.
	:param dict, kwargs:
	:return: file name of the stored file.
	:rtype: str
	"""

	indent = kwargs.pop('indent', 4)

	try:
		with open(filename, 'w') as json_file:
			json.dump(data, json_file, indent=indent, **kwargs)
	except IOError:
		logger.error('Data not saved to file {}'.format(filename))
		return None

	logger.debug('File correctly saved to: {}'.format(filename))

	return filename


def get_unreal_engine_transform_for_maya_node(node_name):
	"""
	Returns Unreal valid transform from given Maya transform node.

	:param str node_name: name of the Maya transform node to convert its transform to an Unreal transform.
	:return: dictionary containing the Unreal transform data.
	:rtype: dict
	"""

	def _xyz_list_build(param):
		xyz_list = param[:]
		xyz_list[0] = param[0]
		xyz_list[1] = param[2]
		xyz_list[2] = param[1]

		return xyz_list

	attr_dict = dict()
	attr_dict['translation'] = cmds.xform(node_name, q=True, ws=True, t=True)
	attr_dict['rotation'] = cmds.xform(node_name, q=True, ws=True, ro=True)
	attr_dict['scale'] = cmds.xform(node_name, q=True, ws=True, s=True)
	attr_dict['rotatePivot'] = cmds.xform(node_name, q=True, ws=True, rp=True)
	attr_dict['scalePivot'] = cmds.xform(node_name, q=True, ws=True, sp=True)

	up_axis = cmds.upAxis(query=True, ax=True)
	if up_axis.lower() == 'y':
		attr_dict['translation'] = _xyz_list_build(attr_dict['translation'])
		attr_dict['rotation'] = _xyz_list_build(attr_dict['rotation'])
		attr_dict['scale'] = _xyz_list_build(attr_dict['scale'])
		attr_dict['rotatePivot'] = _xyz_list_build(attr_dict['rotatePivot'])
		attr_dict['scalePivot'] = _xyz_list_build(attr_dict['scalePivot'])

	return attr_dict


def get_transforms_for_mesh_node(node):
	"""
	Returns the transform values of the given mesh node.

	:param str node: transform node to get transform channel values for.
	:return: tuple containing the translation, rotation and scale values.
	:rtype: tuple(list(float, float, float), list(float, float, float), list(float, float, float))
	"""

	first_shape = get_first_in_list(cmds.listRelatives(node, shapes=True))
	if not first_shape or cmds.objectType(first_shape) != 'mesh':
		return list(), list(), list()

	first_shape = get_first_in_list(cmds.listRelatives(node, shapes=True, f=True))
	if not first_shape == '{}Shape'.format(node):
		if not cmds.referenceQuery(node, isNodeReferenced=True):
			cmds.rename(first_shape, '{}Shape'.format(node))

	translation_value = cmds.xform(node, query=True, t=True, ws=True)
	scale_value = cmds.xform(node, query=True, s=1, ws=True)
	world_matrix = OpenMaya.MMatrix(cmds.getAttr('{}.worldMatrix'.format(node)))
	transform_matrix = OpenMaya.MTransformationMatrix(world_matrix)
	euler_rotation = transform_matrix.rotation(asQuaternion=False)
	euler_rotation.reorderIt(3)
	rotation_value = [math.degrees(angle) for angle in (euler_rotation.x, euler_rotation.y, euler_rotation.z)]

	return translation_value, rotation_value, scale_value


def get_selected_cameras(camera_type='all'):
	"""
	Returns current selected cameras within current Maya scene.

	:param str camera_type: camera type.
	:return: list of selected cameras.
	:rtype: list(pm.Camera)
	"""

	selected_tranforms = cmds.ls(sl=True, long=True) or list()
	if not selected_tranforms:
		return list()

	found_cameras = list()
	for selected_tranform in selected_tranforms:
		transform_shapes = cmds.listRelatives(selected_tranform, shapes=True, noIntermediate=True)
		camera_shapes = [found_shape for found_shape in transform_shapes if cmds.nodeType(found_shape) == 'camera']
		found_cameras.extend(camera_shapes)

	return found_cameras


def node_is_mesh(node=None):
	"""
	Returns whether given Maya node is a mesh.

	:param str node: node to check.
	:return: True if given node is a mesh; False otherwise.
	:rtype: bool
	"""

	node = node or get_first_in_list(cmds.ls(sl=True, long=True))
	if not node:
		return False

	if cmds.listRelatives(node, c=True):
		if cmds.objectType(cmds.listRelatives(node, c=True, f=True)[0]) == 'mesh':
			return True

	return False


def get_skin_clusters_for_node(node):
	"""
	Returns list of skin clusters applied to given shape or transform node.

	:param str node: name of the shape or transform we want to retrieve applied skin clusters for.
	:return: list of skin cluster node names.
	:rtype: list(str)
	"""

	found_skin_clusters = set()

	for connection in cmds.listConnections(node, d=True) or list():
		if cmds.objectType(connection) != 'skinCluster':
			continue
		found_skin_clusters.add(connection)

	return list(found_skin_clusters)


def get_skin_cluster_meshes(skin_cluster):
	"""
	Returns a list of all transform nodes of the meshes skinned to the given skin cluster node.

	:param str skin_cluster: skin cluster node to retrieved transform nodes skinned to it.
	:return: list of transform nodes.
	:rtype: list(str)
	"""

	found_meshes = set()
	for connection in cmds.listConnections(skin_cluster, d=True) or list():
		if cmds.objectType(connection) != 'transform':
			continue
		first_shape = get_first_in_list(cmds.listRelatives(connection, shapes=True) or list())
		if not first_shape or cmds.objectType(first_shape) != 'mesh':
			continue
		found_meshes.add(connection)

	return list(found_meshes)


def get_instances(nodes=None):
	"""
	Returns a list with all instances nodes. If not nodes are given, current selected nodes will be taken into
	consideration.

	:param list(str) or None nodes: list of nodes to check.
	:return: list of node names that are instances.
	:rtype: list(str)
	"""

	found_instances = list()
	orig_selection = cmds.ls(sl=True)
	node = get_first_in_list(force_list(nodes or orig_selection))
	cmds.select(node)
	iter_dag = OpenMaya.MItDag(OpenMaya.MItDag.kBreadthFirst)
	while not iter_dag.isDone():
		instanced = OpenMaya.MItDag.isInstanced(iter_dag)
		if instanced:
			found_instances.append(iter_dag.fullPathName())
		iter_dag.next()
	cmds.select(orig_selection) if orig_selection else cmds.select(clear=True)

	return found_instances


def setup_axis(axis):
	"""
	Updates all the model panels to match the correct view along axis
	axis: x or y

	Return: None
	"""

	if axis not in ('y', 'z'):
		"{} is not a valid up axis. Please choose 'y' or 'z'".format(axis)
		return

	cmds.upAxis(axis=axis, rv=True)
	model_panels = cmds.getPanel(type='modelPanel')
	cameras = [cmds.modelPanel(model_panel, q=True, camera=True) for model_panel in model_panels]
	for model_panel, camera in zip(model_panels, cameras):
		if camera == 'top':
			cmds.viewSet(camera, viewNegativeY=True) if axis == 'y' else cmds.viewSet(camera, viewNegativeZ=True)
		if camera == 'front':
			cmds.viewSet(camera, viewNegativeZ=True) if axis == 'y' else cmds.viewSet(camera, viewY=True)
		if camera == 'left' or camera == 'side':
			cmds.viewSet(camera, viewNegativeX=True) if axis == 'y' else cmds.viewSet(camera, viewNegativeX=True)
		if camera == 'right':
			cmds.viewSet(camera, viewX=True) if axis == 'y' else cmds.viewSet(camera, viewX=True)
		cmds.viewLookAt(camera)
		cmds.viewFit(camera, panel=model_panel, animate=False)


def get_frame_rate():
	"""
	Returns current scene frame rate.

	:return: scene frame rate.
	:rtype: int
	"""

	current_unit = cmds.currentUnit(query=True, time=True)
	if current_unit == 'film':
		return 24
	if current_unit == 'show':
		return 48
	if current_unit == 'pal':
		return 25
	if current_unit == 'ntsc':
		return 30
	if current_unit == 'palf':
		return 50
	if current_unit == 'ntscf':
		return 60
	if 'fps' in current_unit:
		return int(cmds.currentUnit(query=True, time=True).replace('fps',''))

	return 1


def timer(f):
	"""
	Function decorator that gets the elapsed time with a more descriptive output.

	:param callable f: decorated function
	"""

	@wraps(f)
	def wrapper(*args, **kwargs):
		start_time = time.time()
		res = f(*args, **kwargs)
		function_name = f.func_name if is_python2() else f.__name__
		logger.info('<{}> Elapsed time : {}'.format(function_name, time.time() - start_time))
		return res
	return wrapper


def keep_selection_decorator(fn):
	"""
	Function decorator that makes sure that original selection is keep after executing the wrapped function.

	:param callable fn: decorated function.
	"""

	@wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			tmp_selection = cmds.ls(sl=True, l=True)
			result = None
			try:
				result = fn(*args, **kwargs)
			except Exception:
				raise
			finally:
				cmds.select(tmp_selection)
			return result
		except Exception:
			raise
	return wrapper


def viewport_off(fn):
	"""
	Function decorator that turns off Maya display while the function is being executed.

	:param callable fn: decorated function.
	"""

	@wraps(fn)
	def wrapper(*args, **kwargs):
		parallel = False
		maya_version = mel.eval("$mayaVersion = `getApplicationVersionAsFloat`")
		if maya_version >= 2016:
			if 'parallel' in cmds.evaluationManager(q=True, mode=True):
				cmds.evaluationManager(mode='off')
				parallel = True
				logger.debug('Turning off Parallel evaluation...')
		# turn $gMainPane Off and hide the time slider (this is the important part):
		mel.eval('paneLayout -e -manage false $gMainPane')
		cmds.refresh(suspend=True)
		mel.eval('setTimeSliderVisible 0;')

		try:
			return fn(*args, **kwargs)
		finally:
			cmds.refresh(suspend=False)
			mel.eval('setTimeSliderVisible 1;')
			if parallel:
				cmds.evaluationManager(mode='parallel')
				logger.debug('Turning on Parallel evaluation...')
			mel.eval('paneLayout -e -manage true $gMainPane')
			cmds.refresh()

	return wrapper
