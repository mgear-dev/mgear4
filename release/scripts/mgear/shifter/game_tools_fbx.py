import maya.cmds as cmds
import pymel.core as pm
from mgear.core import pyqt
from mgear.core import attribute
from mgear.core import utils
from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.core import callbackManager
from mgear.core import pyFBX as pfbx
import timeit
from functools import partial
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import importlib

from mgear.shifter import game_tools_fbx_utils as fu

# from . import game_tools_fbx_widgets as fw


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

    def create_actions(self):
        # file actions
        self.file_new_node_action = QtWidgets.QAction("New Node", self)
        self.file_new_node_action.setIcon(pyqt.get_icon("mgear_plus-square"))

    def create_widgets(self):

        # menu bar
        self.menu_bar = QtWidgets.QMenuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.file_menu.addAction(self.file_new_node_action)
        self.file_menu.addSeparator()

        # set source roots
        self.mesh_root_label = QtWidgets.QLabel("Mesh Root")
        self.mesh_root_lineedit = QtWidgets.QLineEdit()
        self.mesh_root_set_button = QtWidgets.QPushButton("Set")

        self.joint_root_label = QtWidgets.QLabel("Joint Root")
        self.joint_root_lineedit = QtWidgets.QLineEdit()
        self.joint_root_set_button = QtWidgets.QPushButton("Set")

        # model deformers options
        self.skinning_checkbox = QtWidgets.QCheckBox("Skinning")
        self.skinning_checkbox.setChecked(True)
        self.blendshapes_checkbox = QtWidgets.QCheckBox("Blendshapes")
        self.blendshapes_checkbox.setChecked(True)

        # settings
        self.up_axis_label = QtWidgets.QLabel("Up Axis")
        self.up_axis_combobox = QtWidgets.QComboBox()
        self.up_axis_combobox.addItem("Y")
        self.up_axis_combobox.addItem("Z")
        self.file_type_label = QtWidgets.QLabel("File Type")
        self.file_type_combobox = QtWidgets.QComboBox()
        self.file_type_combobox.addItem("Binary")
        self.file_type_combobox.addItem("ASCII")
        self.fbx_version_label = QtWidgets.QLabel("FBX Version")
        self.fbx_version_combobox = QtWidgets.QComboBox()
        self.populate_fbx_versions_combobox(self.fbx_version_combobox)

        # FBX SDK settings
        self.remove_namespace_checkbox = QtWidgets.QCheckBox(
            "Remove Namespace"
        )
        self.remove_namespace_checkbox.setChecked(True)
        self.clean_scene_checkbox = QtWidgets.QCheckBox(
            "Joint and Mesh Root Child of Scene Root + Clean Up Scene"
        )
        self.clean_scene_checkbox.setChecked(True)

        # animation

        return

    def create_layout(self):

        # set source layout
        self.mesh_root_layout = QtWidgets.QHBoxLayout()
        self.mesh_root_layout.setContentsMargins(1, 1, 1, 1)
        self.mesh_root_layout.addWidget(self.mesh_root_label)
        self.mesh_root_layout.addWidget(self.mesh_root_lineedit)
        self.mesh_root_layout.addWidget(self.mesh_root_set_button)

        self.joint_root_layout = QtWidgets.QHBoxLayout()
        self.joint_root_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_layout.addWidget(self.joint_root_label)
        self.joint_root_layout.addWidget(self.joint_root_lineedit)
        self.joint_root_layout.addWidget(self.joint_root_set_button)

        self.set_source_groupbox = QtWidgets.QGroupBox("Set Source Elements")
        self.set_source_layout = QtWidgets.QVBoxLayout(
            self.set_source_groupbox
        )
        self.set_source_layout.addLayout(self.mesh_root_layout)
        self.set_source_layout.addLayout(self.joint_root_layout)

        self.set_source_layout.setSpacing(2)

        # deformers layout
        self.model_deformers_groupbox = QtWidgets.QGroupBox("Deformers")
        self.model_deformers_layout = QtWidgets.QHBoxLayout(
            self.model_deformers_groupbox
        )
        self.model_deformers_layout.addWidget(self.skinning_checkbox)
        self.model_deformers_layout.addWidget(self.blendshapes_checkbox)

        self.set_source_layout = QtWidgets.QVBoxLayout(
            self.model_deformers_groupbox
        )

        # settings layout
        self.settings_groupbox = QtWidgets.QGroupBox("Settings")
        self.settings_form_layout = QtWidgets.QFormLayout(
            self.settings_groupbox
        )
        self.settings_form_layout.setWidget(
            0, QtWidgets.QFormLayout.LabelRole, self.up_axis_label
        )
        self.settings_form_layout.setWidget(
            0, QtWidgets.QFormLayout.FieldRole, self.up_axis_combobox
        )
        self.settings_form_layout.setWidget(
            1, QtWidgets.QFormLayout.LabelRole, self.file_type_label
        )
        self.settings_form_layout.setWidget(
            1, QtWidgets.QFormLayout.FieldRole, self.file_type_combobox
        )
        self.settings_form_layout.setWidget(
            2, QtWidgets.QFormLayout.LabelRole, self.fbx_version_label
        )
        self.settings_form_layout.setWidget(
            2, QtWidgets.QFormLayout.FieldRole, self.fbx_version_combobox
        )

        # FBX SDK settings
        self.sdk_settings_groupbox = QtWidgets.QGroupBox("FBX SDK settings")
        self.sdk_settings_layout = QtWidgets.QVBoxLayout(
            self.sdk_settings_groupbox
        )
        self.sdk_settings_layout.addWidget(self.remove_namespace_checkbox)
        self.sdk_settings_layout.addWidget(self.clean_scene_checkbox)

        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)
        self.main_layout.setMenuBar(self.menu_bar)

        self.main_layout.addWidget(self.set_source_groupbox)
        self.main_layout.addWidget(self.model_deformers_groupbox)
        self.main_layout.addWidget(self.settings_groupbox)
        self.main_layout.addWidget(self.sdk_settings_groupbox)
        self.main_layout.addStretch()

    def create_connections(self):
        return

    # Helper methods

    def populate_fbx_versions_combobox(self, combobox):
        fbx_versions = pfbx.get_fbx_versions()
        for v in fbx_versions:
            combobox.addItem(v)


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
