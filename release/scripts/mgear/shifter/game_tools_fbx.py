import os
import timeit
import importlib
from functools import partial

import maya.cmds as cmds
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

# from mgear.vendor.Qt import QtWidgets
# from mgear.vendor.Qt import QtCore
# from mgear.vendor.Qt import QtGui
# TODO: comment out later. using direct import for better auto completion
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

from mgear.core import pyqt
from mgear.core import widgets
from mgear.core import attribute
from mgear.core import utils
from mgear.core import string
from mgear.core import callbackManager
from mgear.core import pyFBX as pfbx

from mgear.shifter import game_tools_fbx_utils as fu

from mgear.uegear import bridge, commands as uegear


class FBXExport(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FBXExport, self).__init__(parent)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.setWindowTitle("Shifter's FBX Export")
        min_w = 300
        default_w = 400
        default_h = 800
        self.setMinimumWidth(min_w)
        self.resize(default_w, default_h)

        self.create_actions()
        self.create_widgets()
        self.create_layout()
        self.create_connections()

        self.refresh_fbx_sdk_ui()
        self.refresh_ue_connection()

    def create_actions(self):
        # file actions
        self.file_export_preset_action = QtWidgets.QAction("Export Preset", self)
        self.file_export_preset_action.setIcon(pyqt.get_icon("mgear_log-out"))
        self.file_import_preset_action = QtWidgets.QAction("Import Preset", self)
        self.file_import_preset_action.setIcon(pyqt.get_icon("mgear_log-in"))
        self.set_fbx_sdk_path_action = QtWidgets.QAction("Set Python FBX SDK", self)
        self.fbx_sdk_path_action = QtWidgets.QAction("Python FBX SDK Path: Not set", self)
        self.fbx_sdk_path_action.setEnabled(False)
        self.refresh_uegear_connection_action = QtWidgets.QAction("Refresh Unreal Engine Connection", self)
        self.refresh_uegear_connection_action.setIcon(pyqt.get_icon("mgear_refresh-cw"))

    def create_widgets(self):

        # menu bar
        self.menu_bar = QtWidgets.QMenuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.file_menu.addAction(self.file_export_preset_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.file_import_preset_action)
        self.file_menu.addSeparator()
        self.fbx_sdk_menu = self.menu_bar.addMenu("FBX SDK")
        self.fbx_sdk_menu.addAction(self.set_fbx_sdk_path_action)
        self.fbx_sdk_menu.addSeparator()
        self.fbx_sdk_menu.addAction(self.fbx_sdk_path_action)
        self.uegear_menu = self.menu_bar.addMenu("ueGear")
        self.uegear_menu.addAction(self.refresh_uegear_connection_action)

        # set source roots
        self.geo_root_label = QtWidgets.QLabel("Geo Root")
        self.geo_root_list = QtWidgets.QListWidget()
        self.geo_root_list.setSelectionMode(QtWidgets.QListWidget.ExtendedSelection)
        self.geo_root_set_button = QtWidgets.QPushButton()
        self.geo_root_set_button.setIcon(pyqt.get_icon("mgear_mouse-pointer"))
        self.geo_root_add_button = QtWidgets.QPushButton()
        self.geo_root_add_button.setIcon(pyqt.get_icon("mgear_plus"))
        self.geo_root_remove_button = QtWidgets.QPushButton()
        self.geo_root_remove_button.setIcon(pyqt.get_icon("mgear_minus"))
        self.geo_root_auto_set_button = QtWidgets.QPushButton("Auto")
        self.geo_root_auto_set_button.setMaximumWidth(40)

        self.joint_root_label = QtWidgets.QLabel("Joint Root")
        self.joint_root_list = QtWidgets.QListWidget()
        self.joint_root_list.setSelectionMode(QtWidgets.QListWidget.ExtendedSelection)
        self.joint_root_set_button = QtWidgets.QPushButton()
        self.joint_root_set_button.setIcon(pyqt.get_icon("mgear_mouse-pointer"))
        self.joint_root_add_button = QtWidgets.QPushButton()
        self.joint_root_add_button.setIcon(pyqt.get_icon("mgear_plus"))
        self.joint_root_remove_button = QtWidgets.QPushButton()
        self.joint_root_remove_button.setIcon(pyqt.get_icon("mgear_minus"))
        self.joint_root_auto_set_button = QtWidgets.QPushButton("Auto")
        self.joint_root_auto_set_button.setMaximumWidth(40)

        # settings
        self.up_axis_combobox = QtWidgets.QComboBox()
        self.up_axis_combobox.addItem("Y")
        self.up_axis_combobox.addItem("Z")
        self.file_type_combobox = QtWidgets.QComboBox()
        self.file_type_combobox.addItem("Binary")
        self.file_type_combobox.addItem("ASCII")
        self.fbx_version_combobox = QtWidgets.QComboBox()
        self.populate_fbx_versions_combobox(self.fbx_version_combobox)
        self.fbx_export_presets_combobox = QtWidgets.QComboBox()
        self.populate_fbx_export_presets_combobox(self.fbx_export_presets_combobox)

        # FBX SDK settings
        self.separated_meshes_checkbox = QtWidgets.QCheckBox("Separated Meshes")
        self.separated_meshes_checkbox.setChecked(True)
        self.remove_namespace_checkbox = QtWidgets.QCheckBox("Remove Namespace")
        self.remove_namespace_checkbox.setChecked(True)
        self.clean_scene_checkbox = QtWidgets.QCheckBox("Joint and Geo Root Child of Scene Root + Clean Up Scene")
        self.clean_scene_checkbox.setChecked(True)

        # path and filename
        self.file_path_label = QtWidgets.QLabel("Path")
        self.file_path_lineedit = QtWidgets.QLineEdit()
        self.file_path_set_button = widgets.create_button(icon="mgear_folder")

        self.file_name_label = QtWidgets.QLabel("File Name")
        self.file_name_lineedit = QtWidgets.QLineEdit()

        # export skeletalMesh settings
        self.skinning_checkbox = QtWidgets.QCheckBox("Skinning")
        self.skinning_checkbox.setChecked(True)
        self.blendshapes_checkbox = QtWidgets.QCheckBox("Blendshapes")
        self.blendshapes_checkbox.setChecked(True)
        self.export_skeletal_geo_button = QtWidgets.QPushButton(
            "Export SkeletalMesh/SkinnedMesh"
        )
        self.export_skeletal_geo_button.setStyleSheet(
            "QPushButton {background:rgb(70, 100, 150); }"
        )

        # export animation
        self.export_animation_button = QtWidgets.QPushButton(
            "Export Animation"
        )
        self.export_animation_button.setStyleSheet(
            "QPushButton {background:rgb(150, 35, 50); }"
        )

        # Unreal Engine import
        # path and filename
        self.ue_file_path_label = QtWidgets.QLabel("Path")
        self.ue_file_path_lineedit = QtWidgets.QLineEdit()
        self.ue_file_path_set_button = widgets.create_button(icon="mgear_folder")



    def create_layout(self):

        # set source layout
        self.geo_root_layout = QtWidgets.QVBoxLayout()
        self.geo_root_layout.setContentsMargins(1, 1, 1, 1)
        self.geo_root_label_layout = QtWidgets.QHBoxLayout()
        self.geo_root_label_layout.setContentsMargins(1, 1, 1, 1)
        self.geo_root_label_layout.addStretch()
        self.geo_root_label_layout.addWidget(self.geo_root_label)
        self.geo_root_label_layout.addStretch()
        self.geo_root_layout.addLayout(self.geo_root_label_layout)
        self.geo_root_layout.addWidget(self.geo_root_list)
        self.geo_root_buttons_layout = QtWidgets.QHBoxLayout()
        self.geo_root_buttons_layout.setContentsMargins(1, 1, 1, 1)
        self.geo_root_buttons_layout.addWidget(self.geo_root_set_button)
        self.geo_root_buttons_layout.addWidget(self.geo_root_add_button)
        self.geo_root_buttons_layout.addWidget(self.geo_root_remove_button)
        self.geo_root_buttons_layout.addStretch()
        self.geo_root_buttons_layout.addWidget(self.geo_root_auto_set_button)
        self.geo_root_layout.addLayout(self.geo_root_buttons_layout)

        self.joint_root_layout = QtWidgets.QVBoxLayout()
        self.joint_root_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_label_layout = QtWidgets.QHBoxLayout()
        self.joint_root_label_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_label_layout.addStretch()
        self.joint_root_label_layout.addWidget(self.joint_root_label)
        self.joint_root_label_layout.addStretch()
        self.joint_root_layout.addLayout(self.joint_root_label_layout)
        self.joint_root_layout.addWidget(self.joint_root_list)
        self.joint_root_buttons_layout = QtWidgets.QHBoxLayout()
        self.joint_root_buttons_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_buttons_layout.addWidget(self.joint_root_set_button)
        self.joint_root_buttons_layout.addWidget(self.joint_root_add_button)
        self.joint_root_buttons_layout.addWidget(self.joint_root_remove_button)
        self.joint_root_buttons_layout.addStretch()
        self.joint_root_buttons_layout.addWidget(self.joint_root_auto_set_button)
        self.joint_root_layout.addLayout(self.joint_root_buttons_layout)

        self.set_source_layout = QtWidgets.QHBoxLayout()
        self.set_source_layout.addLayout(self.geo_root_layout)
        self.set_source_layout.addLayout(self.joint_root_layout)
        self.set_source_layout.setSpacing(2)

        self.set_source_collap_wgt = widgets.CollapsibleWidget(
            "Set Source Elements"
        )
        self.set_source_collap_wgt.addLayout(self.set_source_layout)

        # settings layout
        self.settings_groupbox = QtWidgets.QGroupBox("FBX Settings")
        self.settings_form_layout = QtWidgets.QFormLayout(
            self.settings_groupbox
        )

        self.settings_form_layout.addRow("Up Axis", self.up_axis_combobox)
        self.settings_form_layout.addRow("File Type", self.file_type_combobox)
        self.settings_form_layout.addRow("File Version", self.fbx_version_combobox)
        self.settings_form_layout.addRow("FBX Preset", self.fbx_export_presets_combobox)


        # FBX SDK settings
        if pfbx.FBX_SDK:
            title = "FBX SDK settings"
        else:
            title = "FBX SDK settings (Disable SDK Not Found)"

        self.sdk_settings_groupbox = QtWidgets.QGroupBox(title)
        self.sdk_settings_layout = QtWidgets.QVBoxLayout(
            self.sdk_settings_groupbox
        )
        self.sdk_settings_layout.addWidget(self.remove_namespace_checkbox)
        self.sdk_settings_layout.addWidget(self.clean_scene_checkbox)
        self.sdk_settings_layout.addWidget(self.separated_meshes_checkbox)

        # general setting collapsible widget
        self.settings_collap_wgt = widgets.CollapsibleWidget("Settings")
        self.settings_collap_wgt.addWidget(self.settings_groupbox)
        self.settings_collap_wgt.addWidget(self.sdk_settings_groupbox)

        # export path layout
        self.file_path_layout = QtWidgets.QHBoxLayout()
        self.file_path_layout.setContentsMargins(1, 1, 1, 1)
        self.file_path_layout.addWidget(self.file_path_label)
        self.file_path_layout.addWidget(self.file_path_lineedit)
        self.file_path_layout.addWidget(self.file_path_set_button)

        self.file_name_layout = QtWidgets.QHBoxLayout()
        self.file_name_layout.setContentsMargins(1, 1, 1, 1)
        self.file_name_layout.addWidget(self.file_name_label)
        self.file_name_layout.addWidget(self.file_name_lineedit)

        self.path_layout = QtWidgets.QVBoxLayout()
        self.path_layout.addLayout(self.file_path_layout)
        self.path_layout.addLayout(self.file_name_layout)
        self.path_layout.setSpacing(2)

        self.file_path_collap_wgt = widgets.CollapsibleWidget("File Path")
        self.file_path_collap_wgt.addLayout(self.path_layout)

        # export skeletalMesh layout
        self.model_deformers_groupbox = QtWidgets.QGroupBox("Deformers")
        self.model_deformers_layout = QtWidgets.QHBoxLayout(
            self.model_deformers_groupbox
        )
        self.model_deformers_layout.addWidget(self.skinning_checkbox)
        self.model_deformers_layout.addWidget(self.blendshapes_checkbox)

        self.export_geo_collap_wgt = widgets.CollapsibleWidget(
            "Export Skeletal Geo"
        )
        self.export_geo_collap_wgt.addWidget(self.model_deformers_groupbox)
        self.export_geo_collap_wgt.addWidget(self.export_skeletal_geo_button)

        # export Animation layout
        self.export_anim_collap_wgt = widgets.CollapsibleWidget(
            "Export Animation"
        )
        self.export_anim_collap_wgt.addWidget(self.export_animation_button)

        # Unreal Engine import layout
        self.ue_import_collap_wgt = widgets.CollapsibleWidget(
            "Unreal Engine Import"
        )

        self.ue_import_cbx = QtWidgets.QCheckBox('Enable Unreal Engine Import?')

        self.ue_file_path_layout = QtWidgets.QHBoxLayout()
        self.ue_file_path_layout.setContentsMargins(1, 1, 1, 1)
        self.ue_file_path_layout.addWidget(self.ue_file_path_label)
        self.ue_file_path_layout.addWidget(self.ue_file_path_lineedit)
        self.ue_file_path_layout.addWidget(self.ue_file_path_set_button)

        self.ue_path_layout = QtWidgets.QVBoxLayout()
        self.ue_path_layout.addLayout(self.ue_file_path_layout)
        self.ue_path_layout.addSpacing(2)

        self.ue_import_collap_wgt.addWidget(self.ue_import_cbx)
        self.ue_import_collap_wgt.addLayout(self.ue_path_layout)

        # Scroll Area layout
        self.base_scrollarea_wgt = QtWidgets.QWidget()

        self.scrollarea_layout = QtWidgets.QVBoxLayout(
            self.base_scrollarea_wgt
        )
        self.scrollarea_layout.setContentsMargins(2, 2, 2, 2)
        self.scrollarea_layout.setSpacing(2)
        self.scrollarea_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scrollarea_layout.addWidget(self.set_source_collap_wgt)
        self.scrollarea_layout.addWidget(self.settings_collap_wgt)
        self.scrollarea_layout.addWidget(self.file_path_collap_wgt)
        self.scrollarea_layout.addWidget(self.ue_import_collap_wgt)
        self.scrollarea_layout.addWidget(self.export_geo_collap_wgt)
        self.scrollarea_layout.addWidget(self.export_anim_collap_wgt)

        self.scrollarea_wgt = QtWidgets.QScrollArea(self)
        self.scrollarea_wgt.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scrollarea_wgt.setWidgetResizable(True)
        self.scrollarea_wgt.setWidget(self.base_scrollarea_wgt)

        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)
        self.main_layout.setMenuBar(self.menu_bar)

        self.main_layout.addWidget(self.scrollarea_wgt)

    def create_connections(self):

        self.set_fbx_sdk_path_action.triggered.connect(self.set_fbx_sdk_path)
        self.refresh_uegear_connection_action.triggered.connect(self.refresh_ue_connection)

        self.geo_root_set_button.clicked.connect(
            partial(
                self.set_list_items_from_sel,
                self.geo_root_list,
                "transform",
            )
        )
        self.geo_root_add_button.clicked.connect(
            partial(
                self.add_list_items_from_sel,
                self.geo_root_list,
                "transform"
            )
        )
        self.geo_root_remove_button.clicked.connect(
            partial(
                self.remove_list_items_from_sel,
                self.geo_root_list
            )
        )
        self.geo_root_auto_set_button.clicked.connect(partial(self.auto_set_geo_roots, clear=True))

        self.joint_root_set_button.clicked.connect(
            partial(
                self.set_list_items_from_sel,
                self.joint_root_list,
                "joint",
            )
        )
        self.joint_root_add_button.clicked.connect(
            partial(
                self.add_list_items_from_sel,
                self.joint_root_list,
                "joint"
            )
        )
        self.joint_root_remove_button.clicked.connect(
            partial(
                self.remove_list_items_from_sel,
                self.joint_root_list
            )
        )
        self.joint_root_auto_set_button.clicked.connect(partial(self.auto_set_joint_roots, clear=True))
        self.file_name_lineedit.textChanged.connect(self.normalize_name)
        self.file_path_set_button.clicked.connect(self.set_folder_path)
        self.export_skeletal_geo_button.clicked.connect(
            self.export_skeletal_mesh
        )

        self.ue_file_path_set_button.clicked.connect(self.set_ue_folder_path)


    # slots

    def normalize_name(self):
        name = string.removeInvalidCharacter2(self.file_name_lineedit.text())
        self.file_name_lineedit.setText(name)

    def populate_fbx_versions_combobox(self, combobox):
        fbx_versions = pfbx.get_fbx_versions()
        for v in fbx_versions:
            combobox.addItem(v)

    def populate_fbx_export_presets_combobox(self, combobox):
        fbx_export_file_paths = pfbx.get_fbx_export_presets()
        for fbx_export_file_path in fbx_export_file_paths:
            fbx_export_file_name = os.path.basename(fbx_export_file_path)
            fbx_export_base_file_name, _ = os.path.splitext(fbx_export_file_name)
            combobox.addItem(fbx_export_base_file_name, userData=fbx_export_file_path)

        # Force user defined as the default preset
        combobox.setCurrentText('User defined')

    def populate_fbx_import_presets_combobox(self, combobox):
        fbx_import_file_paths = pfbx.get_fbx_import_presets()
        for fbx_import_file_path in fbx_export_file_paths:
            fbx_export_file_name = os.path.basename(fbx_import_file_path)
            fbx_export_base_file_name, _ = os.path.splitext(fbx_export_file_name)
            combobox.addItem(fbx_export_base_file_name, userData=fbx_import_file_path)

        # Force user defined as the default preset
        combobox.setCurrentText('User defined')


    def set_folder_path(self):
        folder_path = pm.fileDialog2(fileMode=3)
        if folder_path:
            self.file_path_lineedit.setText(
                string.normalize_path(folder_path[0])
            )

    def set_fbx_sdk_path(self):
        current_fbx_sdk_path = pfbx.get_fbx_sdk_path()
        fbx_sdk_path = pm.fileDialog2(fileMode=3, startingDirectory=current_fbx_sdk_path)
        if fbx_sdk_path:
            pfbx.set_fbx_skd_path(fbx_sdk_path[0], user=True)

        self.refresh_fbx_sdk_ui()

    def refresh_fbx_sdk_ui(self):
        self.remove_namespace_checkbox.setEnabled(pfbx.FBX_SDK)
        self.clean_scene_checkbox.setEnabled(pfbx.FBX_SDK)
        self.separated_meshes_checkbox.setEnabled(pfbx.FBX_SDK)

        fbx_sdk_path = pfbx.get_fbx_sdk_path()
        if not fbx_sdk_path or not os.path.isdir(fbx_sdk_path):
            self.fbx_sdk_path_action.setText("Python FBX SDK: Not set")
        else:
            self.fbx_sdk_path_action.setText("Python FBX SDK: {}".format(fbx_sdk_path))

    def refresh_ue_connection(self):
        is_available = bool(uegear.content_project_directory())
        self.ue_import_collap_wgt.setEnabled(is_available)
        if not is_available:
            cmds.warning('Unreal Engine Import functionality not available. Run Unreal Engine and load ueGear plugin.')
            self.ue_import_cbx.setChecked(False)

    def set_ue_folder_path(self):
        content_folder = uegear.content_project_directory()
        folder_path = cmds.fileDialog2(fileMode=3, startingDirectory=content_folder)
        if folder_path:
            self.ue_file_path_lineedit.setText(string.normalize_path(folder_path[0]))


    def export_skeletal_mesh(self):

        self.auto_set_geo_roots()
        self.auto_set_joint_roots()
        self.auto_file_path()

        # retrieve export config
        geos = [self.geo_root_list.item(i).text() for i in range(self.geo_root_list.count())]
        jnt_roots = [self.joint_root_list.item(i).text() for i in range(self.joint_root_list.count())]
        up_axis = self.up_axis_combobox.currentText()
        file_type = self.file_type_combobox.currentText()
        fbx_version = self.fbx_version_combobox.currentText()
        remove_namespace = self.remove_namespace_checkbox.isChecked()
        scene_clean = self.clean_scene_checkbox.isChecked()
        separated_meshes = self.separated_meshes_checkbox.isChecked()
        file_name = self.file_name_lineedit.text()
        file_path = self.file_path_lineedit.text()
        skinning = self.skinning_checkbox.isChecked()
        blendshapes = self.blendshapes_checkbox.isChecked()

        path = string.normalize_path(
            os.path.join(file_path, file_name + ".fbx")
        )

        current_export_preset = self.fbx_export_presets_combobox.currentText()
        if not current_export_preset or current_export_preset == 'User defined':
            fu.export_skeletal_mesh(
                jnt_roots,
                geos,
                path,
                up_axis=up_axis,
                file_type=file_type,
                fbx_version=fbx_version,
                remove_namespace=remove_namespace,
                scene_clean=scene_clean,
                skinning=skinning,
                blendshapes=blendshapes,
                separated_meshes=separated_meshes
            )
        # else:
        #     preset_file_path = self.fbx_export_presets_combobox.itemData(self.fbx_export_presets_combobox.currentIndex())
        #     if not preset_file_path or not os.path.isfile(preset_file_path):
        #         cmds.error('FBX Export Preset file was not found: "{}"'.format(preset_file_path))
        #         return
        #     fu.export_skeletal_mesh_from_preset(jnt_root, geo, path, preset_path=preset_file_path)
        #
        # # automatically import FBX into Unreal if necessary
        # if self.ue_import_cbx.isChecked() and os.path.isfile(path):
        #     uegear_bridge = bridge.UeGearBridge()
        #     import_path = self.ue_file_path_lineedit.text()
        #     if not import_path or not os.path.isdir(import_path):
        #         cmds.warning('Unreal Engine Import Path does not exist: "{}"'.format(import_path))
        #         return
        #     asset_name = os.path.splitext(os.path.basename(path))[0]
        #     import_options = {'destination_name': asset_name, 'replace_existing': True, 'save': False}
        #     result = uegear_bridge.execute(
        #         'import_skeletal_mesh', parameters={
        #             'fbx_file': path,
        #             'import_path': import_path,
        #             'import_options': str(import_options)
        #         }).get('ReturnValue', False)
        #     if not result:
        #         cmds.warning('Was not possible to export asset: {}. Please check Unreal Engine Output Log'.format(asset_name))

        return True


    # Helper methods

    def list_to_str(self, element_list):
        """Create a comma "," separated list with the string names of the elements

        Args:
            element_list (list): PyNode list

        Returns:
            str: formatted string list
        """
        str_list = element_list[0].name()
        if len(element_list) > 1:
            for e in element_list[1:]:
                str_list = "{},{}".format(str_list, e.name())

        return str_list

    def auto_set_geo_roots(self, clear=False):
        if clear:
            self.geo_root_list.clear()

        if not self.geo_root_list.count():
            g_roots = fu.get_geo_root() or list()
            for g_root in g_roots:
                self.geo_root_list.addItem(g_root.name())

    def auto_set_joint_roots(self, clear=False):
        if clear:
            self.joint_root_list.clear()

        if not self.joint_root_list.count():
            j_roots = fu.get_joint_root() or list()
            for j_root in j_roots:
                self.joint_root_list.addItem(j_root.name())

    def auto_file_path(self):
        if (
            not self.file_path_lineedit.text()
            or not self.file_name_lineedit.text()
        ):
            file_path = pm.fileDialog2(fileMode=0, fileFilter="FBX(*.fbx)")
            if file_path:
                dir_name = os.path.dirname(file_path[0])
                file_name = os.path.splitext(os.path.basename(file_path[0]))[0]

                self.file_path_lineedit.setText(
                    string.normalize_path(dir_name)
                )
                self.file_name_lineedit.setText(file_name)

    def get_rig_root():
        return

    def filter_sel_by_type(self, type_filter=None):
        """Return the element names if match the correct type

        Args:
            type_filter (str, optional): Type to filter: for example "joint"
                                         or "transform"

        Returns:
            list[str]: list of filtered node names.

        """

        filter_sel = list()
        sel = pm.selected()
        if not sel:
            pm.displayWarning("Nothing selected")
            return

        for node in sel:
            if type_filter:
                sel_type = sel[0].type()
                if not type_filter == sel_type:
                    pm.displayWarning(
                        "Selected element is not of type: {}".format(type_filter)
                    )
                    continue
            filter_sel.append(node.name())

        return filter_sel

    def set_list_items_from_sel(self, listwidget, type_filter):
        """Set list widget items from selected element filtered by type

        Args:
            listwidget (QListWidget): QT line list widget object
            type_filter (str): Type to filter: for example "joint"
                               or "transform"
        """

        listwidget.clear()
        node_names = self.filter_sel_by_type(type_filter)
        for node_name in node_names:
            listwidget.addItem(node_name)

    def add_list_items_from_sel(self, listwidget, type_filter):
        """Adds list widget items from selected element filtered by type

        Args:
            listwidget (QListWidget): QT line list widget object
            type_filter (str): Type to filter: for example "joint"
                               or "transform"
        """

        item_names = [listwidget.item(i).text() for i in range(listwidget.count())]
        node_names = self.filter_sel_by_type(type_filter)
        for node_name in node_names:
            if node_name in item_names:
                continue
            listwidget.addItem(node_name)

    def remove_list_items_from_sel(self, listwidget):
        """Removes list widget items from selected list items

        Args:
            listwidget (QListWidget): QT line list widget object
        """

        selected_items = listwidget.selectedItems()
        for selected_item in selected_items:
            listwidget.takeItem(listwidget.row(selected_item))



def openFBXExport(*args):
    return pyqt.showDialog(FBXExport, dockable=True)


if __name__ == "__main__":

    from mgear.shifter import game_tools_fbx_widgets

    import sys

    if sys.version_info[0] == 2:
        reload(game_tools_fbx_widgets)
    else:
        importlib.reload(game_tools_fbx_widgets)

    start = timeit.default_timer()

    openFBXExport()

    end = timeit.default_timer()
    timeConsumed = end - start
    print("{} time elapsed running".format(timeConsumed))
