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

# from . import game_tools_fbx_widgets as gtw


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

        # set roots
        self.mesh_root_label = QtWidgets.QLabel("Mesh Root")
        self.mesh_root_lineedit = QtWidgets.QLineEdit()
        self.mesh_root_set_button = QtWidgets.QPushButton("Set")

        self.joint_root_label = QtWidgets.QLabel("Joint Root")
        self.joint_root_lineedit = QtWidgets.QLineEdit()
        self.joint_root_set_button = QtWidgets.QPushButton("Set")

        # model export options
        self.skinning_checkbox = QtWidgets.QCheckBox("Skinning")
        self.blendshapes_checkbox = QtWidgets.QCheckBox("Blendshapes")

        # settings
        self.up_axis_combox = QtWidgets.QComboBox("Up Axis")
        self.up_axis_combox.addItem("Y")
        self.up_axis_combox.addItem("Z")
        self.file_type_combox = QtWidgets.QComboBox("File Type")
        self.file_type_combox.addItem("Binary")
        self.file_type_combox.addItem("ASCII")
        self.fbx_version_combox = QtWidgets.QComboBox("FBX Version")

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

        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)
        self.main_layout.setMenuBar(self.menu_bar)

        self.main_layout.addWidget(self.set_source_groupbox)
        self.main_layout.addWidget(self.model_deformers_groupbox)
        self.main_layout.addStretch()

    def create_connections(self):
        return


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
