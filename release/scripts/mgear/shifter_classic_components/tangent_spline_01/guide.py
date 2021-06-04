"""Guide Squash 01 module"""

from functools import partial

from mgear.shifter.component import guide
from mgear.core import transform, pyqt
from mgear.vendor.Qt import QtWidgets, QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

from . import settingsUI as sui

# guide info
AUTHOR = "anima inc."
URL = "www.studioanima.co.jp "
EMAIL = ""
VERSION = [1, 0, 0]
TYPE = "tangent_spline_01"
NAME = "tangentSpline"
DESCRIPTION = ("Spline with tangent controls and IK reference Array. \n"
               "All controls are world oriented")

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
        self.save_transform = ["root", "tan0", "tan1", "tan2", "tip", "tiptan"]
        self.save_blade = ["blade"]

    def addObjects(self):
        """Add the Guide Root, blade and locators"""

        self.root = self.addRoot()

        vTemp = transform.getOffsetPosition(self.root, [0, 3, 0])
        self.tip = self.addLoc("tip", self.root, vTemp)

        vTemp = transform.getOffsetPosition(self.root, [0, 1, 0])
        self.tan0 = self.addLoc("tan0", self.root, vTemp)

        vTemp = transform.getOffsetPosition(self.root, [0, 2, 0])
        self.tan1 = self.addLoc("tan1", self.tip, vTemp)

        vTemp = transform.getOffsetPosition(self.root, [0, 4, 0])
        self.tan2 = self.addLoc("tan2", self.tip, vTemp)

        vTemp = transform.getOffsetPosition(self.root, [0, 5, 0])
        self.tiptan = self.addLoc("tiptan", self.tan2, vTemp)

        self.blade = self.addBlade("blade", self.root, self.tan0)

        centers = [self.root,
                   self.tan0,
                   self.tan1,
                   self.tip,
                   self.tan2,
                   self.tiptan]
        self.dispcrv = self.addDispCurve("spline_crv", centers, 3)

        centers = [self.root, self.tan0]
        self.dispcrv = self.addDispCurve("tangentA_crv", centers, 1)
        centers = [self.tan1, self.tip, self.tan2, self.tiptan]
        self.dispcrv = self.addDispCurve("tangentB_crv", centers, 1)

    def addParameters(self):
        """Add the configurations settings"""

        self.pKeepLength = self.addParam("keepLength", "bool", False)
        self.pJntNb = self.addParam("jntNb", "long", 3, 1)

        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None)

        self.pRootRefArray = self.addParam("rootRefArray", "string", "")
        self.pTipRefArray = self.addParam("tipRefArray", "string", "")


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

        super(self.__class__, self).__init__(parent=parent)
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
        self.resize(280, 620)

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
        self.populateCheck(self.settingsTab.keepLength_checkBox,
                           "keepLength")
        self.settingsTab.jntNb_spinBox.setValue(self.root.attr("jntNb").get())

        rootRefArrayItems = self.root.attr("rootRefArray").get().split(",")
        for item in rootRefArrayItems:
            self.settingsTab.rootRefArray_listWidget.addItem(item)
        tipRefArrayItems = self.root.attr("tipRefArray").get().split(",")
        for item in tipRefArrayItems:
            self.settingsTab.tipRefArray_listWidget.addItem(item)

    def create_componentLayout(self):

        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)

        self.setLayout(self.settings_layout)

    def create_componentConnections(self):

        self.settingsTab.keepLength_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.keepLength_checkBox,
                    "keepLength"))

        self.settingsTab.jntNb_spinBox.valueChanged.connect(
            partial(self.updateSpinBox,
                    self.settingsTab.jntNb_spinBox,
                    "jntNb"))

        self.settingsTab.rootRefArrayAdd_pushButton.clicked.connect(
            partial(self.addItem2listWidget,
                    self.settingsTab.rootRefArray_listWidget,
                    "rootRefArray"))

        self.settingsTab.rootRefArrayRemove_pushButton.clicked.connect(
            partial(self.removeSelectedFromListWidget,
                    self.settingsTab.rootRefArray_listWidget,
                    "rootRefArray"))

        self.settingsTab.rootRefArray_copyRef_pushButton.clicked.connect(
            partial(self.copyFromListWidget,
                    self.settingsTab.tipRefArray_listWidget,
                    self.settingsTab.rootRefArray_listWidget,
                    "rootRefArray"))

        self.settingsTab.rootRefArray_listWidget.installEventFilter(self)

        self.settingsTab.tipRefArrayAdd_pushButton.clicked.connect(
            partial(self.addItem2listWidget,
                    self.settingsTab.tipRefArray_listWidget,
                    "tipRefArray"))

        self.settingsTab.tipRefArrayRemove_pushButton.clicked.connect(
            partial(self.removeSelectedFromListWidget,
                    self.settingsTab.tipRefArray_listWidget,
                    "tipRefArray"))

        self.settingsTab.tipRefArray_copyRef_pushButton.clicked.connect(
            partial(self.copyFromListWidget,
                    self.settingsTab.rootRefArray_listWidget,
                    self.settingsTab.tipRefArray_listWidget,
                    "tipRefArray"))

        self.settingsTab.tipRefArray_listWidget.installEventFilter(self)

    def eventFilter(self, sender, event):
        if event.type() == QtCore.QEvent.ChildRemoved:
            if sender == self.settingsTab.rootRefArray_listWidget:
                self.updateListAttr(sender, "rootRefArray")
            elif sender == self.settingsTab.tipRefArray_listWidget:
                self.updateListAttr(sender, "tipRefArray")
            return True
        else:
            return QtWidgets.QDialog.eventFilter(self, sender, event)

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
