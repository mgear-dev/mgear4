"""Guide Squash 01 module"""

from functools import partial

from mgear.shifter.component import guide
from mgear.core import transform, pyqt
from mgear.vendor.Qt import QtWidgets, QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

from . import settingsUI as sui

# guide info
AUTHOR = "Miquel Campos"
URL = "www.mcsgear.com"
EMAIL = ""
VERSION = [1, 0, 0]
TYPE = "squash_01"
NAME = "squash"
DESCRIPTION = "Linear squash component"

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

        self.save_transform = ["root", "tip"]
        self.save_blade = ["blade"]

    def addObjects(self):
        """Add the Guide Root, blade and locators"""

        self.root = self.addRoot()
        vTemp = transform.getOffsetPosition(self.root, [2, 0, 0])
        self.loc = self.addLoc("tip", self.root, vTemp)
        self.blade = self.addBlade("blade", self.root, self.loc)

        centers = [self.root, self.loc]
        self.dispcrv = self.addDispCurve("crv", centers)

    def addParameters(self):
        """Add the configurations settings"""

        self.pRefArray = self.addParam("ikrefarray", "string", "")
        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam("parentJointIndex",
                                               "long",
                                               -1,
                                               None,
                                               None)
        self.pSquashX = self.addParam("squashX", "double", 1, 0, 1)
        self.pSquashY = self.addParam("squashY", "double", 1, 0, 1)
        self.pSquashZ = self.addParam("squashZ", "double", 1, 0, 1)
        self.pStretchX = self.addParam("stretchX", "double", 1, 0, 1)
        self.pStretchY = self.addParam("stretchY", "double", 1, 0, 1)
        self.pStretchZ = self.addParam("stretchZ", "double", 1, 0, 1)

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
        self.resize(350, 350)

    def create_componentControls(self):
        return

    def populate_componentControls(self):
        """Populate the controls values.

        Populate the controls values from the custom attributes of the
        component.

        """
        # populate tab
        self.tabs.insertTab(1, self.settingsTab, "Component Settings")

        refArrayItems = self.root.attr("ikrefarray").get().split(",")
        for item in refArrayItems:
            self.settingsTab.refArray_listWidget.addItem(item)

        self.settingsTab.squashX_slider.setValue(int(self.root.attr("squashX").get() * 100))
        self.settingsTab.squashX_spinBox.setValue(int(self.root.attr("squashX").get() * 100))

        self.settingsTab.squashY_slider.setValue(int(self.root.attr("squashY").get() * 100))
        self.settingsTab.squashY_spinBox.setValue(int(self.root.attr("squashY").get() * 100))

        self.settingsTab.squashZ_slider.setValue(int(self.root.attr("squashZ").get() * 100))
        self.settingsTab.squashZ_spinBox.setValue(int(self.root.attr("squashZ").get() * 100))


        self.settingsTab.stretchX_slider.setValue(int(self.root.attr("stretchX").get() * 100))
        self.settingsTab.stretchX_spinBox.setValue(int(self.root.attr("stretchX").get() * 100))

        self.settingsTab.stretchY_slider.setValue(int(self.root.attr("stretchY").get() * 100))
        self.settingsTab.stretchY_spinBox.setValue(int(self.root.attr("stretchY").get() * 100))

        self.settingsTab.stretchZ_slider.setValue(int(self.root.attr("stretchZ").get() * 100))
        self.settingsTab.stretchZ_spinBox.setValue(int(self.root.attr("stretchZ").get() * 100))



    def create_componentLayout(self):

        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)

        self.setLayout(self.settings_layout)

    def create_componentConnections(self):

        self.settingsTab.refArrayAdd_pushButton.clicked.connect(
            partial(self.addItem2listWidget,
                    self.settingsTab.refArray_listWidget,
                    "ikrefarray"))
        self.settingsTab.refArrayRemove_pushButton.clicked.connect(
            partial(self.removeSelectedFromListWidget,
                    self.settingsTab.refArray_listWidget,
                    "ikrefarray"))
        self.settingsTab.refArray_listWidget.installEventFilter(self)

        self.settingsTab.squashX_slider.valueChanged.connect(partial(self.updateSlider, self.settingsTab.squashX_slider, "squashX"))
        self.settingsTab.squashX_spinBox.valueChanged.connect(partial(self.updateSlider, self.settingsTab.squashX_spinBox, "squashX"))

        self.settingsTab.squashY_slider.valueChanged.connect(partial(self.updateSlider, self.settingsTab.squashY_slider, "squashY"))
        self.settingsTab.squashY_spinBox.valueChanged.connect(partial(self.updateSlider, self.settingsTab.squashY_spinBox, "squashY"))

        self.settingsTab.squashZ_slider.valueChanged.connect(partial(self.updateSlider, self.settingsTab.squashZ_slider, "squashZ"))
        self.settingsTab.squashZ_spinBox.valueChanged.connect(partial(self.updateSlider, self.settingsTab.squashZ_spinBox, "squashZ"))

        self.settingsTab.stretchX_slider.valueChanged.connect(partial(self.updateSlider, self.settingsTab.stretchX_slider, "stretchX"))
        self.settingsTab.stretchX_spinBox.valueChanged.connect(partial(self.updateSlider, self.settingsTab.stretchX_spinBox, "stretchX"))

        self.settingsTab.stretchY_slider.valueChanged.connect(partial(self.updateSlider, self.settingsTab.stretchY_slider, "stretchY"))
        self.settingsTab.stretchY_spinBox.valueChanged.connect(partial(self.updateSlider, self.settingsTab.stretchY_spinBox, "stretchY"))

        self.settingsTab.stretchZ_slider.valueChanged.connect(partial(self.updateSlider, self.settingsTab.stretchZ_slider, "stretchZ"))
        self.settingsTab.stretchZ_spinBox.valueChanged.connect(partial(self.updateSlider, self.settingsTab.stretchZ_spinBox, "stretchZ"))

    def eventFilter(self, sender, event):
        if event.type() == QtCore.QEvent.ChildRemoved:
            if sender == self.settingsTab.refArray_listWidget:
                self.updateListAttr(sender, "ikrefarray")
            return True
        else:
            return QtWidgets.QDialog.eventFilter(self, sender, event)

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
