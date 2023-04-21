import os
import timeit
import importlib
from functools import partial

import maya.cmds as cmds
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore

from mgear.core import pyqt
from mgear.core import widgets
from mgear.core import string
from mgear.core import pyFBX as pfbx

from mgear.shifter import game_tools_fbx_utils as fu, game_tools_fbx_widgets as fuw

from mgear.uegear import bridge, commands as uegear


class FBXExport(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FBXExport, self).__init__(parent)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.setWindowTitle("Shifter's FBX Export")
        min_w = 300
        default_w = 400
        default_h = 1000
        self.setMinimumWidth(min_w)
        self.resize(default_w, default_h)

        self.create_actions()
        self.create_widgets()
        self.create_layout()
        self.create_connections()

        self.refresh_fbx_sdk_ui()
        self.refresh_ue_connection()

        self._settings = QtCore.QSettings(
            QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, 'mcsGear', 'mgearFbxExporter')
        self.restore_ui_state()

    def closeEvent(self, event):

        # make sure UI is stored, even if UI is launched without docking functionality
        self.save_ui_state()

        super(FBXExport, self).closeEvent(event)

    def dockCloseEventTriggered(self):
        super(FBXExport, self).dockCloseEventTriggered()

        self.save_ui_state()

    def create_actions(self):
        # file actions
        self.file_export_preset_action = QtWidgets.QAction("Export Shifter FBX Preset", self)
        self.file_export_preset_action.setIcon(pyqt.get_icon("mgear_log-out"))
        self.file_import_preset_action = QtWidgets.QAction("Import Shifter FBX Preset", self)
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
        self.geo_root_list.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
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
        self.joint_root_lineedit = QtWidgets.QLineEdit()
        self.joint_root_set_button = QtWidgets.QPushButton()
        self.joint_root_set_button.setIcon(pyqt.get_icon("mgear_mouse-pointer"))
        self.joint_root_auto_set_button = QtWidgets.QPushButton("Auto")
        self.joint_root_auto_set_button.setMaximumWidth(40)

        # settings
        self.settings_tab = QtWidgets.QTabWidget()

        self.settings_widget = QtWidgets.QWidget()
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
        self.settings_tab.addTab(self.settings_widget, "FBX Settings")

        # FBX SDK settings
        self.fbx_sdk_settings_widget = QtWidgets.QWidget()
        self.remove_namespace_checkbox = QtWidgets.QCheckBox("Remove Namespace")
        self.remove_namespace_checkbox.setChecked(True)
        self.clean_scene_checkbox = QtWidgets.QCheckBox("Joint and Geo Root Child of Scene Root + Clean Up Scene")
        self.clean_scene_checkbox.setChecked(True)
        self.settings_tab.addTab(self.fbx_sdk_settings_widget, "FBX SDK Settings")

        # path and filename
        self.file_path_label = QtWidgets.QLabel("Path")
        self.file_path_lineedit = QtWidgets.QLineEdit()
        self.file_path_set_button = widgets.create_button(icon="mgear_folder")

        self.file_name_label = QtWidgets.QLabel("File Name")
        self.file_name_lineedit = QtWidgets.QLineEdit()

        # export skeletalMesh settings
        self.export_geo_widget = QtWidgets.QWidget()
        self.skinning_checkbox = QtWidgets.QCheckBox("Skinning")
        self.skinning_checkbox.setChecked(True)
        self.blendshapes_checkbox = QtWidgets.QCheckBox("Blendshapes")
        self.blendshapes_checkbox.setChecked(True)
        self.use_partitions_checkbox = QtWidgets.QCheckBox("Use Partitions")
        self.use_partitions_checkbox.setChecked(True)
        self.skeletal_mesh_partitions_label = QtWidgets.QLabel("Partitions")
        self.skeletal_mesh_partitions_outliner = PartitionsTreeView()
        self.skeletal_mesh_partitions_outliner.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.skeletal_mesh_partition_add_button = QtWidgets.QPushButton()
        self.skeletal_mesh_partition_add_button.setIcon(pyqt.get_icon("mgear_plus"))
        self.skeletal_mesh_partition_remove_button = QtWidgets.QPushButton()
        self.skeletal_mesh_partition_remove_button.setIcon(pyqt.get_icon("mgear_minus"))
        self.export_skeletal_geo_button = QtWidgets.QPushButton("Export SkeletalMesh/SkinnedMesh")
        self.export_skeletal_geo_button.setStyleSheet("QPushButton {background:rgb(70, 100, 150); }")

        # export animation
        self.export_animation_widget = QtWidgets.QWidget()
        self.export_animations_button = QtWidgets.QPushButton("Export Animations")
        self.export_animations_button.setStyleSheet("QPushButton {background:rgb(150, 35, 50); }")
        self.animation_clips_list_widget = fuw.AnimClipsListWidget(parent=self)

        # Unreal Engine import
        # path and filename
        self.ue_file_path_label = QtWidgets.QLabel("Path")
        self.ue_file_path_lineedit = QtWidgets.QLineEdit()
        self.ue_file_path_set_button = widgets.create_button(icon="mgear_folder")

    def create_layout(self):

        # set source layout
        self.geo_root_layout = QtWidgets.QHBoxLayout()
        self.geo_root_layout.setContentsMargins(1, 1, 1, 1)
        self.geo_root_layout.addWidget(self.geo_root_list)
        self.geo_root_buttons_layout = QtWidgets.QVBoxLayout()
        self.geo_root_buttons_layout.setContentsMargins(1, 1, 1, 1)
        self.geo_root_buttons_layout.addWidget(self.geo_root_set_button)
        self.geo_root_buttons_layout.addWidget(self.geo_root_add_button)
        self.geo_root_buttons_layout.addWidget(self.geo_root_remove_button)
        self.geo_root_buttons_layout.addWidget(self.geo_root_auto_set_button)
        self.geo_root_buttons_layout.addStretch()
        self.geo_root_layout.addLayout(self.geo_root_buttons_layout)

        self.joint_root_layout = QtWidgets.QHBoxLayout()
        self.joint_root_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_layout.addWidget(self.joint_root_lineedit)
        self.joint_root_buttons_layout = QtWidgets.QHBoxLayout()
        self.joint_root_buttons_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_buttons_layout.addWidget(self.joint_root_set_button)
        self.joint_root_buttons_layout.addWidget(self.joint_root_auto_set_button)
        self.joint_root_layout.addLayout(self.joint_root_buttons_layout)

        self.set_source_layout = QtWidgets.QGridLayout()
        self.set_source_layout.addWidget(self.geo_root_label, 0, 0, QtCore.Qt.AlignRight)
        self.set_source_layout.addLayout(self.geo_root_layout, 0, 1)
        self.set_source_layout.addWidget(self.joint_root_label, 1, 0, QtCore.Qt.AlignRight)
        self.set_source_layout.addLayout(self.joint_root_layout, 1, 1)
        self.set_source_layout.setSpacing(2)

        self.set_source_collap_wgt = widgets.CollapsibleWidget("Set Source Elements")
        self.set_source_collap_wgt.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        self.set_source_collap_wgt.addLayout(self.set_source_layout)

        # settings layout
        self.settings_form_layout = QtWidgets.QFormLayout(self.settings_widget)
        self.settings_form_layout.addRow("Up Axis", self.up_axis_combobox)
        self.settings_form_layout.addRow("File Type", self.file_type_combobox)
        self.settings_form_layout.addRow("File Version", self.fbx_version_combobox)
        self.settings_form_layout.addRow("FBX Preset", self.fbx_export_presets_combobox)

        # FBX SDK settings
        if pfbx.FBX_SDK:
            title = "FBX SDK settings"
        else:
            title = "FBX SDK settings (Disable SDK Not Found)"

        self.sdk_settings_layout = QtWidgets.QVBoxLayout(self.fbx_sdk_settings_widget)
        self.sdk_settings_layout.addWidget(self.remove_namespace_checkbox)
        self.sdk_settings_layout.addWidget(self.clean_scene_checkbox)

        # general setting collapsible widget
        self.settings_collap_wgt = widgets.CollapsibleWidget("Settings")
        self.settings_collap_wgt.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        self.settings_collap_wgt.addWidget(self.settings_tab)

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

        # Unreal Engine import layout
        self.ue_import_collap_wgt = widgets.CollapsibleWidget("Unreal Engine Import")

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

        self.export_collap_wgt = widgets.CollapsibleWidget("Export")
        self.export_collap_wgt.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.MinimumExpanding)
        self.export_tab = QtWidgets.QTabWidget()
        self.export_collap_wgt.addWidget(self.export_tab)

        # export skeletalMesh layout
        self.export_geo_layout = QtWidgets.QVBoxLayout()
        self.export_geo_layout.setContentsMargins(1, 1, 1, 1)
        self.export_geo_widget.setLayout(self.export_geo_layout)
        self.model_deformers_groupbox = QtWidgets.QGroupBox("Deformers")
        self.model_deformers_layout = QtWidgets.QHBoxLayout(self.model_deformers_groupbox)
        self.model_deformers_layout.addWidget(self.skinning_checkbox)
        self.model_deformers_layout.addWidget(self.blendshapes_checkbox)
        self.model_deformers_layout.addWidget(self.use_partitions_checkbox)

        self.export_geo_layout.addWidget(self.model_deformers_groupbox)
        self.skeletal_mesh_partitions_label_layout = QtWidgets.QHBoxLayout()
        self.skeletal_mesh_partitions_label_layout.setContentsMargins(1, 1, 1, 1)
        self.skeletal_mesh_partitions_label_layout.addStretch()
        self.skeletal_mesh_partitions_label_layout.addWidget(self.skeletal_mesh_partitions_label)
        self.skeletal_mesh_partitions_label_layout.addStretch()
        self.skeletal_mesh_list_layout = QtWidgets.QHBoxLayout()
        self.skeletal_mesh_list_layout.setContentsMargins(1, 1, 1, 1)
        self.skeletal_mesh_partitions_buttons_layout = QtWidgets.QVBoxLayout()
        self.skeletal_mesh_partitions_buttons_layout.setContentsMargins(1, 1, 1, 1)
        self.skeletal_mesh_partitions_buttons_layout.addWidget(self.skeletal_mesh_partition_add_button)
        self.skeletal_mesh_partitions_buttons_layout.addWidget(self.skeletal_mesh_partition_remove_button)
        self.skeletal_mesh_partitions_buttons_layout.addStretch()
        self.skeletal_mesh_list_layout.addWidget(self.skeletal_mesh_partitions_outliner)
        self.skeletal_mesh_list_layout.addLayout(self.skeletal_mesh_partitions_buttons_layout)
        self.export_geo_layout.addLayout(self.skeletal_mesh_partitions_label_layout)
        self.export_geo_layout.addLayout(self.skeletal_mesh_list_layout)
        self.export_geo_layout.addWidget(self.export_skeletal_geo_button)
        self.export_tab.addTab(self.export_geo_widget, "Skeletal Mesh")

        # export Animation layout
        self.export_animation_layout = QtWidgets.QVBoxLayout()
        self.export_animation_layout.setContentsMargins(1, 1, 1, 1)
        self.export_animation_widget.setLayout(self.export_animation_layout)
        self.export_animation_layout.addWidget(self.animation_clips_list_widget)
        self.export_animation_buttons_layout = QtWidgets.QHBoxLayout()
        self.export_animation_buttons_layout.addWidget(self.export_animations_button)
        self.export_animation_layout.addLayout(self.export_animation_buttons_layout)
        self.export_tab.addTab(self.export_animation_widget, "Animation")

        # TODO: Remove this line
        self.export_tab.setCurrentIndex(1)

        # Scroll Area layout
        self.base_scrollarea_wgt = QtWidgets.QWidget()

        self.scrollarea_layout = QtWidgets.QVBoxLayout(self.base_scrollarea_wgt)
        self.scrollarea_layout.setContentsMargins(2, 2, 2, 2)
        self.scrollarea_layout.setSpacing(2)
        self.scrollarea_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scrollarea_layout.addWidget(self.set_source_collap_wgt)
        self.scrollarea_layout.addWidget(self.settings_collap_wgt)
        self.scrollarea_layout.addWidget(self.file_path_collap_wgt)
        self.scrollarea_layout.addWidget(self.ue_import_collap_wgt)
        self.scrollarea_layout.addWidget(self.export_collap_wgt)

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
                self.set_line_edit_text_from_sel,
                self.joint_root_lineedit,
                "joint",
            )
        )
        self.joint_root_auto_set_button.clicked.connect(partial(self.auto_set_joint_root))
        self.file_name_lineedit.textChanged.connect(self.normalize_name)
        self.file_path_set_button.clicked.connect(self.set_folder_path)
        self.export_skeletal_geo_button.clicked.connect(self.export_skeletal_mesh)

        self.ue_file_path_set_button.clicked.connect(self.set_ue_folder_path)
        self.use_partitions_checkbox.toggled.connect(self.set_use_partitions)
        self.skeletal_mesh_partition_add_button.clicked.connect(self.add_skeletal_mesh_partition)
        self.skeletal_mesh_partition_remove_button.clicked.connect(self.remove_skeletal_mesh_partition)
        self.skeletal_mesh_partitions_outliner.itemEnabledChanged.connect(self.partition_item_enabled_changed)
        self.skeletal_mesh_partitions_outliner.itemAddNode.connect(self.partition_item_add_skeletal_mesh)
        self.skeletal_mesh_partitions_outliner.itemRenamed.connect(self.partition_item_renamed)
        self.skeletal_mesh_partitions_outliner.itemRemoved.connect(self.partition_skeletal_mesh_removed)
        self.skeletal_mesh_partitions_outliner.droppedItems.connect(self.partition_items_dropped)

        self.export_animations_button.clicked.connect(self.export_animation_clips)

    # functions

    def get_root_joint(self):
        root_joint = self.joint_root_lineedit.text().split(",")
        return root_joint[0] if root_joint else None

    def get_export_path(self):
        return self.file_path_lineedit.text()

    def get_file_name(self):
        return self.file_name_lineedit.text()

    def get_remove_namespace(self):
        return self.remove_namespace_checkbox.isChecked()

    def get_scene_clean(self):
        return self.clean_scene_checkbox.isChecked()

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
        for fbx_import_file_path in fbx_import_file_paths:
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
        self.use_partitions_checkbox.setEnabled(pfbx.FBX_SDK)
        self.set_use_partitions(self.use_partitions_checkbox.isChecked())

        fbx_sdk_path = pfbx.get_fbx_sdk_path()
        if not fbx_sdk_path or not os.path.isdir(fbx_sdk_path):
            self.fbx_sdk_path_action.setText("Python FBX SDK: Not set")
        else:
            self.fbx_sdk_path_action.setText("Python FBX SDK: {}".format(fbx_sdk_path))

    def refresh_ue_connection(self):
        # is_available = bool(uegear.content_project_directory())
        is_available = False
        self.ue_import_collap_wgt.setEnabled(is_available)
        if not is_available:
            cmds.warning('Unreal Engine Import functionality not available. Run Unreal Engine and load ueGear plugin.')
            self.ue_import_cbx.setChecked(False)

    def update_settings(self):

        # Function that can be used to update settings file before loading them.
        # Useful in case we change the way UI settings are stored, so we can update old setting files.

        pass

    def save_ui_state(self):
        if not self._settings:
            return False

        self._settings.beginGroup('settings')
        self._settings.setValue('up axis', self.up_axis_combobox.currentText())
        self._settings.setValue('file type', self.file_type_combobox.currentText())
        self._settings.setValue('fbx version', self.fbx_version_combobox.currentText())
        self._settings.setValue('export preset', self.fbx_export_presets_combobox.currentText())
        self._settings.endGroup()

        self._settings.beginGroup('sdk settings')
        self._settings.setValue('remove namespace', self.remove_namespace_checkbox.isChecked())
        self._settings.setValue('clean up scene', self.clean_scene_checkbox.isChecked())
        self._settings.endGroup()

        self._settings.beginGroup('file path')
        self._settings.setValue('path', self.file_path_lineedit.text())
        self._settings.setValue('file name', self.file_name_lineedit.text())
        self._settings.endGroup()

        self._settings.beginGroup('unreal engine')
        self._settings.setValue('enable', self.ue_import_cbx.isChecked())
        self._settings.setValue('path', self.ue_file_path_lineedit.text())
        self._settings.endGroup()

        self._settings.beginGroup('export')
        self._settings.setValue('skeletal mesh/skinning', self.skinning_checkbox.isChecked())
        self._settings.setValue('skeletal mesh/blendshapes', self.blendshapes_checkbox.isChecked())
        self._settings.setValue('skeletal mesh/use partitions', self.use_partitions_checkbox.isChecked())
        self._settings.endGroup()

        return True

    def restore_ui_state(self):
        if not self._settings:
            return False

        self.update_settings()

        self.up_axis_combobox.setCurrentText(self._settings.value('settings/up axis', '', str))
        self.file_type_combobox.setCurrentText(self._settings.value('settings/file type', '', str))
        self.fbx_version_combobox.setCurrentText(self._settings.value('settings/fbx version', '', str))
        self.fbx_export_presets_combobox.setCurrentText(self._settings.value('settings/export preset', str))

        self.remove_namespace_checkbox.setChecked(self._settings.value('sdk settings/remove namespace', True, bool))
        self.clean_scene_checkbox.setChecked(self._settings.value('sdk settings/clean up scene', True, bool))

        self.file_path_lineedit.setText(self._settings.value('file path/path', '', str))
        self.file_name_lineedit.setText(self._settings.value('file path/file name', '', str))

        self.ue_import_cbx.setChecked(self._settings.value('unreal engine/enable', False, bool))
        self.ue_file_path_lineedit.setText(self._settings.value('unreal engine/path', '', str))

        self.skinning_checkbox.setChecked(self._settings.value('export/skeletal mesh/skinning', True, bool))
        self.blendshapes_checkbox.setChecked(self._settings.value('export/skeletal mesh/blendshapes', True, bool))
        self.use_partitions_checkbox.setChecked(self._settings.value('export/skeletal mesh/use partitions', True, bool))

        return True

    def set_ue_folder_path(self):
        content_folder = uegear.content_project_directory()
        folder_path = cmds.fileDialog2(fileMode=3, startingDirectory=content_folder)
        if folder_path:
            self.ue_file_path_lineedit.setText(string.normalize_path(folder_path[0]))

    def set_use_partitions(self, flag):
        self.skeletal_mesh_partitions_outliner.setEnabled(flag)
        self.skeletal_mesh_partitions_label.setEnabled(flag)
        self.skeletal_mesh_partition_add_button.setEnabled(flag)
        self.skeletal_mesh_partition_remove_button.setEnabled(flag)

    def add_skeletal_mesh_partition(self):

        export_node = fu.FbxExportNode.get() or fu.FbxExportNode.create()
        name, ok = QtWidgets.QInputDialog.getText(
            self, 'New Partition', 'New Partition', QtWidgets.QLineEdit.Normal, 'New Partition')
        if not ok or not name:
            return
        result = export_node.add_new_skeletal_mesh_partition(name, list())
        if not result:
            return

        self.skeletal_mesh_partitions_outliner.reset_contents()

    def remove_skeletal_mesh_partition(self):

        selected_partition_items = self.skeletal_mesh_partitions_outliner.selectedItems()
        if not selected_partition_items:
            return

        for selected_partition_item in selected_partition_items:
            if selected_partition_item.node.is_master:
                return

        response = cmds.confirmDialog(
            title='Confirm', message='Confirm Deletion',
            button=['Yes', 'No'], defaultButton='Yes', cancelButton='No', dismissString='No')
        if response == 'Yes':
            for selected_partition_item in selected_partition_items:
                selected_partition_item.delete_node()

    def partition_item_enabled_changed(self, item):

        if not item:
            return

        export_node = fu.FbxExportNode.get()
        if not export_node:
            return

        export_node.set_partition_enabled(item.node.node_name, item.is_enabled())

    def partition_item_add_skeletal_mesh(self, item):

        if not item:
            return

        export_node = fu.FbxExportNode.get()
        if not export_node:
            return

        transforms = cmds.ls(sl=True, long=True, type='transform')
        meshes = [child for child in transforms if cmds.listRelatives(child, shapes=True)]

        export_node.add_skeletal_meshes_to_partition(item.node.node_name, meshes)

        self.skeletal_mesh_partitions_outliner.reset_contents()

    def partition_item_renamed(self, old_name, new_name):

        if not old_name or not new_name or old_name == new_name:
            return

        export_node = fu.FbxExportNode.get()
        if not export_node:
            return

        export_node.set_partition_name(old_name, new_name)

    def partition_skeletal_mesh_removed(self, parent_name, removed_name):

        if not parent_name or not removed_name:
            return

        export_node = fu.FbxExportNode.get()
        if not export_node:
            return

        export_node.delete_skeletal_mesh_from_partition(parent_name, removed_name)

        self.skeletal_mesh_partitions_outliner.reset_contents()

    def partition_items_dropped(self, parent_item, dropped_items, duplicate=False):

        if not parent_item or not dropped_items:
            return

        export_node = fu.FbxExportNode.get()
        if not export_node:
            return

        valid_items = [item for item in dropped_items if item.is_master]
        if not valid_items:
            return

        if not duplicate:
            # remove items from their old partitions
            for item in valid_items:
                export_node.delete_skeletal_mesh_from_partition(item.parent().node.node_name, item.node.node_name)

        # add items to new partition
        meshes_names = [item.node.node_name for item in valid_items]
        export_node.add_skeletal_meshes_to_partition(parent_item.node.node_name, meshes_names)

    def export_skeletal_mesh(self):

        print('----- Exporting Skeletal Meshes -----')

        geo_roots = [self.geo_root_list.item(i).text() for i in range(self.geo_root_list.count())]
        if not geo_roots:
            cmds.warning('No geo roots defined!')
            return False
        jnt_root = self.joint_root_lineedit.text().split(",")
        if not jnt_root[0]:
            cmds.warning('No Joint Root defined!')
            return False
        print('\t>>> Geo Roots: {}'.format(geo_roots))
        print('\t>>> Joint Root: {}'.format(jnt_root))

        self.auto_file_path()
        file_path = self.file_path_lineedit.text()
        file_name = self.file_name_lineedit.text()
        if not file_path or not file_name:
            cmds.warning('Not valid file path and name defined!')
            return False

        partitions = dict()
        use_partitions = self.use_partitions_checkbox.isChecked()
        if use_partitions:

            # Master partition data is retrieved from UI
            # TODO: Should we store master data within FbxExporterNode too?
            master_partition = self.skeletal_mesh_partitions_outliner.get_master_partition()

            export_nodes = fu.FbxExportNode.find()
            if not export_nodes:
                cmds.warning('No export nodes found within scene!')
                return False
            if len(export_nodes) > 2:
                cmds.warning(
                    'Multiple FBX Export nodes found in scene. Using first one found: "{}"'.format(export_nodes[0]))
            found_partitions = dict()
            found_partitions.update(master_partition)
            found_partitions.update(export_nodes[0].get_partitions())
            for partition_name, partition_data in found_partitions.items():
                enabled = partition_data.get('enabled', True)
                skeletal_meshes = partition_data.get('skeletalMeshes', list())
                if not enabled or not skeletal_meshes:
                    continue
                partitions[partition_name] = skeletal_meshes
            print('\t>>> Partitions: {}'.format(partitions))

        current_export_preset = self.fbx_export_presets_combobox.currentText()
        preset_file_path = ''
        if current_export_preset and current_export_preset != 'User defined':
            preset_file_path = self.fbx_export_presets_combobox.itemData(
                self.fbx_export_presets_combobox.currentIndex())
        print('\t>>> Preset File Path: {}'.format(preset_file_path))

        # retrieve export config
        export_config = {
            'up_axis': self.up_axis_combobox.currentText(),
            'file_type': self.file_type_combobox.currentText(),
            'fbx_version': self.fbx_version_combobox.currentText(),
            'remove_namespace': self.remove_namespace_checkbox.isChecked(),
            'scene_clean': self.clean_scene_checkbox.isChecked(),
            'use_partitions': use_partitions,
            'file_name': file_name,
            'file_path': file_path,
            'skinning': self.skinning_checkbox.isChecked(),
            'blendshapes': self.blendshapes_checkbox.isChecked(),
            'partitions': partitions
        }

        result = fu.export_skeletal_mesh(
            jnt_root,
            geo_roots,
            **export_config
        )
        if not result:
            cmds.warning('Something went wrong while exporting Skeletal Mesh/es')
            return False

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
        #         cmds.warning('Was not possible to export asset: {}. Please check Unreal Engine Output Log'.format(
        #             asset_name))

        return True

    def export_animation_clips(self):

        print('----- Exporting Animation Clips -----')

        jnt_root = self.joint_root_lineedit.text().split(',')
        if not jnt_root[0]:
            cmds.warning('No Joint Root defined')
            return False
        jnt_root = jnt_root[0]
        print('\t>>> Joint Root: {}'.format(jnt_root))

        self.auto_file_path()
        file_path = self.file_path_lineedit.text()
        file_name = self.file_name_lineedit.text()
        if not file_path or not file_name:
            cmds.warning('Not valid file path and name defined!')
            return False

        current_export_preset = self.fbx_export_presets_combobox.currentText()
        preset_file_path = ''
        if current_export_preset and current_export_preset != 'User defined':
            preset_file_path = self.fbx_export_presets_combobox.itemData(
                self.fbx_export_presets_combobox.currentIndex())
        print('\t>>> Preset File Path: {}'.format(preset_file_path))

        export_nodes = fu.FbxExportNode.find()
        if not export_nodes:
            return False
        if len(export_nodes) > 2:
            cmds.warning(
                'Multiple FBX Export nodes found in scene. Using first one found: "{}"'.format(export_nodes[0]))
        export_node = export_nodes[0]

        # retrieve export config
        base_export_config = {
            'up_axis': self.up_axis_combobox.currentText(),
            'file_type': self.file_type_combobox.currentText(),
            'fbx_version': self.fbx_version_combobox.currentText(),
            'remove_namespace': self.remove_namespace_checkbox.isChecked(),
            'scene_clean': self.clean_scene_checkbox.isChecked(),
            'file_name': file_name,
            'file_path': file_path,
        }

        for anim_clip_data in export_node.get_animation_clips(jnt_root):
            anim_clip_export_data = base_export_config.copy()
            anim_clip_export_data.update(anim_clip_data)
            fu.export_animation_clip(jnt_root, **anim_clip_export_data)

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

        self.skeletal_mesh_partitions_outliner.set_geo_roots(
            [self.geo_root_list.item(i).text() for i in range(self.geo_root_list.count())])

    def auto_set_joint_root(self):
        j_roots = fu.get_joint_root() or list()
        if j_roots:
            joint_name = j_roots[0].name()
            self.joint_root_lineedit.setText(joint_name)
            self.animation_clips_list_widget.refresh()

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
            return filter_sel

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

    def set_line_edit_text_from_sel(self, lieneedit, type_filter):
        """Set line edit text from selected element filtered by type

        Args:
            lieneedit (QLineEdit): QT line edit object
            type_filter (str): Type to filter: for example "joint"
                               or "transform"
        """
        text = self.filter_sel_by_type(type_filter)
        if text:
            lieneedit.setText(text)
        if type_filter == 'joint':
            self.animation_clips_list_widget.refresh(text)

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

        if listwidget == self.geo_root_list:
            self.skeletal_mesh_partitions_outliner.set_geo_roots(
                [listwidget.item(i).text() for i in range(listwidget.count())])

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

        if listwidget == self.geo_root_list:
            self.skeletal_mesh_partitions_outliner.set_geo_roots(
                [listwidget.item(i).text() for i in range(listwidget.count())])

    def remove_list_items_from_sel(self, listwidget):
        """Removes list widget items from selected list items

        Args:
            listwidget (QListWidget): QT line list widget object
        """

        selected_items = listwidget.selectedItems()
        for selected_item in selected_items:
            listwidget.takeItem(listwidget.row(selected_item))

        if listwidget == self.geo_root_list:
            self.skeletal_mesh_partitions_outliner.set_geo_roots(
                [listwidget.item(i).text() for i in range(listwidget.count())])


class PartitionNodeClass(fuw.NodeClass):
    def __init__(self, node_name, node_type, is_root, icon, enabled, network_enabled, is_master=False):
        super(PartitionNodeClass, self).__init__(
            node_name=node_name, node_type=node_type, is_root=is_root, icon=icon, enabled=enabled,
            network_enabled=network_enabled)

        self._is_master = is_master

    @property
    def is_master(self):
        return self._is_master

    @is_master.setter
    def is_master(self, flag):
        self._is_master = flag


class PartitionTreeItem(fuw.TreeItem):

    def __init__(self, node, header, show_enabled, parent=None):
        super(PartitionTreeItem, self).__init__(node=node, header=header, show_enabled=show_enabled, parent=parent)

    def is_master(self):
        return self.node.is_master


class PartitionsTreeView(fuw.OutlinerTreeView):

    NODE_CLASS = PartitionNodeClass
    TREE_ITEM_CLASS = PartitionTreeItem

    def __init__(self, parent=None):

        self._master_item = None
        self._geo_roots = list()

        super(PartitionsTreeView, self).__init__(parent=parent)

    def mouseDoubleClickEvent(self, event):

        if event.button() == QtCore.Qt.LeftButton:
            index = self.indexAt(event.pos())
            if index.row() == -1:
                self._action_button_pressed = False
                super(PartitionsTreeView, self).mousePressEvent(event)
                self.clearSelection()
                self.window().repaint()
                return
            item = self._get_corresponding_item(index)
            if item and not item.is_root():
                cmds.select(item.get_name())

        super(PartitionsTreeView, self).mouseDoubleClickEvent(event)

    def can_be_dropped(self, index):

        valid = super(PartitionsTreeView, self).can_be_dropped(index)
        if not valid:
            return valid

        # only root nodes can accept drop events
        item = self.itemFromIndex(index)
        return False if not item.is_master else True

    def set_geo_roots(self, geo_roots):
        self._geo_roots = geo_roots
        self.reset_contents()

    def get_master_partition(self):
        master_partition = dict()
        master_partition['Master'] = {'enabled': True, 'skeletalMeshes': []}
        if not self._master_item:
            return master_partition

        for i in range(self._master_item.childCount()):
            item = self._master_item.child(i)
            master_partition['Master']['skeletalMeshes'].append(item.get_name())

        return master_partition

    def find_items(self):

        export_nodes = fu.FbxExportNode.find()
        if not export_nodes:
            return dict()
        if len(export_nodes) > 2:
            cmds.warning('Multiple FBX Export nodes found in scene. Using first one found: "{}"'.format(export_nodes[0]))

        return export_nodes[0].get_partitions()

    def populate_items(self, add_callbacks=True):

        if add_callbacks:
            self.cleanup()

        self._master_item = self._create_master_root_item()
        self._master_item.setFlags(self._master_item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDropEnabled)
        self._master_item.setFlags(self._master_item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
        self.addTopLevelItem(self._master_item)

        all_items = self.find_items()

        for item_name, item_data in all_items.items():
            root_item = self._create_root_item(item_name)
            root_item.setFlags(root_item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDropEnabled)
            root_item.setFlags(root_item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
            self.addTopLevelItem(root_item)
            child_items = item_data.get('skeletalMeshes', list())
            for child_node in child_items:
                child = self._add_partition_item(child_node, root_item)
                child.setFlags(child.flags() | QtCore.Qt.ItemIsEditable)
                child.setFlags(child.flags() & ~QtCore.Qt.ItemIsDropEnabled)
                root_item.addChild(child)
                if add_callbacks:
                    pass
            enabled = item_data.get('enabled', True)
            color = item_data.get('color', None)
            if not enabled:
                root_item.set_enabled()
            if color is not None:
                root_item.set_label_color(color)

        self._update_master_partition()

    def _on_custom_context_menu_requested(self, pos):

        item = self._get_current_item()
        if not item or item.is_master():
            return

        super(PartitionsTreeView, self)._on_custom_context_menu_requested(pos)

    def _create_master_root_item(self):

        node_icon = pyqt.get_icon('mgear_package')
        root_node = self.NODE_CLASS('Master', 'Root', True, node_icon, True, True, is_master=True)
        root_node.can_be_disabled = False
        root_node.can_be_deleted = False
        root_node.can_add_children = False
        root_node.can_be_duplicated = False

        item = self.TREE_ITEM_CLASS(root_node, 'Master', True, parent=self)

        return item

    def _add_master_partition_item(self, node, partition_item):

        node_icon = pyqt.get_icon('mgear_box')
        item_node = self.NODE_CLASS(node, 'Geometry', False, node_icon, True, partition_item.node.network_enabled)
        item_node.can_be_disabled = False
        item_node.can_be_deleted = False

        item = self.TREE_ITEM_CLASS(item_node, '', True, partition_item)

        return item

    def _update_master_partition(self):
        if not self._master_item or not self._geo_roots:
            return

        found_meshes = list()
        for geo_root in self._geo_roots:
            children = cmds.listRelatives(geo_root, allDescendents=True, fullPath=True, type='transform') or list()
            meshes = [child for child in children if cmds.listRelatives(child, shapes=True) or list()]
            found_meshes.extend(meshes)
        if not found_meshes:
            return

        partition_meshes = list()
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if not item or item == self._master_item:
                continue
            for j in range(item.childCount()):
                child = item.child(j)
                partition_meshes.append(child.get_name())

        for found_mesh in found_meshes:
            if found_mesh in partition_meshes:
                continue
            child = self._add_master_partition_item(found_mesh, self._master_item)
            child.setFlags(child.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDropEnabled)
            self._master_item.addChild(child)


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
