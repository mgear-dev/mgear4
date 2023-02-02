import os
import sys
import traceback
from collections import OrderedDict

import pymel.core as pm
import maya.cmds as cmds

from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui

from mgear.core import pyFBX as pfbx
from mgear.core import pyqt
from mgear.shifter import game_tools_fbx_sdk_utils

NO_EXPORT_TAG = 'no_export'
WORLD_CONTROL_NAME = 'world_ctl'


def export_skeletal_mesh(jnt_roots, geo_roots, path, **kwargs):

    preset_path = kwargs.get('preset_path', None)
    up_axis = kwargs.get('up_axis', None)
    file_type = kwargs.get('file_type', 'binary').lower()
    fbx_version = kwargs.get('fbx_version', None)
    remove_namespaces = kwargs.get('remove_namespace')
    scene_clean = kwargs.get('scene_clean', True)
    skinning = kwargs.get('skinning', True)
    blendshapes = kwargs.get('blendshapes', True)
    use_partitions = kwargs.get('use_partitions', True)
    partitions = kwargs.get('partitions', None)

    # export settings config
    pfbx.FBXResetExport()

    # set configuration
    fbx_version_str = None
    if up_axis is not None:
        pfbx.FBXExportUpAxis(up_axis)
    if fbx_version is not None:
        fbx_version_str = '{}00'.format(fbx_version.split('/')[0].replace(' ', ''))
        pfbx.FBXExportFileVersion(v=fbx_version_str)
    if file_type == 'ascii':
        pfbx.FBXExportInAscii(v=True)
    pfbx.FBXExportSkins(v=skinning)
    pfbx.FBXExportShapes(v=blendshapes)
    # if preset is given, previous defined settinsg will be overriden
    if preset_path is not None:
        # load FBX export preset file
        pfbx.FBXLoadExportPresetFile(f=preset_path)

    # select elements and export all the data
    pm.select(jnt_roots + geo_roots)

    fbx_modified = False
    pfbx.FBXExport(f=path, s=True)
    fbx_file = game_tools_fbx_sdk_utils.FbxSdkGameToolsWrapper(path)
    if scene_clean:
        fbx_file.clean_scene(no_export_tag=NO_EXPORT_TAG, world_control_name=WORLD_CONTROL_NAME)
        fbx_modified = True
    if remove_namespaces:
        fbx_file.remove_namespaces()
        fbx_modified = True
    if fbx_modified:
        fbx_file.save(
            mode=file_type, file_version=fbx_version_str, close=True, preset_path=preset_path,
            skins=skinning, blendshapes=blendshapes)

    # post process with FBX SDK if available
    if pfbx.FBX_SDK:
        if use_partitions:
            if not partitions:
                cmds.warning("No Mesh partitions defined")
                return False
            export_skeletal_mesh_partitions(
                jnt_roots=jnt_roots, mesh_partitions=partitions, path=path,
                skins=skinning, blendshapes=blendshapes)

    return True


def export_skeletal_mesh_partitions(jnt_roots, mesh_partitions, path, deformations=None, skins=None, blendshapes=None):

    if not pfbx.FBX_SDK:
        cmds.warning("Python FBX SDK is not available. Skeletal Mesh partitions export functionality is not available!")
        return False

    # data that will be exported into a temporal file
    partitions_data = OrderedDict()

    for mesh_partition in mesh_partitions:

        # we retrieve all end joints from the the influenced joints
        influences = pm.skinCluster(mesh_partition, query=True, influence=True)

        # make sure the hierarchy from the root joint to the influence joints is retrieved.
        joint_hierarchy = OrderedDict()
        for jnt_root in jnt_roots:
            joint_hierarchy.setdefault(jnt_root, list())
            for inf_jnt in influences:
                jnt_hierarchy = joint_list(jnt_root, inf_jnt)
                for hierarchy_jnt in jnt_hierarchy:
                    if hierarchy_jnt not in joint_hierarchy[jnt_root]:
                        joint_hierarchy[jnt_root].append(hierarchy_jnt)

        partitions_data.setdefault(mesh_partition, dict())

        # the joint chain to export will be the shorter one between the root joint and the influences
        short_hierarchy = None
        for root_jnt, joint_hierarchy in joint_hierarchy.items():
            total_joints = len(joint_hierarchy)
            if total_joints <= 0:
                continue
            if short_hierarchy is None:
                short_hierarchy = joint_hierarchy
                partitions_data[mesh_partition]['root'] = root_jnt
            elif len(short_hierarchy) > len(joint_hierarchy):
                short_hierarchy = joint_hierarchy
                partitions_data[mesh_partition]['root'] = root_jnt
        if short_hierarchy is None:
            continue

        # we make sure we update the hierarchy to include all joints between the skeleton root joint and
        # the first joint of the found joint hierarchy
        root_jnt = root_joint(short_hierarchy[0])
        if root_jnt not in short_hierarchy:
            parent_hierarchy = joint_list(root_jnt, short_hierarchy[0])
            short_hierarchy = parent_hierarchy + short_hierarchy

        partitions_data[mesh_partition]['hierarchy'] = [jnt.name() for jnt in short_hierarchy]

    try:
        for mesh_partition_name, partition_data in partitions_data.items():
            fbx_file = game_tools_fbx_sdk_utils.FbxSdkGameToolsWrapper(path)
            fbx_file.export_skeletal_mesh(
                mesh_partition_name, partition_data['hierarchy'],
                deformations=deformations, skins=skins, blendshapes=blendshapes)
            fbx_file.close()
    except Exception as exc:
        cmds.error('Something wrong happened while export skeleton mesh: {}'.format(traceback.format_exc()))
        return False

    return True


def export_animation_clip():
    return


def get_geo_grp():
    """Return the goemetry group (objectSet in Maya) of the rig.
    If more than one xxx_geo_grp is available will pop up a selection list

    Returns:
        PyNode: objectSet
    """
    geo_grp = None
    geo_groups = pm.ls("*:*_geo_grp", "*_geo_grp", type="objectSet")
    if geo_groups:
        if len(geo_groups) > 1:
            item = select_item(geo_groups, "Select Geo Group")
            if item:
                geo_grp = pm.PyNode(item)
        else:
            geo_grp = geo_groups[0]
    return geo_grp


def get_geo_root():
    geo_grp = get_geo_grp()
    if geo_grp:
        memb = geo_grp.members()
        if memb:
            return memb
        else:
            pm.displayWarning("Geo_grp is empty. Please set geo root manually")
    else:
        pm.displayWarning(
            "Not Geo_grp available, please set geo roots manually"
        )


def get_joint_org():
    jnt_org = None
    joint_orgs = pm.ls("*:jnt_org", "*jnt_org", type="transform")
    if joint_orgs:
        if len(joint_orgs) > 1:
            item = select_item(joint_orgs, "Select Joint Org Node")
            if item:
                jnt_org = pm.PyNode(item)
        else:
            jnt_org = joint_orgs[0]
    return jnt_org


def get_joint_root():
    jnt_org = get_joint_org()
    if jnt_org:
        return jnt_org.getChildren()
    else:
        pm.displayWarning(
            "Not Joint found under jnt_org, please set joint roots manually"
        )


def select_item(items, title):
    """Create modal dialog to select item from list and return the selected tiem

    Args:
        items (list): List of str items
        title (str): Tittle for the modoal dialo

    Returns:
        str: selected item
    """
    item = None
    select_dialog = SelectorDialog(items, title)

    result = select_dialog.exec_()

    if result == QtWidgets.QDialog.Accepted:
        item = select_dialog.item

    return item


def root_joint(start_joint):
    """
    Recursively traverses up the hierarchy until finding the first object that does not have a parent.

    :param str node_name: node name to get root of.
    :param str node_type: node type for the root node.
    :return: found root node.
    :rtype: str
    """

    parent = pm.listRelatives(start_joint, parent=True, type='joint')
    parent = parent[0] if parent else None

    return root_joint(parent) if parent else start_joint


def joint_list(start_joint, end_joint):
    """Returns a list of joints between and including given start and end joint

    Args:
        start_joint str: start joint of joint list
        end_joint str end joint of joint list

    Returns:
        list[str]: joint list
    """

    if start_joint == end_joint:
        return [start_joint]

    # check hierarchy
    descendant_list = pm.ls(pm.listRelatives(start_joint, ad=True, fullPath=True), long=True, type='joint')
    if not descendant_list.count(end_joint):
        # raise Exception('End joint "{}" is not a descendant of start joint "{}"'.format(end_joint, start_joint))
        return list()

    joint_list = [end_joint]
    while joint_list[-1] != start_joint:
        parent_jnt = pm.listRelatives(joint_list[-1], p=True, pa=True, fullPath=True)
        if not parent_jnt:
            raise Exception('Found root joint while searching for start joint "{}"'.format(start_joint))
        joint_list.append(parent_jnt[0])

    joint_list.reverse()

    return joint_list


def end_joint(start_joint):

    end_joint = None
    next_joint = start_joint
    while next_joint:
        child_list = pm.listRelatives(next_joint, fullPath=True, c=True) or list()
        child_joints = pm.ls(child_list, long=True, type='joint') or list()
        if child_joints:
            next_joint = child_joints[0]
        else:
            end_joint = next_joint
            next_joint = None

    return end_joint



class SelectorDialog(QtWidgets.QDialog):
    def __init__(
        self, items=[], title="Selector Dialog", parent=pyqt.maya_main_window()
    ):
        super(SelectorDialog, self).__init__(parent)
        self.title = title
        self.items = items
        self.item = None

        self.setWindowTitle(self.title)
        self.setWindowFlags(
            self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
        )

        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        self.list_wgt = QtWidgets.QListWidget()
        for item in self.items:
            self.list_wgt.addItem(item.name())

        self.ok_btn = QtWidgets.QPushButton("OK")

    def create_layout(self):
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        main_layout.addWidget(self.list_wgt)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)

    def create_connections(self):
        self.list_wgt.itemClicked.connect(self.get_item)
        self.list_wgt.itemDoubleClicked.connect(self.accept)

        self.ok_btn.clicked.connect(self.accept)

    def get_item(self, item):
        self.item = item.text()


if __name__ == "__main__":

    if sys.version_info[0] == 2:
        reload(pfbx)
    else:
        import importlib

        importlib.reload(pfbx)

    # export_skeletal_mesh(
    #     "Root", "geo_root", r"C:\Users/Miquel/Desktop/testing_auto2.fbx"
    # )

    grp = get_joint_root()
    print(grp)
