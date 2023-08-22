import os
import timeit
import importlib
from functools import partial

import maya.cmds as cmds
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from mgear.vendor.Qt import QtWidgets, QtCore
from mgear.core import (
    pyqt,
    pyFBX as pfbx,
    string,
    widget_settings_manager,
    widgets
)
from mgear.shifter.game_tools_fbx import (
    fbx_export_node,
    partitions_outliner,
    utils,
    widgets as fbx_widgets
)
from mgear.uegear import commands as uegear


WIDGET_SETTINGS = widget_settings_manager.WidgetSettingsManager("FbxExporter")


class FBXExporter(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FBXExporter, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Shifter's FBX Export")
        min_w = 300
        default_w = 400
        default_h = 1000
        self.setMinimumWidth(min_w)
        self.resize(default_w, default_h)

        self.create_layout()
        self.create_connections()
        self.refresh_fbx_sdk_ui()
        self.refresh_ue_connection()

        WIDGET_SETTINGS.load_ui_state(self.widget_dict)
        self._update_geo_root_data()

    def closeEvent(self, event):
        # make sure UI is stored, even if UI is launched without docking functionality
        WIDGET_SETTINGS.save_ui_state(self.widget_dict)
        super(FBXExporter, self).closeEvent(event)

    def dockCloseEventTriggered(self):
        super(FBXExporter, self).dockCloseEventTriggered()
        WIDGET_SETTINGS.save_ui_state(self.widget_dict)
    
    def create_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)

        self.create_menu_bar()
        self.create_source_elements_widget()
        self.create_settings_widget()
        self.create_file_path_widget()
        self.create_unreal_import_widget()
        self.create_export_widget()

        self.widget_dict = {
            "geo root": self.geo_root_list,
            "joint root": self.joint_root_lineedit,
            "up axis": self.up_axis_combobox,
            "file type": self.file_type_combobox,
            "fbx version": self.fbx_version_combobox,
            "fbx export preset": self.fbx_export_presets_combobox,
            "remove namespace": self.remove_namespace_checkbox,
            "clean up scene": self.clean_scene_checkbox,
            "file path": self.file_path_lineedit,
            "file name": self.file_name_lineedit,
            "ue enable": self.ue_import_cbx,
            "ue file path": self.ue_file_path_lineedit,
            "skinning": self.skinning_checkbox,
            "blendshapes": self.blendshapes_checkbox,
            "partitions": self.partitions_checkbox
        }

    def create_menu_bar(self):
        # menu bar
        self.menu_bar = QtWidgets.QMenuBar()
        self.main_layout.setMenuBar(self.menu_bar)

        # file actions
        self.file_menu = self.menu_bar.addMenu("File")
        self.file_export_preset_action = QtWidgets.QAction(
            "Export Shifter FBX Preset", self
        )
        self.file_export_preset_action.setIcon(pyqt.get_icon("mgear_log-out"))
        self.file_import_preset_action = QtWidgets.QAction(
            "Import Shifter FBX Preset", self
        )
        self.file_import_preset_action.setIcon(pyqt.get_icon("mgear_log-in"))
        self.file_menu.addAction(self.file_export_preset_action)
        self.file_menu.addAction(self.file_import_preset_action)

        # fbx sdk actions
        self.fbx_sdk_menu = self.menu_bar.addMenu("FBX SDK")
        self.set_fbx_sdk_path_action = QtWidgets.QAction(
            "Set Python FBX SDK", self
        )
        self.fbx_sdk_path_action = QtWidgets.QAction(
            "Python FBX SDK Path: Not set", self
        )
        self.fbx_sdk_path_action.setEnabled(False)
        self.fbx_sdk_menu.addAction(self.set_fbx_sdk_path_action)
        self.fbx_sdk_menu.addAction(self.fbx_sdk_path_action)

        # ueGear actions
        self.uegear_menu = self.menu_bar.addMenu("ueGear")
        self.refresh_uegear_connection_action = QtWidgets.QAction(
            "Refresh Unreal Engine Connection", self
        )
        self.refresh_uegear_connection_action.setIcon(
            pyqt.get_icon("mgear_refresh-cw")
        )
        self.uegear_menu.addAction(self.refresh_uegear_connection_action)

    def create_source_elements_widget(self):
        def create_button(layout, label="", icon=None, max_width=40,
                          max_height=20):
            button = QtWidgets.QPushButton(label)
            button.setMaximumSize(max_width, max_height)
            if icon:
                button.setIcon(pyqt.get_icon(icon))
            layout.addWidget(button)
            return button

        # main collapsible widget layout
        source_collap_wgt = widgets.CollapsibleWidget("Source Elements")
        source_collap_wgt.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                        QtWidgets.QSizePolicy.Maximum)
        self.main_layout.addWidget(source_collap_wgt)

        source_layout = QtWidgets.QGridLayout()
        source_layout.setSpacing(2)
        source_collap_wgt.addLayout(source_layout)

        # geo root layout
        geo_layout = QtWidgets.QVBoxLayout()
        source_layout.addLayout(geo_layout, 0, 0)

        geo_label = QtWidgets.QLabel("Geo Root")
        geo_layout.addWidget(geo_label)
        self.geo_root_list = QtWidgets.QListWidget()
        self.geo_root_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                         QtWidgets.QSizePolicy.MinimumExpanding)
        self.geo_root_list.setSelectionMode(QtWidgets.QListWidget.ExtendedSelection)
        geo_layout.addWidget(self.geo_root_list)

        geo_buttons_layout = QtWidgets.QVBoxLayout()
        source_layout.addLayout(geo_buttons_layout, 0, 1)

        geo_buttons_layout.addStretch()
        self.geo_set_btn = create_button(geo_buttons_layout,
                                         icon="mgear_mouse-pointer")
        self.geo_add_btn = create_button(geo_buttons_layout,
                                         icon="mgear_plus")
        self.geo_rem_btn = create_button(geo_buttons_layout,
                                         icon="mgear_minus")
        self.geo_auto_set_btn = create_button(geo_buttons_layout,
                                              label="Auto")
        geo_buttons_layout.addStretch()

        # joint root layout
        joint_layout = QtWidgets.QVBoxLayout()
        source_layout.addLayout(joint_layout, 1, 0)

        joint_label = QtWidgets.QLabel("Joint Root")
        joint_layout.addWidget(joint_label)
        self.joint_root_lineedit = QtWidgets.QLineEdit()
        joint_layout.addWidget(self.joint_root_lineedit)

        joint_buttons_layout = QtWidgets.QVBoxLayout()
        source_layout.addLayout(joint_buttons_layout, 1, 1)
        self.joint_set_btn = create_button(joint_buttons_layout,
                                           icon="mgear_mouse-pointer")
        self.joint_auto_set_btn = create_button(joint_buttons_layout,
                                                label="Auto")


    def create_settings_widget(self):
        # main collapsible widget layout
        settings_collap_wgt = widgets.CollapsibleWidget("Settings")
        settings_collap_wgt.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
        self.main_layout.addWidget(settings_collap_wgt)
        settings_tab = QtWidgets.QTabWidget()
        settings_collap_wgt.addWidget(settings_tab)

        # fbx settings tab
        fbx_tab = QtWidgets.QWidget()
        settings_tab.addTab(fbx_tab, "FBX")

        self.up_axis_combobox = QtWidgets.QComboBox()
        self.up_axis_combobox.addItems(["Y", "Z"])
        self.file_type_combobox = QtWidgets.QComboBox()
        self.file_type_combobox.addItems(["Binary", "ASCII"])
        self.fbx_version_combobox = QtWidgets.QComboBox()
        self.fbx_version_combobox.addItems(pfbx.get_fbx_versions())
        self.fbx_export_presets_combobox = QtWidgets.QComboBox()
        self.populate_fbx_presets_combobox(
            self.fbx_export_presets_combobox, pfbx.get_fbx_export_presets()
        )
        self.settings_form_layout = QtWidgets.QFormLayout(fbx_tab)
        self.settings_form_layout.addRow("Up Axis", self.up_axis_combobox)
        self.settings_form_layout.addRow("File Type", self.file_type_combobox)
        self.settings_form_layout.addRow(
            "File Version", self.fbx_version_combobox
        )
        self.settings_form_layout.addRow(
            "FBX Preset", self.fbx_export_presets_combobox
        )

        # fbx sdk settings tab
        fbx_sdk_tab = QtWidgets.QWidget()
        settings_tab.addTab(fbx_sdk_tab, "FBX SDK")
        fbx_sdk_layout = QtWidgets.QVBoxLayout(fbx_sdk_tab)

        self.remove_namespace_checkbox = QtWidgets.QCheckBox("Remove Namespace")
        self.remove_namespace_checkbox.setChecked(True)
        self.clean_scene_checkbox = QtWidgets.QCheckBox(
            "Joint and Geo Root Child of Scene Root + Clean Up Scene")
        self.clean_scene_checkbox.setChecked(True)
        fbx_sdk_layout.addWidget(self.remove_namespace_checkbox)
        fbx_sdk_layout.addWidget(self.clean_scene_checkbox)

    def create_file_path_widget(self):
        # main collapsible widget layout
        file_path_collap_wgt = widgets.CollapsibleWidget("File Path")
        self.main_layout.addWidget(file_path_collap_wgt)
        self.path_layout = QtWidgets.QVBoxLayout()
        self.path_layout.setSpacing(2)
        file_path_collap_wgt.addLayout(self.path_layout)

        # export path
        self.file_path_layout = QtWidgets.QHBoxLayout()
        self.file_path_layout.setContentsMargins(1, 1, 1, 1)
        self.path_layout.addLayout(self.file_path_layout)

        file_path_label = QtWidgets.QLabel("Path")
        self.file_path_lineedit = QtWidgets.QLineEdit()
        self.file_set_btn = widgets.create_button(icon="mgear_folder")
        self.file_path_layout.addWidget(file_path_label)
        self.file_path_layout.addWidget(self.file_path_lineedit)
        self.file_path_layout.addWidget(self.file_set_btn)

        # export file name
        self.file_name_layout = QtWidgets.QHBoxLayout()
        self.file_name_layout.setContentsMargins(1, 1, 1, 1)
        self.path_layout.addLayout(self.file_name_layout)

        file_name_label = QtWidgets.QLabel("File Name")
        self.file_name_lineedit = QtWidgets.QLineEdit()
        self.file_name_layout.addWidget(file_name_label)
        self.file_name_layout.addWidget(self.file_name_lineedit)

    def create_unreal_import_widget(self):
        self.ue_import_collap_wgt = widgets.CollapsibleWidget("Unreal Engine Import")
        self.main_layout.addWidget(self.ue_import_collap_wgt)
        self.ue_path_layout = QtWidgets.QVBoxLayout()
        self.ue_path_layout.addSpacing(2)
        self.ue_import_collap_wgt.addLayout(self.ue_path_layout)

        self.ue_import_cbx = QtWidgets.QCheckBox("Enable Unreal Engine Import?")
        self.ue_import_collap_wgt.addWidget(self.ue_import_cbx)

        self.ue_file_path_layout = QtWidgets.QHBoxLayout()
        self.ue_file_path_layout.setContentsMargins(1, 1, 1, 1)
        self.ue_path_layout.addLayout(self.ue_file_path_layout)

        self.ue_file_path_label = QtWidgets.QLabel("Path")
        self.ue_file_path_lineedit = QtWidgets.QLineEdit()
        self.ue_file_set_btn = widgets.create_button(icon="mgear_folder")
        self.ue_file_path_layout.addWidget(self.ue_file_path_lineedit)
        self.ue_file_path_layout.addWidget(self.ue_file_path_label)
        self.ue_file_path_layout.addWidget(self.ue_file_set_btn)

    def create_export_widget(self):
        export_collap_wgt = widgets.CollapsibleWidget("Export")
        export_collap_wgt.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.main_layout.addWidget(export_collap_wgt)
        
        self.export_tab = QtWidgets.QTabWidget()
        export_collap_wgt.addWidget(self.export_tab)

        self.create_skeletal_mesh_tab()
        self.create_animation_tab()

    def create_skeletal_mesh_tab(self):
        # main collapsible widget layout
        skeletal_mesh_tab = QtWidgets.QWidget()
        self.export_tab.addTab(skeletal_mesh_tab, "Skeletal Mesh")
        skeletal_mesh_layout = QtWidgets.QVBoxLayout(skeletal_mesh_tab)

        # deformers options
        deformers_label = QtWidgets.QLabel("Deformers")
        skeletal_mesh_layout.addWidget(deformers_label)

        deformers_layout = QtWidgets.QHBoxLayout()
        skeletal_mesh_layout.addLayout(deformers_layout)

        self.skinning_checkbox = QtWidgets.QCheckBox("Skinning")
        self.skinning_checkbox.setChecked(True)
        self.blendshapes_checkbox = QtWidgets.QCheckBox("Blendshapes")
        self.blendshapes_checkbox.setChecked(True)
        self.partitions_checkbox = QtWidgets.QCheckBox("Partitions")
        self.partitions_checkbox.setChecked(True)
        deformers_layout.addWidget(self.skinning_checkbox)
        deformers_layout.addWidget(self.blendshapes_checkbox)
        deformers_layout.addWidget(self.partitions_checkbox)

        # partitions layout
        self.partitions_label = QtWidgets.QLabel("Partitions")
        skeletal_mesh_layout.addWidget(self.partitions_label)
        partitions_layout = QtWidgets.QHBoxLayout()
        skeletal_mesh_layout.addLayout(partitions_layout)

        # partitions outliner
        self.partitions_outliner = partitions_outliner.PartitionsOutliner()
        self.partitions_outliner.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding)
        partitions_layout.addWidget(self.partitions_outliner)

        # partition buttons
        partition_buttons_layout = QtWidgets.QVBoxLayout()
        partition_buttons_layout.addStretch()
        partitions_layout.addLayout(partition_buttons_layout)

        self.skmesh_add_btn = QtWidgets.QPushButton()
        self.skmesh_add_btn.setIcon(pyqt.get_icon("mgear_plus"))
        partition_buttons_layout.addWidget(self.skmesh_add_btn)

        self.skmesh_rem_btn = QtWidgets.QPushButton()
        self.skmesh_rem_btn.setIcon(pyqt.get_icon("mgear_minus"))
        partition_buttons_layout.addWidget(self.skmesh_rem_btn)
        partition_buttons_layout.addStretch()

        # export button
        self.skmesh_export_btn = QtWidgets.QPushButton("Export SkeletalMesh/SkinnedMesh")
        self.skmesh_export_btn.setStyleSheet("QPushButton {background:rgb(70, 100, 150);}")
        skeletal_mesh_layout.addWidget(self.skmesh_export_btn)

    def create_animation_tab(self):
        # export animation
        animation_tab = QtWidgets.QWidget()
        self.export_tab.addTab(animation_tab, "Animation")
        animation_layout = QtWidgets.QVBoxLayout(animation_tab)

        self.animation_clips_list_widget = fbx_widgets.AnimClipsListWidget(parent=self)
        animation_layout.addWidget(self.animation_clips_list_widget)

        self.anim_export_btn = QtWidgets.QPushButton("Export Animations")
        self.anim_export_btn.setStyleSheet("QPushButton {background:rgb(150, 35, 50);}")
        animation_layout.addWidget(self.anim_export_btn)

    def create_connections(self):
        # menu connections
        self.set_fbx_sdk_path_action.triggered.connect(self.set_fbx_sdk_path)
        self.refresh_uegear_connection_action.triggered.connect(
            self.refresh_ue_connection
        )

        # source element connections
        self.geo_set_btn.clicked.connect(
            partial(self._add_list_items_from_sel, self.geo_root_list,
                    "transform", clear=True))
        self.geo_add_btn.clicked.connect(
            partial(self._add_list_items_from_sel, self.geo_root_list,
                    "transform"))
        self.geo_rem_btn.clicked.connect(
            partial(self._remove_list_items_from_sel, self.geo_root_list))
        self.geo_auto_set_btn.clicked.connect(
            partial(self._auto_set_geo_roots, clear=True))

        self.joint_set_btn.clicked.connect(
            partial(self._set_lineedit_text_from_sel, self.joint_root_lineedit,
                    "joint"))
        self.joint_auto_set_btn.clicked.connect(
            partial(self._auto_set_joint_root)
        )

        # file path connections
        self.file_set_btn.clicked.connect(self.set_folder_path)
        self.file_name_lineedit.textChanged.connect(self.normalize_name)

        # ue file path connection
        self.ue_file_set_btn.clicked.connect(self.set_ue_folder_path)

        # skeletal mesh connections
        self.partitions_checkbox.toggled.connect(self.set_use_partitions)
        self.skmesh_add_btn.clicked.connect(self.add_skeletal_mesh_partition)
        self.skmesh_rem_btn.clicked.connect(self.remove_skeletal_mesh_partition)
        self.skmesh_export_btn.clicked.connect(self.export_skeletal_mesh)

        # animation connection
        self.anim_export_btn.clicked.connect(self.export_animation_clips)

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

    def normalize_name(self):
        name = string.removeInvalidCharacter2(self.file_name_lineedit.text())
        self.file_name_lineedit.setText(name)

    def populate_fbx_presets_combobox(self, combobox, filepaths):
        for path in filepaths:
            fbx_filename = os.path.basename(path)
            fbx_base_filename, _ = os.path.splitext(fbx_filename)
            combobox.addItem(fbx_base_filename, userData=path)

        # Force user defined as the default preset
        combobox.setCurrentText("User defined")

    def set_folder_path(self):
        folder_path = pm.fileDialog2(fileMode=3)
        if folder_path:
            self.file_path_lineedit.setText(
                string.normalize_path(folder_path[0])
            )

    def set_fbx_sdk_path(self):
        current_fbx_sdk_path = pfbx.get_fbx_sdk_path()
        fbx_sdk_path = pm.fileDialog2(
            fileMode=3, startingDirectory=current_fbx_sdk_path
        )
        if fbx_sdk_path:
            pfbx.set_fbx_skd_path(fbx_sdk_path[0], user=True)

        self.refresh_fbx_sdk_ui()

    def refresh_fbx_sdk_ui(self):
        self.remove_namespace_checkbox.setEnabled(pfbx.FBX_SDK)
        self.clean_scene_checkbox.setEnabled(pfbx.FBX_SDK)
        self.partitions_checkbox.setEnabled(pfbx.FBX_SDK)
        self.set_use_partitions(self.partitions_checkbox.isChecked())

        fbx_sdk_path = pfbx.get_fbx_sdk_path()
        if not fbx_sdk_path or not os.path.isdir(fbx_sdk_path):
            self.fbx_sdk_path_action.setText("Python FBX SDK: Not set")
        else:
            self.fbx_sdk_path_action.setText(
                "Python FBX SDK: {}".format(fbx_sdk_path)
            )

    def refresh_ue_connection(self):
        # TODO: Uncomment
        # is_available = bool(uegear.content_project_directory())
        is_available = False
        self.ue_import_collap_wgt.setEnabled(is_available)
        if not is_available:
            cmds.warning(
                "Unreal Engine Import functionality not available. Run Unreal Engine and load ueGear plugin."
            )
            self.ue_import_cbx.setChecked(False)

    def update_settings(self):
        # Function that can be used to update settings file before loading them.
        # Useful in case we change the way UI settings are stored, so we can update old setting files.
        pass

    def set_ue_folder_path(self):
        content_folder = uegear.content_project_directory()
        folder_path = cmds.fileDialog2(
            fileMode=3, startingDirectory=content_folder
        )
        if folder_path:
            self.ue_file_path_lineedit.setText(
                string.normalize_path(folder_path[0])
            )

    def set_use_partitions(self, flag):
        self.partitions_outliner.setEnabled(flag)
        self.partitions_label.setEnabled(flag)
        self.skmesh_add_btn.setEnabled(flag)
        self.skmesh_rem_btn.setEnabled(flag)

    def add_skeletal_mesh_partition(self):
        export_node = self._get_or_create_export_node()
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "New Partition",
            "New Partition",
            QtWidgets.QLineEdit.Normal,
            "New Partition",
        )
        if not (name and ok):
            return
        result = export_node.add_new_skeletal_mesh_partition(name, list())
        if not result:
            return
        self.partitions_outliner.reset_contents()

    def remove_skeletal_mesh_partition(self):
        selected_partition_items = (
            self.partitions_outliner.selectedItems()
        )
        if not selected_partition_items:
            return

        for selected_partition_item in selected_partition_items:
            if selected_partition_item.node.is_master:
                return

        response = cmds.confirmDialog(
            title="Confirm",
            message="Confirm Deletion",
            button=["Yes", "No"],
            defaultButton="Yes",
            cancelButton="No",
            dismissString="No",
        )
        if response == "Yes":
            for selected_partition_item in selected_partition_items:
                selected_partition_item.delete_node()

    def export_skeletal_mesh(self):
        print("----- Exporting Skeletal Meshes -----")

        # force creation of the export node
        self._get_or_create_export_node()

        geo_roots = self._get_listwidget_item_names(self.geo_root_list)
        if not geo_roots:
            cmds.warning("No geo roots defined!")
            return False
        jnt_root = self.joint_root_lineedit.text().split(",")
        if not jnt_root[0]:
            cmds.warning("No Joint Root defined!")
            return False
        print("\t>>> Geo Roots: {}".format(geo_roots))
        print("\t>>> Joint Root: {}".format(jnt_root))

        self._auto_set_file_path()
        file_path = self.file_path_lineedit.text()
        file_name = self.file_name_lineedit.text()
        if not file_path or not file_name:
            cmds.warning("Not valid file path and name defined!")
            return False

        partitions = dict()
        use_partitions = self.partitions_checkbox.isChecked()
        if use_partitions:

            # Master partition data is retrieved from UI
            # TODO: Should we store master data within FbxExporterNode too?
            master_partition = (
                self.partitions_outliner.get_master_partition()
            )

            export_nodes = fbx_export_node.FbxExportNode.find()
            if not export_nodes:
                cmds.warning("No export nodes found within scene!")
                return False
            if len(export_nodes) > 2:
                cmds.warning(
                    'Multiple FBX Export nodes found in scene. \
                        Using first one found: "{}"'.format(export_nodes[0])
                )
            found_partitions = dict()
            found_partitions.update(master_partition)
            found_partitions.update(export_nodes[0].get_partitions())
            for partition_name, partition_data in found_partitions.items():
                enabled = partition_data.get("enabled", True)
                skeletal_meshes = partition_data.get("skeletalMeshes", list())
                if not enabled or not skeletal_meshes:
                    continue
                partitions[partition_name] = skeletal_meshes
            print("\t>>> Partitions: {}".format(partitions))

        current_export_preset = self.fbx_export_presets_combobox.currentText()
        preset_file_path = ""
        if current_export_preset and current_export_preset != "User defined":
            preset_file_path = self.fbx_export_presets_combobox.itemData(
                self.fbx_export_presets_combobox.currentIndex()
            )
        print("\t>>> Preset File Path: {}".format(preset_file_path))

        # retrieve export config
        export_config = {
            "up_axis": self.up_axis_combobox.currentText(),
            "file_type": self.file_type_combobox.currentText(),
            "fbx_version": self.fbx_version_combobox.currentText(),
            "remove_namespace": self.remove_namespace_checkbox.isChecked(),
            "scene_clean": self.clean_scene_checkbox.isChecked(),
            "use_partitions": use_partitions,
            "file_name": file_name,
            "file_path": file_path,
            "skinning": self.skinning_checkbox.isChecked(),
            "blendshapes": self.blendshapes_checkbox.isChecked(),
            "partitions": partitions,
        }

        result = utils.export_skeletal_mesh(jnt_root, geo_roots, **export_config)
        if not result:
            cmds.warning(
                "Something went wrong while exporting Skeletal Mesh/es"
            )
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
        print("----- Exporting Animation Clips -----")

        jnt_root = self.joint_root_lineedit.text().split(",")
        if not jnt_root[0]:
            cmds.warning("No Joint Root defined")
            return False
        jnt_root = jnt_root[0]
        print("\t>>> Joint Root: {}".format(jnt_root))

        self._auto_set_file_path()
        file_path = self.file_path_lineedit.text()
        file_name = self.file_name_lineedit.text()
        if not file_path or not file_name:
            cmds.warning("Not valid file path and name defined!")
            return False

        current_export_preset = self.fbx_export_presets_combobox.currentText()
        preset_file_path = ""
        if current_export_preset and current_export_preset != "User defined":
            preset_file_path = self.fbx_export_presets_combobox.itemData(
                self.fbx_export_presets_combobox.currentIndex()
            )
        print("\t>>> Preset File Path: {}".format(preset_file_path))

        export_nodes = fbx_export_node.FbxExportNode.find()
        if not export_nodes:
            return False
        if len(export_nodes) > 2:
            cmds.warning(
                'Multiple FBX Export nodes found in scene. Using first one found: "{}"'.format(
                    export_nodes[0]
                )
            )
        export_node = export_nodes[0]

        # retrieve export config
        base_export_config = {
            "up_axis": self.up_axis_combobox.currentText(),
            "file_type": self.file_type_combobox.currentText(),
            "fbx_version": self.fbx_version_combobox.currentText(),
            "remove_namespace": self.remove_namespace_checkbox.isChecked(),
            "scene_clean": self.clean_scene_checkbox.isChecked(),
            "file_name": file_name,
            "file_path": file_path,
        }

        for anim_clip_data in export_node.get_animation_clips(jnt_root):
            anim_clip_export_data = base_export_config.copy()
            anim_clip_export_data.update(anim_clip_data)
            utils.export_animation_clip(jnt_root, **anim_clip_export_data)

        return True

    # Helper methods
    def _get_or_create_export_node(self):
        return fbx_export_node.FbxExportNode.get() or \
            fbx_export_node.FbxExportNode.create()

    def _get_listwidget_item_names(self, listwidget):
        return [listwidget.item(i).text() for i in range(listwidget.count())]

    def _update_geo_root_data(self):
        item_names = self._get_listwidget_item_names(self.geo_root_list)
        self.partitions_outliner.set_geo_roots(item_names)
        export_node = self._get_or_create_export_node()
        export_node.save_root_data("geo_root", item_names)

    def _auto_set_geo_roots(self, clear=False):
        geo_roots = list()
        if clear:
            self.geo_root_list.clear()
        if not self.geo_root_list.count():
            geo_roots.append(utils.get_geo_root())
        self.geo_root_list.addItems(geo_roots)
        self._update_geo_root_data()

    def _auto_set_joint_root(self):
        joint_roots = utils.get_joint_root()
        joint_name = joint_roots[0].name() if joint_roots else ""
        self.joint_root_lineedit.setText(joint_name)
        self.animation_clips_list_widget.refresh()
        export_node = self._get_or_create_export_node()
        export_node.save_root_data("joint_root", joint_name)

    def _auto_set_file_path(self):
        if self.file_path_lineedit.text() or self.file_name_lineedit.text():
            return
        file_path = pm.fileDialog2(fileMode=0, fileFilter="FBX(*.fbx)")
        if not file_path:
            return
        file_path = file_path[0]
        dir_name = os.path.dirname(file_path)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        self.file_path_lineedit.setText(string.normalize_path(dir_name))
        self.file_name_lineedit.setText(file_name)

    def _filter_selection_by_type(self, type_filter=None):
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
                if type_filter != sel_type:
                    pm.displayWarning(
                        "Selected element is not of type: {}".format(
                            type_filter
                        )
                    )
                    continue
            filter_sel.append(node.name())

        return filter_sel

    def _add_list_items_from_sel(self, listwidget, type_filter, clear=False):
        """Adds list widget items from selected element filtered by type

        Args:
            listwidget (QListWidget): QT line list widget object
            type_filter (str): Type to filter: for example "joint"
                               or "transform"
        """
        if clear:
            listwidget.clear()
        item_names = self._get_listwidget_item_names(listwidget)
        node_names = self._filter_selection_by_type(type_filter)
        for node_name in node_names:
            if not clear and node_name in item_names:
                continue
            listwidget.addItem(node_name)
        if listwidget == self.geo_root_list:
            self._update_geo_root_data()

    def _remove_list_items_from_sel(self, listwidget):
        """Removes list widget items from selected list items

        Args:
            listwidget (QListWidget): QT line list widget object
        """
        selected_items = listwidget.selectedItems()
        for selected_item in selected_items:
            listwidget.takeItem(listwidget.row(selected_item))
        if listwidget == self.geo_root_list:
            self._update_geo_root_data()

    def _set_lineedit_text_from_sel(self, lineedit, type_filter):
        """Set line edit text from selected element filtered by type

        Args:
            lineedit (QLineEdit): QT line edit object
            type_filter (str): Type to filter: for example "joint"
                               or "transform"
        """
        text = self._filter_selection_by_type(type_filter)
        text = text[0] if text else ""
        lineedit.setText(text)
        export_node = self._get_or_create_export_node()
        export_node.save_root_data("joint_root", text)
        if type_filter == "joint":
            self.animation_clips_list_widget.refresh()


def openFBXExporter(*args):
    return pyqt.showDialog(FBXExporter, dockable=True)


if __name__ == "__main__":
    from mgear.shifter.game_tools_fbx import widgets

    import sys
    if sys.version_info[0] == 2:
        reload(widgets)
    else:
        importlib.reload(widgets)

    start = timeit.default_timer()
    openFBXExporter()
    end = timeit.default_timer()
    timeConsumed = end - start
    print("{} time elapsed running".format(timeConsumed))
