"""Guide Mouth 01 module"""

from mgear.shifter.component import guide
from mgear.core import transform, pyqt
from mgear.vendor.Qt import QtWidgets, QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

# guide info
AUTHOR = "Jeremie Passerin, Miquel Campos"
URL = ", www.miquletd.com"
EMAIL = ""
VERSION = [2, 0, 0]
TYPE = "mouth_02"
NAME = "mouth"
DESCRIPTION = "mouth lips and jaw. Extra offset Jaw control"

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
        self.save_transform = ["root", "rotcenter", "lipup", "liplow", "jaw"]

    def addObjects(self):
        """Add the Guide Root, blade and locators"""

        # eye guide
        self.root = self.addRoot()
        vTemp = transform.getOffsetPosition(self.root, [0, 0, 1])
        self.rotcenter = self.addLoc("rotcenter", self.root, vTemp)
        vTemp = transform.getOffsetPosition(self.root, [0, .3, 1.3])
        self.lipup = self.addLoc("lipup", self.rotcenter, vTemp)
        vTemp = transform.getOffsetPosition(self.root, [0, -.3, 1.3])
        self.liplow = self.addLoc("liplow", self.rotcenter, vTemp)
        vTemp = transform.getOffsetPosition(self.root, [0, -2, 2])
        self.jaw = self.addLoc("jaw", self.root, vTemp)

        centers = [self.root, self.rotcenter]
        self.dispcrv = self.addDispCurve("crv", centers)

        centers = [self.lipup, self.rotcenter]
        self.dispcrv = self.addDispCurve("crv", centers)

        centers = [self.liplow, self.rotcenter]
        self.dispcrv = self.addDispCurve("crv", centers)

        centers = [self.root, self.jaw]
        self.dispcrv = self.addDispCurve("crv", centers)

    def addParameters(self):
        """Add the configurations settings"""

        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None)

        return


##########################################################
# Setting Page
##########################################################


class componentSettings(MayaQWidgetDockableMixin, guide.componentMainSettings):
    """Create the component setting window"""

    def __init__(self, parent=None):
        self.toolName = TYPE
        # Delete old instances of the componet settings window.
        pyqt.deleteInstances(self, MayaQDockWidget)

        super(componentSettings, self).__init__(parent=parent)

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
        self.resize(350, 350)

    def create_componentControls(self):
        return

    def populate_componentControls(self):
        """Populate the controls values.

        Populate the controls values from the custom attributes of the
        component.

        """
        return

    def create_componentLayout(self):

        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)

        self.setLayout(self.settings_layout)

    def create_componentConnections(self):
        return

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
