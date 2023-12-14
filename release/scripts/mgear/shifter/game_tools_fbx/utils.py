import os
import sys
import ctypes
import ctypes.wintypes
import traceback
import subprocess
import tempfile

import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om

from mgear.vendor.Qt import QtWidgets, QtCore

from mgear.core import (
    pyFBX as pfbx,
    pyqt,
    string,
    utils as coreUtils,
    animLayers,
)
from mgear.shifter.game_tools_fbx import sdk_utils

NO_EXPORT_TAG = "no_export"
WORLD_CONTROL_NAME = "world_ctl"

FRAMES_PER_SECOND = {
    "24 FPS": ("film", 24),
    "30 FPS": ("ntsc", 30),
    "60 FPS": ("ntscf", 60),
    "120 FPS": ("120fps", 120),
}
AS_FRAMES = dict(FRAMES_PER_SECOND.values())
TRANSFORM_ATTRIBUTES = [
    "tx",
    "ty",
    "tz",
    "rx",
    "ry",
    "rz",
    "sx",
    "sy",
    "sz",
    "visibility",
]


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


def export_skeletal_mesh(export_data):
    geo_roots = export_data.get("geo_roots", "")
    joint_roots = [export_data.get("joint_root", "")]
    file_path = export_data.get("file_path", "")
    file_name = export_data.get("file_name", "")
    preset_path = export_data.get("preset_path", None)
    up_axis = export_data.get("up_axis", None)
    file_type = export_data.get("file_type", "binary").lower()
    fbx_version = export_data.get("fbx_version", None)
    remove_namespaces = export_data.get("remove_namespace", True)
    scene_clean = export_data.get("scene_clean", True)
    deformations = export_data.get("deformations", True)
    skinning = export_data.get("skinning", True)
    blendshapes = export_data.get("blendshapes", True)
    use_partitions = export_data.get("use_partitions", True)

    if not file_name.endswith(".fbx"):
        file_name = "{}.fbx".format(file_name)
    export_path = string.normalize_path(os.path.join(file_path, file_name))
    print("\t>>> Export Path: {}".format(export_path))

    # export settings config
    pfbx.FBXResetExport()

    # set configuration
    if preset_path is not None:
        # load FBX export preset file
        pfbx.FBXLoadExportPresetFile(f=preset_path)
    pfbx.FBXExportSkins(v=skinning)
    pfbx.FBXExportShapes(v=blendshapes)
    fbx_version_str = None
    if up_axis is not None:
        pfbx.FBXExportUpAxis(up_axis)
    if fbx_version is not None:
        fbx_version_str = "{}00".format(
            fbx_version.split("/")[0].replace(" ", "")
        )
        pfbx.FBXExportFileVersion(v=fbx_version_str)
    if file_type == "ascii":
        pfbx.FBXExportInAscii(v=True)

    # select elements and export all the data
    pm.select(geo_roots + joint_roots)

    # Exports the data from the scene that has teh tool open into a "master_fbx" file.
    pfbx.FBXExport(f=export_path, s=True)

    # Instead of altering the Maya scene file, we will alter the "master" fbx data.
    # The master fbx file is the file that has just been exported.

    path_is_valid = os.path.exists(export_path)

    if not path_is_valid:
        # "master" fbx file does not exist, exit early.
        return False

    # Create a temporary job python file
    script_content = """
python "from mgear.shifter.game_tools_fbx import fbx_batch";
python "master_path='{master_path}'";
python "root_joint='{joint_root}'";
python "root_geos={geo_roots}";
python "export_data={e_data}";
python "fbx_batch.perform_fbx_condition({ns}, {sc}, master_path, root_joint, root_geos, {sk}, {bs}, {ps}, export_data)";
""".format(
        ns=remove_namespaces,
        sc=scene_clean,
        master_path=export_path,
        geo_roots=geo_roots,
        joint_root= joint_roots[0],
        sk=skinning,
        bs=blendshapes,
        ps=use_partitions,
        e_data=export_data)

    script_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.mel')
    script_file.write(script_content)
    script_file_path = script_file.name
    script_file.close()

    mayabatch_dir = coreUtils.get_maya_path()

    # Depending on the os we would need to change from maya, to maya batch
    # windows uses mayabatch
    if str(coreUtils.get_os()) == "win64" or str(coreUtils.get_os()) == "nt":
        option = "mayabatch"
    else:
        option = "maya"

    if option == "maya":
        mayabatch_command = 'maya'
    else:
        mayabatch_command = "mayabatch"

    mayabatch_path = os.path.join(mayabatch_dir, mayabatch_command)
    mayabatch_args = [mayabatch_path]

    if option == "maya":
        mayabatch_args.append("-batch")

    mayabatch_args.append("-script")
    mayabatch_args.append(script_file_path)

    print("[Launching] MayaBatch")
    print("   {}".format(mayabatch_args))
    print("   {}".format(" ".join(mayabatch_args)))

# Use Popen for more control
    with subprocess.Popen(mayabatch_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False) as process:
        # Capture the output and errors
        stdout, stderr = process.communicate()

        # Check the return code
        returncode = process.returncode

        # Check the result
        if returncode == 0:
            print("Mayabatch process completed successfully.")
            print("-------------------------------------------")
            print("Output:", stdout)
            print("-------------------------------------------")
        else:
            print("Mayabatch process failed.")
            print("Error:", stderr)
            return False

    # If all goes well return the export path location, else None
    return True


def export_animation_clip(config_data, clip_data):
    """
    Exports a singular animation clip.

    config_data: The configuration for the scene/session
    clip_data: Information about the clip to be exported.

    :return: return the path of the newly exported fbx.
    :rtype: str
    """
    # Clip Data
    start_frame = clip_data.get(
        "start_frame", cmds.playbackOptions(query=True, minTime=True)
    )
    end_frame = clip_data.get(
        "end_frame", cmds.playbackOptions(query=True, maxTime=True)
    )
    title = clip_data.get("title", "")
    frame_rate = clip_data.get("geo_root", coreUtils.get_frame_rate())
    anim_layer = clip_data.get("anim_layer", "")

    # Config Data
    root_joint = config_data.get("joint_root", "")
    file_path = config_data.get("file_path", "")
    file_name = config_data.get("file_name", "")
    preset_path = config_data.get("preset_path", None)
    up_axis = config_data.get(
        "up_axis", cmds.optionVar(query="upAxisDirection")
    )
    file_type = config_data.get("file_type", "binary").lower()
    fbx_version = config_data.get("fbx_version", None)
    remove_namespaces = config_data.get("remove_namespace")
    scene_clean = config_data.get("scene_clean", True)

    # Validate timeline range
    if start_frame > end_frame:
        msg = "Start frame {} must be lower than the end frame {}"
        cmds.error(msg.format(start_frame, end_frame))
        return False

    # Validate file path
    if not file_path or not file_name:
        msg = "No valid file path or file name given for the FBX to export!"
        cmds.warning(msg)
        return False

    if title:
        file_name = "{}_{}".format(file_name, title)
    if not file_name.endswith(".fbx"):
        file_name = "{}.fbx".format(file_name)
    path = string.normalize_path(os.path.join(file_path, file_name))
    print("\t>>> Export Path: {}".format(path))

    auto_key_state = cmds.autoKeyframe(query=True, state=True)
    cycle_check = cmds.cycleCheck(query=True, evaluation=True)
    scene_modified = cmds.file(query=True, modified=True)
    current_frame_range = cmds.currentUnit(query=True, time=True)
    current_frame = cmds.currentTime(query=True)
    original_start_frame = cmds.playbackOptions(query=True, minTime=True)
    original_end_frame = cmds.playbackOptions(query=True, maxTime=True)
    temp_mesh = None
    temp_skin_cluster = None
    original_anim_layer_weights = animLayers.get_layer_weights()

    try:
        # set anim layer to enable
        if animLayers.animation_layer_exists(anim_layer):
            animLayers.set_layer_weight(anim_layer, toggle_other_off=True)

        # disable viewport
        mel.eval("paneLayout -e -manage false $gMainPane")

        pfbx.FBXResetExport()

        # set configuration
        if preset_path is not None:
            # load FBX export preset file
            pfbx.FBXLoadExportPresetFile(f=preset_path)
        pfbx.FBXExportSkins(v=False)
        pfbx.FBXExportShapes(v=False)
        fbx_version_str = None
        if up_axis is not None:
            pfbx.FBXExportUpAxis(up_axis)
        if fbx_version is not None:
            fbx_version_str = "{}00".format(
                fbx_version.split("/")[0].replace(" ", "")
            )
            pfbx.FBXExportFileVersion(v=fbx_version_str)
        if file_type == "ascii":
            pfbx.FBXExportInAscii(v=True)

        # # create temporal triangle to skin
        # temp_mesh = cmds.polyCreateFacet(point=[(-0, 0, 0), (0, 0, 0), (0, 0, 0)], name='mgear_temp_mesh')[0]
        # temp_skin_cluster = cmds.skinCluster(
        #     [root_joint], temp_mesh, toSelectedBones=False, maximumInfluences=1, skinMethod=0)[0]

        # select elements to export
        pm.select([root_joint])

        # Set frame range
        cmds.currentTime(start_frame)
        old_frame_rate = coreUtils.get_frame_rate()
        new_frame_rate = frame_rate
        # only set if frame rate changed
        mult_rate = new_frame_rate / old_frame_rate
        if mult_rate != 1:
            old_range = start_frame, end_frame
            start_frame = old_range[0] * mult_rate
            end_frame = old_range[1] * mult_rate
            coreUtils.set_frame_rate(frame_rate)

        pm.autoKeyframe(state=False)
        pfbx.FBXExportAnimationOnly(v=False)
        pfbx.FBXExportBakeComplexAnimation(v=True)
        pfbx.FBXExportBakeComplexStart(v=start_frame)
        pfbx.FBXExportBakeComplexEnd(v=end_frame)
        pfbx.FBXExportCameras(v=True)
        pfbx.FBXExportConstraints(v=True)
        pfbx.FBXExportLights(v=True)
        pfbx.FBXExportQuaternion(v="quaternion")
        pfbx.FBXExportAxisConversionMethod("none")
        pfbx.FBXExportApplyConstantKeyReducer(v=False)
        pfbx.FBXExportSmoothMesh(v=False)
        pfbx.FBXExportShapes(v=True)
        pfbx.FBXExportSkins(v=True)
        pfbx.FBXExportSkeletonDefinitions(v=True)
        pfbx.FBXExportEmbeddedTextures(v=False)
        pfbx.FBXExportInputConnections(v=True)
        pfbx.FBXExportInstances(v=True)
        pfbx.FBXExportUseSceneName(v=True)
        pfbx.FBXExportSplitAnimationIntoTakes(c=True)
        pfbx.FBXExportGenerateLog(v=False)
        pfbx.FBXExport(f=path, s=True)

        fbx_modified = False
        fbx_file = sdk_utils.FbxSdkGameToolsWrapper(path)
        fbx_file.parent_to_world(root_joint, remove_top_parent=True)
        if remove_namespaces:
            fbx_file.remove_namespaces()
            fbx_modified = True
        if scene_clean:
            fbx_file.clean_scene(
                no_export_tag=NO_EXPORT_TAG,
                world_control_name=WORLD_CONTROL_NAME,
            )
            fbx_modified = True
        if fbx_modified:
            fbx_file.save(
                mode=file_type,
                file_version=fbx_version_str,
                close=True,
                preset_path=preset_path,
                skins=True,
            )

    except Exception as exc:
        raise exc
    finally:
        # setup again original anim layer weights
        if anim_layer and original_anim_layer_weights:
            animLayers.set_layer_weights(original_anim_layer_weights)

        if temp_skin_cluster and cmds.objExists(temp_skin_cluster):
            cmds.delete(temp_skin_cluster)
        if temp_mesh and cmds.objExists(temp_mesh):
            cmds.delete(temp_mesh)

        cmds.currentTime(current_frame)
        cmds.currentUnit(time=current_frame_range)

        pm.autoKeyframe(state=auto_key_state)
        pm.cycleCheck(evaluation=cycle_check)
        cmds.playbackOptions(min=original_start_frame, max=original_end_frame)

        # if the scene was not modified before doing our changes, we force it back now
        if scene_modified is False:
            cmds.file(modified=False)

        # enable viewport
        mel.eval("paneLayout -e -manage true $gMainPane")

    return path


def create_mgear_playblast(
    file_name="", folder=None, start_frame=None, end_frame=None, scale=75
):
    file_name = file_name or "playblast"
    file_name = os.path.splitext(os.path.basename(file_name))[0]
    file_name = "{}.avi".format(file_name)
    time_range = cmds.playbackOptions(
        query=True, minTime=True
    ), cmds.playbackOptions(query=True, maxTime=True)
    start_frame = start_frame if start_frame is not None else time_range[0]
    end_frame = end_frame if end_frame is not None else time_range[1]
    if end_frame <= start_frame:
        end_frame = start_frame + 1

    if not folder or not os.path.isdir(folder):
        folder = get_mgear_playblasts_folder()
        if not os.path.isdir(folder):
            os.makedirs(folder)
    if not os.path.isdir(folder):
        cmds.warning(
            'Was not possible to create mgear playblasts folder: "{}"'.format(
                folder
            )
        )
        return False
    full_path = os.path.join(folder, file_name)
    count = 1
    while os.path.isfile(full_path):
        _file_name = "{}_{}{}".format(
            os.path.splitext(file_name)[0],
            count,
            os.path.splitext(file_name)[1],
        )
        full_path = os.path.join(folder, _file_name)
        count += 1

    cmds.playbackOptions(
        animationStartTime=start_frame,
        minTime=start_frame,
        animationEndTime=end_frame,
        maxTime=end_frame,
    )
    cmds.currentTime(start_frame, edit=True)
    cmds.playblast(p=scale, filename=full_path, forceOverwrite=True)

    return True


def get_mgear_playblasts_folder():
    CSIDL_PERSONAL = 5  # My Documents
    SHGFP_TYPE_CURRENT = 0  # Get current, not default value
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
    )
    documents_folder = os.path.abspath(buf.value)
    playblasts_folder = os.path.join(documents_folder, "mgear_playblasts")

    return playblasts_folder


def open_mgear_playblast_folder():
    folder = get_mgear_playblasts_folder()
    if not folder or not os.path.isdir(folder):
        cmds.warning(
            'Was not possible to open mgear playblasts folder: "{}"'.format(
                folder
            )
        )
        return False

    if sys.platform.startswith("darwin"):
        subprocess.Popen(["open", folder])
    elif os.name == "nt":
        os.startfile(folder)
    elif os.name == "posix":
        subprocess.Popen(["xdg-open", folder])
    else:
        cmds.error("OS not supported: {}".format(os.name))

    return True


def get_geo_grp():
    """Return the geometry group (objectSet in Maya) of the rig.
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


def get_end_joint(start_joint):
    end_joint = None
    next_joint = start_joint
    while next_joint:
        child_list = (
            pm.listRelatives(next_joint, fullPath=True, c=True) or list()
        )
        child_joints = pm.ls(child_list, long=True, type="joint") or list()
        if child_joints:
            next_joint = child_joints[0]
        else:
            end_joint = next_joint
            next_joint = None

    return end_joint


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
