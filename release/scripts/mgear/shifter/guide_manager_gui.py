from mgear.shifter import guide_manager_component, guide_template_explorer
from mgear.vendor.Qt import QtCore, QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from mgear.core import pyqt


# guides manager UI

class GuideManager(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    def __init__(self, parent=None):
        self.toolName = "GuideManager"
        super(GuideManager, self).__init__(parent=parent)

        self.gmc = guide_manager_component.GuideManagerComponent()
        self.gexp = guide_template_explorer.GuideTemplateExplorer()
        self.installEventFilter(self)
        self.create_window()
        self.create_layout()

    def keyPressEvent(self, event):
        if not event.key() == QtCore.Qt.Key_Escape:
            super(GuideManager, self).keyPressEvent(event)

    def create_window(self):

        self.setObjectName(self.toolName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle("Shifter Guide Manager")
        self.resize(280, 750)

    def create_layout(self):

        self.gm_layout = QtWidgets.QVBoxLayout()
        self.gm_layout.setContentsMargins(3, 3, 3, 3)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("manager_tab")
        self.tabs.insertTab(0, self.gmc, "Components")
        self.tabs.insertTab(1, self.gexp, "Templates")

        self.gm_layout.addWidget(self.tabs)

        self.setLayout(self.gm_layout)


def show_guide_manager(*args):
    pyqt.showDialog(GuideManager, dockable=True)
