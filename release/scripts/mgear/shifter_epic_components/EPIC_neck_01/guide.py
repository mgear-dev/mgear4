from functools import partial

from mgear.shifter.component import guide
from mgear.core import transform, pyqt, vector
from mgear.vendor.Qt import QtWidgets, QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

from . import settingsUI as sui

# guide info
AUTHOR = "Jeremie Passerin, Miquel Campos"
URL = "www.jeremiepasserin.com, www.miquel-campos.com"
EMAIL = ""
VERSION = [1, 0, 0]
TYPE = "EPIC_neck_01"
NAME = "neck"
DESCRIPTION = "Game ready component for EPIC's UE and other Game Engines\n"\
    "Based on neck_ik_01"

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
        self.save_transform = ["root", "tan0", "tan1", "neck", "head", "eff"]
        self.save_blade = ["blade"]

    def addObjects(self):
        """Add the Guide Root, blade and locators"""

        self.root = self.addRoot()
        vTemp = transform.getOffsetPosition(self.root, [0, 1, 0])
        self.neck = self.addLoc("neck", self.root, vTemp)
        vTemp = transform.getOffsetPosition(self.root, [0, 1.1, 0])
        self.head = self.addLoc("head", self.neck, vTemp)
        vTemp = transform.getOffsetPosition(self.root, [0, 2, 0])
        self.eff = self.addLoc("eff", self.head, vTemp)

        v0 = vector.linearlyInterpolate(
            self.root.getTranslation(space="world"),
            self.neck.getTranslation(space="world"),
            .333)

        self.tan0 = self.addLoc("tan0", self.root, v0)
        v1 = vector.linearlyInterpolate(
            self.root.getTranslation(space="world"),
            self.neck.getTranslation(space="world"),
            .666)

        self.tan1 = self.addLoc("tan1", self.neck, v1)

        self.blade = self.addBlade("blade", self.root, self.tan0)

        centers = [self.root, self.tan0, self.tan1, self.neck]
        self.dispcrv = self.addDispCurve("neck_crv", centers, 3)

        centers = [self.neck, self.head, self.eff]
        self.dispcrv = self.addDispCurve("head_crv", centers, 1)

    def addParameters(self):
        """Add the configurations settings"""

        # Ik
        self.pHeadRefArray = self.addParam("headrefarray", "string", "")
        self.pIkRefArray = self.addParam("ikrefarray", "string", "")

        # Default values
        self.pMaxStretch = self.addParam("maxstretch", "double", 1.5, 1)
        self.pMaxSquash = self.addParam("maxsquash", "double", .5, 0, 1)
        self.pSoftness = self.addParam("softness", "double", 0, 0, 1)

        # Options
        self.pDivision = self.addParam("division", "long", 2, 1)
        self.pTangentControls = self.addParam("tangentControls", "bool", False)
        self.pChickenStyleIk = self.addParam("chickenStyleIK", "bool", True)
        self.pIKWorldOri = self.addParam("IKWorldOri", "bool", False)

        # FCurves
        self.pSt_profile = self.addFCurveParam(
            "st_profile", [[0, 0], [.5, -1], [1, 0]])

        self.pSq_profile = self.addFCurveParam(
            "sq_profile", [[0, 0], [.5, 1], [1, 0]])

        self.pUseIndex = self.addParam("useIndex", "bool", False)

        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None)

    def get_divisions(self):
        """ Returns correct segments divisions """

        self.divisions = self.root.division.get() + 1

        return self.divisions


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
        self.settingsTab.softness_slider.setValue(
            int(self.root.attr("softness").get() * 100))

        self.settingsTab.softness_spinBox.setValue(
            int(self.root.attr("softness").get() * 100))

        self.settingsTab.maxStretch_spinBox.setValue(
            self.root.attr("maxstretch").get())

        self.settingsTab.maxSquash_spinBox.setValue(
            self.root.attr("maxsquash").get())

        self.settingsTab.division_spinBox.setValue(
            self.root.attr("division").get())

        self.populateCheck(self.settingsTab.tangentControls_checkBox,
                           "tangentControls")

        self.populateCheck(self.settingsTab.chickenStyleIK_checkBox,
                           "chickenStyleIK")

        self.populateCheck(self.settingsTab.IKWorldOri_checkBox,
                           "IKWorldOri")

        ikRefArrayItems = self.root.attr("ikrefarray").get().split(",")
        for item in ikRefArrayItems:
            self.settingsTab.ikRefArray_listWidget.addItem(item)
        headRefArrayItems = self.root.attr("headrefarray").get().split(",")
        for item in headRefArrayItems:
            self.settingsTab.headRefArray_listWidget.addItem(item)

    def create_componentLayout(self):

        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)

        self.setLayout(self.settings_layout)

    def create_componentConnections(self):

        self.settingsTab.softness_slider.valueChanged.connect(
            partial(self.updateSlider,
                    self.settingsTab.softness_slider,
                    "softness"))

        self.settingsTab.softness_spinBox.valueChanged.connect(
            partial(self.updateSlider,
                    self.settingsTab.softness_spinBox,
                    "softness"))

        self.settingsTab.maxStretch_spinBox.valueChanged.connect(
            partial(self.updateSpinBox,
                    self.settingsTab.maxStretch_spinBox,
                    "maxstretch"))

        self.settingsTab.maxSquash_spinBox.valueChanged.connect(
            partial(self.updateSpinBox,
                    self.settingsTab.maxSquash_spinBox,
                    "maxsquash"))

        self.settingsTab.division_spinBox.valueChanged.connect(
            partial(self.updateSpinBox,
                    self.settingsTab.division_spinBox,
                    "division"))

        self.settingsTab.tangentControls_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.tangentControls_checkBox,
                    "tangentControls"))

        self.settingsTab.chickenStyleIK_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.chickenStyleIK_checkBox,
                    "chickenStyleIK"))

        self.settingsTab.IKWorldOri_checkBox.stateChanged.connect(
            partial(self.updateCheck,
                    self.settingsTab.IKWorldOri_checkBox,
                    "IKWorldOri"))

        self.settingsTab.squashStretchProfile_pushButton.clicked.connect(
            self.setProfile)

        self.settingsTab.ikRefArrayAdd_pushButton.clicked.connect(
            partial(self.addItem2listWidget,
                    self.settingsTab.ikRefArray_listWidget,
                    "ikrefarray"))

        self.settingsTab.ikRefArrayRemove_pushButton.clicked.connect(
            partial(self.removeSelectedFromListWidget,
                    self.settingsTab.ikRefArray_listWidget,
                    "ikrefarray"))

        self.settingsTab.ikRefArray_copyRef_pushButton.clicked.connect(
            partial(self.copyFromListWidget,
                    self.settingsTab.headRefArray_listWidget,
                    self.settingsTab.ikRefArray_listWidget,
                    "ikrefarray"))

        self.settingsTab.ikRefArray_listWidget.installEventFilter(self)

        self.settingsTab.headRefArrayAdd_pushButton.clicked.connect(
            partial(self.addItem2listWidget,
                    self.settingsTab.headRefArray_listWidget,
                    "headrefarray"))

        self.settingsTab.headRefArrayRemove_pushButton.clicked.connect(
            partial(self.removeSelectedFromListWidget,
                    self.settingsTab.headRefArray_listWidget,
                    "headrefarray"))

        self.settingsTab.headRefArray_copyRef_pushButton.clicked.connect(
            partial(self.copyFromListWidget,
                    self.settingsTab.ikRefArray_listWidget,
                    self.settingsTab.headRefArray_listWidget,
                    "headrefarray"))

        self.settingsTab.headRefArray_listWidget.installEventFilter(self)

    def eventFilter(self, sender, event):
        if event.type() == QtCore.QEvent.ChildRemoved:
            if sender == self.settingsTab.ikRefArray_listWidget:
                self.updateListAttr(sender, "ikrefarray")
            elif sender == self.settingsTab.headRefArray_listWidget:
                self.updateListAttr(sender, "headrefarray")
            return True
        else:
            return QtWidgets.QDialog.eventFilter(self, sender, event)

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
