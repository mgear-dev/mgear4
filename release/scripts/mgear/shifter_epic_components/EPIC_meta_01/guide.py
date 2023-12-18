from functools import partial

from mgear.shifter.component import guide
from mgear.core import pyqt
from mgear.vendor.Qt import QtWidgets, QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

from . import settingsUI as sui

# guide info
AUTHOR = "Jeremie Passerin, Miquel Campos"
URL = ", www.mcsgear.com"
EMAIL = ", "
VERSION = [1, 0, 0]
TYPE = "EPIC_meta_01"
NAME = "meta"
DESCRIPTION = "metacarpal finger spread."

##########################################################
# CLASS
##########################################################


class Guide(guide.ComponentGuide):
    """Component Guide Class"""

    compType = TYPE
    compName = NAME
    description = DESCRIPTION

    author = AUTHOR
    url = URL
    email = EMAIL
    version = VERSION

    def postInit(self):
        """Initialize the position for the guide"""
        self.save_transform = ["root", "#_loc"]
        self.save_blade = ["blade"]
        self.addMinMax("#_loc", 1, -1)

    def addObjects(self):
        """Add the Guide Root, blade and locators"""

        self.root = self.addRoot()
        self.locs = self.addLocMulti("#_loc", self.root)
        self.blade = self.addBlade("blade", self.root, self.locs[0])

        centers = [self.root]
        centers.extend(self.locs)
        self.dispcrv = self.addDispCurve("crv", centers)

    def addParameters(self):
        """Add the configurations settings"""
        self.pScale = self.addParam("intScale", "bool", True)
        self.pRotate = self.addParam("intRotation", "bool", True)
        self.pTranslation = self.addParam("intTranslation", "bool", True)
        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None)
        self.pJointChainCnx = self.addParam("jointChainCnx", "bool", True)
        self.pMetaCtl = self.addParam("metaCtl", "bool", False)

##########################################################
# Setting Page
##########################################################


class settingsTab(QtWidgets.QDialog, sui.Ui_Form):
    """The Component settings UI"""

    def __init__(self, parent=None):
        super(settingsTab, self).__init__(parent)
        self.setupUi(self)


class componentSettings(MayaQWidgetDockableMixin, guide.componentMainSettings):
    """Create the component setting window"""

    def __init__(self, parent=None):
        self.toolName = TYPE
        # Delete old instances of the componet settings window.
        pyqt.deleteInstances(self, MayaQDockWidget)

        super(componentSettings, self).__init__(parent=parent)
        self.settingsTab = settingsTab()

        self.setup_componentSettingWindow()
        self.create_componentControls()
        self.populate_componentControls()
        self.create_componentLayout()
        self.create_componentConnections()

    def setup_componentSettingWindow(self):
        self.mayaMainWindow = pyqt.maya_main_window()

        self.setObjectName(self.toolName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle(TYPE)
        self.resize(350, 520)

    def create_componentControls(self):
        return

    def populate_componentControls(self):
        """Populate the controls values.

        Populate the controls values from the custom attributes of the
        component.

        """
        # populate tab
        self.tabs.insertTab(1, self.settingsTab, "Component Settings")

        # populate component settings

        self.populateCheck(self.settingsTab.intScale_checkBox,
                           "intScale")
        self.populateCheck(self.settingsTab.intRotation_checkBox,
                           "intRotation")
        self.populateCheck(self.settingsTab.intTranslation_checkBox,
                           "intTranslation")
        self.populateCheck(self.settingsTab.jointChainCnx_checkBox,
                           "jointChainCnx")
        self.populateCheck(self.settingsTab.metaCtl_checkBox,
                           "metaCtl")

    def create_componentLayout(self):

        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)

        self.setLayout(self.settings_layout)

    def create_componentConnections(self):

        self.settingsTab.intScale_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.intScale_checkBox,
                    "intScale"))

        self.settingsTab.intRotation_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.intRotation_checkBox,
                    "intRotation"))
        self.settingsTab.intTranslation_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.intTranslation_checkBox,
                    "intTranslation"))

        self.settingsTab.jointChainCnx_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.jointChainCnx_checkBox,
                    "jointChainCnx"))
        self.settingsTab.metaCtl_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.metaCtl_checkBox,
                    "metaCtl"))

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
