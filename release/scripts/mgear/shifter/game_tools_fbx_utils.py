import pymel.core as pm
import sys
import os

# from mgear.vendor.Qt import QtWidgets
# from mgear.vendor.Qt import QtCore
# from mgear.vendor.Qt import QtGui
# TODO: comment out later. using direct import for better autocompletion
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

from mgear.core import pyFBX as pfbx
from mgear.core import pyqt


def export_skeletal_mesh(jnt_root, mesh_root, path, **kwargs):

    # export settings config
    pfbx.FBXResetExport()

    # set configuration
    if "up_axis" in kwargs.keys():
        pfbx.FBXExportUpAxis(kwargs["up_axis"])

    # select elements
    pm.select([jnt_root, mesh_root])

    # export
    pfbx.FBXExport(f=path, s=True)

    # post process with FBX SDK if available
    return


def export_animation_clip():
    return


def export_skeletal_mesh_from_preset(jnt_root, mesh_root, path, preset_path):

    # export setings config
    pfbx.FBXResetExport()

    # load FBX export preset file
    pfbx.FBXLoadExportPresetFile(f=preset_path)

    # select elements
    pm.select([jnt_root, mesh_root])

    # export
    pfbx.FBXExport(f=path, s=True)

    # post process with FBX SDK if available
    return


def export_animation_clip_from_preset(preset_path):
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
