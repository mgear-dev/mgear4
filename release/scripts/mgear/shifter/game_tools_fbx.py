import maya.cmds as cmds
import pymel.core as pm
from mgear.core import pyqt
from mgear.core import widgets
from mgear.core import attribute
from mgear.core import utils

# from mgear.vendor.Qt import QtWidgets
# from mgear.vendor.Qt import QtCore
# from mgear.vendor.Qt import QtGui
# TODO: comment out later. using direct import for better autocompletion
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

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
        self.file_export_preset_action = QtWidgets.QAction(
            "Export Preset", self
        )
        self.file_export_preset_action.setIcon(pyqt.get_icon("mgear_log-out"))
        self.file_import_preset_action = QtWidgets.QAction(
            "Import Preset", self
        )
        self.file_import_preset_action.setIcon(pyqt.get_icon("mgear_log-in"))

    def create_widgets(self):

        # menu bar
        self.menu_bar = QtWidgets.QMenuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.file_menu.addAction(self.file_export_preset_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.file_import_preset_action)

        # set source roots
        self.geo_root_label = QtWidgets.QLabel("Geo Root")
        self.geo_root_lineedit = QtWidgets.QLineEdit()
        self.geo_root_set_button = QtWidgets.QPushButton("Set")

        self.joint_root_label = QtWidgets.QLabel("Joint Root")
        self.joint_root_lineedit = QtWidgets.QLineEdit()
        self.joint_root_set_button = QtWidgets.QPushButton("Set")

        # settings
        self.up_axis_combobox = QtWidgets.QComboBox()
        self.up_axis_combobox.addItem("Y")
        self.up_axis_combobox.addItem("Z")
        self.file_type_combobox = QtWidgets.QComboBox()
        self.file_type_combobox.addItem("Binary")
        self.file_type_combobox.addItem("ASCII")
        self.fbx_version_combobox = QtWidgets.QComboBox()
        self.populate_fbx_versions_combobox(self.fbx_version_combobox)

        # FBX SDK settings
        self.remove_namespace_checkbox = QtWidgets.QCheckBox(
            "Remove Namespace"
        )
        self.remove_namespace_checkbox.setChecked(True)
        self.remove_namespace_checkbox.setEnabled(pfbx.FBX_SDK)
        self.clean_scene_checkbox = QtWidgets.QCheckBox(
            "Joint and Geo Root Child of Scene Root + Clean Up Scene"
        )
        self.clean_scene_checkbox.setChecked(True)
        self.clean_scene_checkbox.setEnabled(pfbx.FBX_SDK)

        # path and filename
        self.file_path_label = QtWidgets.QLabel("Path")
        self.file_path_lineedit = QtWidgets.QLineEdit()
        self.file_path_set_button = QtWidgets.QPushButton("Set")

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

    def create_layout(self):

        # set source layout
        self.geo_root_layout = QtWidgets.QHBoxLayout()
        self.geo_root_layout.setContentsMargins(1, 1, 1, 1)
        self.geo_root_layout.addWidget(self.geo_root_label)
        self.geo_root_layout.addWidget(self.geo_root_lineedit)
        self.geo_root_layout.addWidget(self.geo_root_set_button)

        self.joint_root_layout = QtWidgets.QHBoxLayout()
        self.joint_root_layout.setContentsMargins(1, 1, 1, 1)
        self.joint_root_layout.addWidget(self.joint_root_label)
        self.joint_root_layout.addWidget(self.joint_root_lineedit)
        self.joint_root_layout.addWidget(self.joint_root_set_button)

        self.set_source_layout = QtWidgets.QVBoxLayout()
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
        self.settings_form_layout.addRow(
            "File Version", self.fbx_version_combobox
        )
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

        # Scroll Area layoout
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
        self.geo_root_set_button.clicked.connect(
            partial(
                self.set_line_edit_text_from_sel,
                self.geo_root_lineedit,
                "transform",
            )
        )
        self.joint_root_set_button.clicked.connect(
            partial(
                self.set_line_edit_text_from_sel,
                self.joint_root_lineedit,
                "joint",
            )
        )

    # Helper methods

    def populate_fbx_versions_combobox(self, combobox):
        fbx_versions = pfbx.get_fbx_versions()
        for v in fbx_versions:
            combobox.addItem(v)

    def set_geo_root():
        return

    def set_joint_root():
        return

    def get_rig_root():
        return

    def filter_sel_by_type(self, type_filter=None):
        """Return the first selected element name if match the correct type

        Args:
            type_filter (str, optional): Type to filter: for example "joint"
                                         or "transform"

        Returns:
            str: Name

        """
        sel = pm.selected()
        if not sel:
            pm.displayWarning("Nothing selected")
            return
        if type_filter:
            sel_type = sel[0].type()
            if not type_filter == sel_type:
                pm.displayWarning(
                    "Selected element is not of type: {}".format(type_filter)
                )
                return
        return sel[0].name()

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
