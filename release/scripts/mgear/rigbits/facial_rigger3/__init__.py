"""Facial Rigger 3.0: eyelid, lips and brow rigs from mesh loops.

The rigs are built by the shared engine in :mod:`mgear.core.facial`, so a
Shifter component can build the same rigs from the same settings.
"""

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtWidgets

from mgear.core import pyqt

from maya import cmds
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from . import eye_ui


class FacialRiggerUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    """Dockable Facial Rigger 3.0 window, one tab per rig."""

    toolName = "FacialRigger3"

    def __init__(self, parent=None):
        """Initialize the window.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(FacialRiggerUI, self).__init__(parent)
        self.setObjectName(self.toolName)
        self.setWindowTitle("Facial Rigger 3.0")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setMinimumWidth(320)
        self.resize(380, 720)
        if cmds.about(ntOS=True):
            flags = self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
            self.setWindowFlags(flags)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.tabs = QtWidgets.QTabWidget()
        self.eye_tab = eye_ui.EyeRiggerTab()
        self.tabs.addTab(self.eye_tab, "Eye")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tabs)


def show(*args):
    """Show the Facial Rigger 3.0 window.

    Returns:
        FacialRiggerUI: The window.
    """
    return pyqt.showDialog(FacialRiggerUI, dockable=True)
