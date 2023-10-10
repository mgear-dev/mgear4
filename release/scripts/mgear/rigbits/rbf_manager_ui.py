#!/usr/bin/env python
"""
A tool to manage a number of rbf type nodes under a user defined setup(name)

Steps -
    set Driver
    set Control for driver(optional, recommended)
    select attributes to driver RBF nodes
    Select Node to be driven in scene(Animation control, transform)
    Name newly created setup
    select attributes to be driven by the setup
    add any additional driven nodes
    position driver(via the control)
    position the driven node(s)
    select add pose

Add notes -
Please ensure the driver node is NOT in the same position more than once. This
will cause the RBFNode to fail while calculating. This can be fixed by deleting
any two poses with the same input values.

Edit Notes -
Edit a pose by selecting "pose #" in the table. (which recalls recorded pose)
reposition any controls involved in the setup
select "Edit Pose"

Delete notes -
select desired "pose #"
select "Delete Pose"

Mirror notes -
setups/Controls will succefully mirror if they have had their inverseAttrs
configured previously.

2.0 -------
LOOK into coloring the pose and how close it is
import replace name support (will work through json manually)
support live connections
settings support for suffix, etc
rename existing setup
newScene callback

Attributes:
    CTL_SUFFIX (str): suffix for anim controls
    DRIVEN_SUFFIX (str): suffix for driven group nodes
    EXTRA_MODULE_DICT (str): name of the dict which holds additional modules
    MGEAR_EXTRA_ENVIRON (str): environment variable to query for paths
    TOOL_NAME (str): name of UI
    TOOL_TITLE (str): title as it appears in the ui
    __version__ (float): UI version

Deleted Attributes:
    RBF_MODULES (dict): of supported rbf modules

__author__ = "Rafael Villar"
__email__ = "rav@ravrigs.com"
__credits__ = ["Miquel Campos", "Ingo Clemens"]

"""
# python
import imp
import os
from functools import partial

# core
import maya.cmds as mc
import pymel.core as pm
import maya.OpenMaya as om
import maya.OpenMayaUI as mui

# mgear
import mgear
from mgear.core import pyqt
import mgear.core.string as mString
from mgear.core import anim_utils
from mgear.vendor.Qt import QtWidgets, QtCore, QtCompat
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

# rbf
from . import rbf_io
from . import rbf_node
from .six import PY2


# =============================================================================
# Constants
# =============================================================================
__version__ = "1.0.8"

_mgear_version = mgear.getVersion()
TOOL_NAME = "RBF Manager"
TOOL_TITLE = "{} v{} | mGear {}".format(TOOL_NAME, __version__, _mgear_version)
UI_NAME = "RBFManagerUI"
WORK_SPACE_NAME = UI_NAME + "WorkspaceControl"

DRIVEN_SUFFIX = rbf_node.DRIVEN_SUFFIX
CTL_SUFFIX = rbf_node.CTL_SUFFIX

MGEAR_EXTRA_ENVIRON = "MGEAR_RBF_EXTRA"
EXTRA_MODULE_DICT = "extraFunc_dict"

MIRROR_SUFFIX = "_mr"

# =============================================================================
# general functions
# =============================================================================


def testFunctions(*args):
    """test function for connecting signals during debug

    Args:
        *args: Description
    """
    print('!!', args)


def getPlugAttrs(nodes, attrType="keyable"):
    """Get a list of attributes to display to the user

    Args:
        nodes (str): name of node to attr query
        keyable (bool, optional): should the list only be kayable attrs

    Returns:
        list: list of attrplugs
    """
    plugAttrs = []
    for node in nodes:
        if attrType == "all":
            attrs = mc.listAttr(node, se=True, u=False)
            aliasAttrs = mc.aliasAttr(node, q=True)
            if aliasAttrs is not None:
                try:
                    attrs.extend(aliasAttrs[0::2])
                except Exception:
                    pass
        elif attrType == "cb":
            attrs = mc.listAttr(node, se=True, u=False, cb=True)
        elif attrType == "keyable":
            attrs = mc.listAttr(node, se=True, u=False, keyable=True)
        if attrs is None:
            continue
        [plugAttrs.append("{}.{}".format(node, a)) for a in attrs]
    return plugAttrs


def existing_rbf_setup(node):
    """check if there is an existing rbf setup associated with the node

    Args:
        node (str): name of the node to query

    Returns:
        list: of the rbftype assiociated with the node
    """
    connected_nodes = mc.listConnections(node,
                                         destination=True,
                                         shapes=True,
                                         scn=True) or []
    connected_node_types = set(mc.nodeType(x) for x in connected_nodes)
    rbf_node_types = set(rbf_io.RBF_MODULES.keys())
    return list(connected_node_types.intersection(rbf_node_types))


def sortRBF(name, rbfType=None):
    """Get node wrapped in RBFNode class based on the type of node

    Args:
        name (str): name of the RBFNode in scene
        rbfType (str, optional): type of RBF to get instance from

    Returns:
        RBFNode: instance of RBFNode
    """
    if mc.objExists(name) and mc.nodeType(name) in rbf_io.RBF_MODULES:
        rbfType = mc.nodeType(name)
        return rbf_io.RBF_MODULES[rbfType].RBFNode(name)
    elif rbfType is not None:
        return rbf_io.RBF_MODULES[rbfType].RBFNode(name)


def getEnvironModules():
    """if there are any environment variables set that load additional
    modules for the UI, query and return dict

    Returns:
        dict: displayName:funcObject
    """
    extraModulePath = os.environ.get(MGEAR_EXTRA_ENVIRON, None)
    if extraModulePath is None or not os.path.exists(extraModulePath):
        return None
    exModule = imp.load_source(MGEAR_EXTRA_ENVIRON,
                               os.path.abspath(extraModulePath))
    additionalFuncDict = getattr(exModule, EXTRA_MODULE_DICT, None)
    if additionalFuncDict is None:
        mc.warning("'{}' not found in {}".format(EXTRA_MODULE_DICT,
                                                 extraModulePath))
        print("No additional menu items added to {}".format(TOOL_NAME))
    return additionalFuncDict


def selectNode(name):
    """Convenience function, to ensure no errors when selecting nodes in UI

    Args:
        name (str): name of node to be selected
    """
    if mc.objExists(name):
        mc.select(name)
    else:
        print(name, "No longer exists for selection!")


# =============================================================================
# UI General Functions
# =============================================================================

def getControlAttrWidget(nodeAttr, label=""):
    """Create a cmds.attrControlGrp and wrap it in a qtWidget, preserving its connection
    to the specified attr

    Args:
        nodeAttr (str): node.attr, the target for the attrControlGrp
        label (str, optional): name for the attr widget

    Returns:
        QtWidget.QLineEdit: A Qt widget created from attrControlGrp
        str: The name of the created Maya attrControlGrp
    """
    mAttrFeild = mc.attrControlGrp(attribute=nodeAttr, label=label, po=True)

    # Convert the Maya control to a Qt pointer
    ptr = mui.MQtUtil.findControl(mAttrFeild)

    # Wrap the Maya control into a Qt widget, considering Python version
    controlWidget = QtCompat.wrapInstance(long(ptr) if PY2 else int(ptr), base=QtWidgets.QWidget)
    controlWidget.setContentsMargins(0, 0, 0, 0)
    controlWidget.setMinimumWidth(0)

    attrEdit = [wdgt for wdgt in controlWidget.children() if type(wdgt) == QtWidgets.QLineEdit]
    [wdgt.setParent(attrEdit[0]) for wdgt in controlWidget.children()
     if type(wdgt) == QtCore.QObject]

    attrEdit[0].setParent(None)
    controlWidget.setParent(attrEdit[0])
    controlWidget.setHidden(True)
    return attrEdit[0], mAttrFeild


def HLine():
    """seporator line for widgets

    Returns:
        Qframe: line for seperating UI elements visually
    """
    seperatorLine = QtWidgets.QFrame()
    seperatorLine.setFrameShape(QtWidgets.QFrame.HLine)
    seperatorLine.setFrameShadow(QtWidgets.QFrame.Sunken)
    return seperatorLine


def VLine():
    """seporator line for widgets

    Returns:
        Qframe: line for seperating UI elements visually
    """
    seperatorLine = QtWidgets.QFrame()
    seperatorLine.setFrameShape(QtWidgets.QFrame.VLine)
    seperatorLine.setFrameShadow(QtWidgets.QFrame.Sunken)
    return seperatorLine


def show(dockable=True, newSceneCallBack=True, *args):
    """To launch the UI and ensure any previously opened instance is closed.

    Returns:
        DistributeUI: instance

    Args:
        *args: Description
        :param newSceneCallBack:
        :param dockable:
    """
    global RBF_UI  # Ensure we have access to the global variable

    # Attempt to close any existing UI with the given name
    if mc.workspaceControl(WORK_SPACE_NAME, exists=True):
        mc.deleteUI(WORK_SPACE_NAME)

    # Create the UI
    RBF_UI = RBFManagerUI(newSceneCallBack=newSceneCallBack)
    RBF_UI.initializePoseControlWidgets()

    # Check if we've saved a size previously and set it
    if mc.optionVar(exists='RBF_UI_width') and mc.optionVar(exists='RBF_UI_height'):
        saved_width = mc.optionVar(query='RBF_UI_width')
        saved_height = mc.optionVar(query='RBF_UI_height')
        RBF_UI.resize(saved_width, saved_height)

    # Show the UI.
    RBF_UI.show(dockable=dockable)
    return RBF_UI


def genericWarning(parent, warningText):
    """generic prompt warning with the provided text

    Args:
        parent (QWidget): Qwidget to be parented under
        warningText (str): information to display to the user

    Returns:
        QtCore.Response: of what the user chose. For warnings
    """
    selWarning = QtWidgets.QMessageBox(parent)
    selWarning.setText(warningText)
    results = selWarning.exec_()
    return results


def promptAcceptance(parent, descriptionA, descriptionB):
    """Warn user, asking for permission

    Args:
        parent (QWidget): to be parented under
        descriptionA (str): info
        descriptionB (str): further info

    Returns:
        QtCore.Response: accept, deline, reject
    """
    msgBox = QtWidgets.QMessageBox(parent)
    msgBox.setText(descriptionA)
    msgBox.setInformativeText(descriptionB)
    msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok |
                              QtWidgets.QMessageBox.Cancel)
    msgBox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
    decision = msgBox.exec_()
    return decision


class ClickableLineEdit(QtWidgets.QLineEdit):

    """subclass to allow for clickable lineEdit, as a button

    Attributes:
        clicked (QtCore.Signal): emitted when clicked
    """

    clicked = QtCore.Signal(str)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.text())
        else:
            super(ClickableLineEdit, self).mousePressEvent(event)


class TabBar(QtWidgets.QTabBar):
    """Subclass to get a taller tab widget, for readability
    """

    def __init__(self):
        super(TabBar, self).__init__()

    def tabSizeHint(self, index):
        width = QtWidgets.QTabBar.tabSizeHint(self, index).width()
        return QtCore.QSize(width, 25)


class RBFManagerUI(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):

    """A manager for creating, mirroring, importing/exporting poses created
    for RBF type nodes.

    Attributes:
        absWorld (bool): Type of pose info look up, world vs local
        addRbfButton (QPushButton): button for adding RBFs to setup
        allSetupsInfo (dict): setupName:[of all the RBFNodes in scene]
        attrMenu (TYPE): Description
        currentRBFSetupNodes (list): currently selected setup nodes(userSelect)
        driverPoseTableWidget (QTableWidget): poseInfo for the driver node
        genericWidgetHight (int): convenience to adjust height of all buttons
        mousePosition (QPose): if tracking mouse position on UI
        rbfTabWidget (QTabWidget): where the driven table node info is
        displayed
    """

    mousePosition = QtCore.Signal(int, int)

    def __init__(self, parent=pyqt.maya_main_window(), hideMenuBar=False, newSceneCallBack=True):
        super(RBFManagerUI, self).__init__(parent=parent)
        # UI info -------------------------------------------------------------
        self.callBackID = None
        self.setWindowTitle(TOOL_TITLE)
        self.setObjectName(UI_NAME)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.genericWidgetHight = 24
        # class info ----------------------------------------------------------
        self.absWorld = True
        self.zeroedDefaults = True
        self.currentRBFSetupNodes = []
        self.allSetupsInfo = None
        self.drivenWidget = []
        self.driverAutoAttr = []
        self.drivenAutoAttr = []

        self.setMenuBar(self.createMenuBar(hideMenuBar=hideMenuBar))
        self.setCentralWidget(self.createCentralWidget())
        self.centralWidget().setMouseTracking(True)
        self.refreshRbfSetupList()
        self.connectSignals()
        # added because the dockableMixin makes the ui appear small
        self.adjustSize()
        self.resize(800, 650)
        if newSceneCallBack:
            self.newSceneCallBack()

    def closeEvent(self, event):
        """Overridden close event to save the size of the UI."""
        width = self.width()
        height = self.height()

        # Save the size to Maya's optionVars
        mc.optionVar(intValue=('RBF_UI_width', width))
        mc.optionVar(intValue=('RBF_UI_height', height))

        # Call the parent class's closeEvent
        super(RBFManagerUI, self).closeEvent(event)

    def callBackFunc(self, *args):
        """super safe function for trying to refresh the UI, should anything
        fail.

        Args:
            *args: Description
        """
        try:
            self.refresh()
        except Exception:
            pass

    def removeSceneCallback(self):
        """remove the callback associated witht he UI, quietly fail.
        """
        try:
            om.MSceneMessage.removeCallback(self.callBackID)
        except Exception as e:
            print("CallBack removal failure:")
            print(e)

    def newSceneCallBack(self):
        """create a new scene callback to refresh the UI when scene changes.
        """
        callBackType = om.MSceneMessage.kSceneUpdate
        try:
            func = self.callBackFunc
            obj = om.MSceneMessage.addCallback(callBackType, func)
            self.callBackID = obj
        except Exception as e:
            print(e)
            self.callBackID = None

    # general functions -------------------------------------------------------
    def getSelectedSetup(self):
        """return the string name of the selected setup from user and type

        Returns:
            str, str: name, nodeType
        """
        selectedSetup = self.rbf_cbox.currentText()
        if selectedSetup.startswith("New"):
            setupType = selectedSetup.split(" ")[1]
            return None, setupType
        else:
            return selectedSetup, self.currentRBFSetupNodes[0].rbfType

    def getDrivenNodesFromSetup(self):
        """based on the user selected setup, get the associated RBF nodes

        Returns:
            list: driven rbfnodes
        """
        drivenNodes = []
        for rbfNode in self.currentRBFSetupNodes:
            drivenNodes.extend(rbfNode.getDrivenNode)
        return drivenNodes

    def __deleteSetup(self):
        decision = promptAcceptance(self,
                                    "Delete current Setup?",
                                    "This will delete all RBF nodes in setup.")
        if decision in [QtWidgets.QMessageBox.Discard,
                        QtWidgets.QMessageBox.Cancel]:
            return
        self.deleteSetup()

    def deleteSetup(self, setupName=None):
        """Delete all the nodes within a setup.

        Args:
            setupName (None, optional): Description
        """
        setupType = None
        if setupName is None:
            setupName, setupType = self.getSelectedSetup()
        nodesToDelete = self.allSetupsInfo.get(setupName, [])
        for rbfNode in nodesToDelete:
            drivenNode = rbfNode.getDrivenNode()
            rbfNode.deleteRBFToggleAttr()
            if drivenNode:
                rbf_node.removeDrivenGroup(drivenNode[0])
            mc.delete(rbfNode.transformNode)
        self.refresh()

    def removeRBFFromSetup(self, drivenWidgetIndex):
        """remove RBF tab from setup. Delete driven group, attrs and clean up

        Args:
            drivenWidgetIndex (QWidget): parent widget that houses the contents
            and info of the rbf node

        Returns:
            n/a: n/a
        """
        decision = promptAcceptance(self,
                                    "Are you sure you want to remove node?",
                                    "This will delete the RBF & driven node.")
        if decision in [QtWidgets.QMessageBox.Discard,
                        QtWidgets.QMessageBox.Cancel]:
            return
        drivenWidget = self.rbfTabWidget.widget(drivenWidgetIndex)
        self.rbfTabWidget.removeTab(drivenWidgetIndex)
        rbfNode = getattr(drivenWidget, "rbfNode")
        self.__deleteAssociatedWidgets(drivenWidget, attrName="associated")
        drivenWidget.deleteLater()
        drivenNode = rbfNode.getDrivenNode()
        rbfNode.deleteRBFToggleAttr()
        if drivenNode and drivenNode[0].endswith(rbf_node.DRIVEN_SUFFIX):
            rbf_node.removeDrivenGroup(drivenNode[0])
        mc.delete(rbfNode.transformNode)
        self.currentRBFSetupNodes.remove(rbfNode)
        if self.rbfTabWidget.count() == 0:
            self.refresh(rbfSelection=True,
                         driverSelection=True,
                         drivenSelection=True,
                         currentRBFSetupNodes=True)
        else:
            self.refreshAllTables()

    def addRBFToSetup(self):
        """query the user in case of a new setup or adding additional RBFs to
        existing.

        Returns:
            TYPE: Description
        """
        result = self.preValidationCheck()

        driverControl = result["driverControl"]
        driverNode, drivenNode = result["driverNode"], result["drivenNode"]
        driverAttrs, drivenAttrs = result["driverAttrs"], result["drivenAttrs"]

        drivenType = mc.nodeType(drivenNode)
        if drivenType in ["transform", "joint"]:
            drivenNode_name = rbf_node.get_driven_group_name(drivenNode)
        else:
            drivenNode_name = drivenNode

        # Check if there is an existing rbf node attached
        if mc.objExists(drivenNode_name):
            if existing_rbf_setup(drivenNode_name):
                msg = "Node is already driven by an RBF Setup."
                genericWarning(self, msg)
                return

        setupName, rbfType = self.getSelectedSetup()

        parentNode = False
        if drivenType in ["transform", "joint"]:
            parentNode = True
            drivenNode = rbf_node.addDrivenGroup(drivenNode)

        # Create RBFNode instance, apply settings
        if not setupName:
            setupName = "{}_WD".format(driverNode)
        rbfNode = sortRBF(drivenNode, rbfType=rbfType)
        rbfNode.setSetupName(setupName)
        rbfNode.setDriverControlAttr(driverControl)
        rbfNode.setDriverNode(driverNode, driverAttrs)
        defaultVals = rbfNode.setDrivenNode(drivenNode, drivenAttrs, parent=parentNode)

        # Check if there are any preexisting nodes in setup, if so copy pose index
        if self.currentRBFSetupNodes:
            currentRbfs = self.currentRBFSetupNodes[0]
            print("Syncing poses indices from  {} >> {}".format(currentRbfs, rbfNode))
            rbfNode.syncPoseIndices(self.currentRBFSetupNodes[0])
        else:
            if self.zeroedDefaults:
                rbfNode.applyDefaultPose()
            else:
                poseInputs = rbf_node.getMultipleAttrs(driverNode, driverAttrs)
                rbfNode.addPose(poseInput=poseInputs, poseValue=defaultVals[1::2])

            self.populateDriverInfo(rbfNode, rbfNode.getNodeInfo())
            self.populateDrivenInfo(rbfNode, rbfNode.getNodeInfo())

        # Add newly created RBFNode to list of current
        self.addPoseButton.setEnabled(True)

        self.currentRBFSetupNodes.append(rbfNode)
        self.refreshRbfSetupList(setToSelection=setupName)
        self.lockDriverWidgets()
        mc.select(driverControl)

    def preValidationCheck(self):
        # Fetch data from UI fields
        driverNode = self.driverLineEdit.text()
        drivenNode = self.drivenLineEdit.text()
        driverControl = self.controlLineEdit.text()
        driverSelectedAttrItems = self.driverAttributesWidget.selectedItems()
        drivenSelectedAttrItems = self.drivenAttributesWidget.selectedItems()

        # Create a default return dictionary with None values
        result = {
            "driverNode": None,
            "drivenNode": None,
            "driverControl": None,
            "driverAttrs": None,
            "drivenAttrs": None
        }

        # Ensure driverNode and drivenNode are provided
        if not driverNode or not drivenNode:
            return result

        # Ensure attributes are selected in the widgets
        if not driverSelectedAttrItems or not drivenSelectedAttrItems:
            return result

        # Check if the driven node is the same as the driver node
        if drivenNode == driverNode:
            genericWarning(self, "Select Node to be driven!")
            return result

        # Update the result dictionary with the fetched values
        result["driverNode"] = driverNode
        result["drivenNode"] = drivenNode
        result["driverControl"] = driverControl
        result["driverAttrs"] = [item.text().split(".")[1] for item in driverSelectedAttrItems]
        result["drivenAttrs"] = [item.text().split(".")[1] for item in drivenSelectedAttrItems]

        return result

    def refreshAllTables(self):
        """Convenience function to refresh all the tables on all the tabs
        with latest information.
        """
        weightInfo = None
        rbfNode = None
        for index in range(self.rbfTabWidget.count()):
            drivenWidget = self.rbfTabWidget.widget(index)
            drivenNodeName = drivenWidget.property("drivenNode")
            for rbfNode in self.currentRBFSetupNodes:
                drivenNodes = rbfNode.getDrivenNode()
                if drivenNodes and drivenNodes[0] != drivenNodeName:
                    continue
                weightInfo = rbfNode.getNodeInfo()
                self.setDrivenTable(drivenWidget, rbfNode, weightInfo)
        if weightInfo and rbfNode:
            self.populateDriverInfo(rbfNode, weightInfo)

    @staticmethod
    def determineAttrType(node):
        nodeType = mc.nodeType(node)
        if nodeType in ["transform", "joint"]:
            keyAttrs = mc.listAttr(node, keyable=True) or []
            requiredAttrs = [
                "{}{}".format(attrType, xyz)
                for xyz in "XYZ"
                for attrType in ["translate", "rotate", "scale"]
            ]

            if not any(attr in keyAttrs for attr in requiredAttrs):
                return "cb"
            return "keyable"
        return "all"

    def deletePose(self):
        """delete a pose from the UI and all the RBFNodes in the setup.

        Returns:
            n/a: n/a
        """
        driverRow = self.driverPoseTableWidget.currentRow()
        drivenWidget = self.rbfTabWidget.currentWidget()
        drivenTableWidget = getattr(drivenWidget, "tableWidget")
        drivenRow = drivenTableWidget.currentRow()
        # TODO if one is allow syncing of nodes of different lengths
        # it should be done here
        if drivenRow != driverRow or drivenRow == -1:
            genericWarning(self, "Select Pose # to be deleted.")
            return

        for rbfNode in self.currentRBFSetupNodes:
            rbfNode.deletePose(indexToPop=drivenRow)
        self.refreshAllTables()

    def editPose(self):
        """edit an existing pose. Specify the index

        Returns:
            TYPE: Description
        """
        rbfNodes = self.currentRBFSetupNodes
        if not rbfNodes:
            return
        driverRow = self.driverPoseTableWidget.currentRow()
        drivenWidget = self.rbfTabWidget.currentWidget()
        drivenTableWidget = getattr(drivenWidget, "tableWidget")
        drivenRow = drivenTableWidget.currentRow()
        if drivenRow != driverRow or drivenRow == -1:
            genericWarning(self, "Select Pose # to be Edited.")
            return
        driverNode = rbfNodes[0].getDriverNode()[0]
        driverAttrs = rbfNodes[0].getDriverNodeAttributes()
        poseInputs = rbf_node.getMultipleAttrs(driverNode, driverAttrs)
        for rbfNode in rbfNodes:
            poseValues = rbfNode.getPoseValues(resetDriven=True)
            rbfNode.addPose(poseInput=poseInputs,
                            poseValue=poseValues,
                            posesIndex=drivenRow)
            rbfNode.forceEvaluation()
        self.refreshAllTables()

    def editPoseValues(self):
        """Edit an existing pose based on the values in the table
        Returns:
            None
        """
        rbfNodes = self.currentRBFSetupNodes
        if not rbfNodes:
            return
        driverRow = self.driverPoseTableWidget.currentRow() # A number
        drivenWidget = self.rbfTabWidget.currentWidget()
        drivenTableWidget = getattr(drivenWidget, "tableWidget")
        drivenRow = drivenTableWidget.currentRow()
        if drivenRow != driverRow or drivenRow == -1:
            genericWarning(self, "Select Pose # to be Edited.")
            return
        driverNode = rbfNodes[0].getDriverNode()[0]
        driverAttrs = rbfNodes[0].getDriverNodeAttributes()
        poseInputs = rbf_node.getMultipleAttrs(driverNode, driverAttrs)
        # print("poseInputs: " + str(poseInputs))
        # print("RBF nodes: " + str(rbfNodes))
        nColumns = drivenTableWidget.columnCount()
        entryWidgets = [drivenTableWidget.cellWidget(drivenRow, c) for c in range(nColumns)]
        newValues = [float(w.text()) for w in entryWidgets]
        # print("values: " + str(newValues))
        rbfNode = getattr(drivenWidget, "rbfNode")
        rbfNodes = [rbfNode]
        for rbfNode in rbfNodes:
            print("rbfNode: {}".format(rbfNode))
            print("poseInputs: {}".format(poseInputs))
            print("New pose values: {}".format(newValues))
            print("poseIndex: {}".format(drivenRow))
            rbfNode.addPose(poseInput=poseInputs,
                            poseValue=newValues,
                            posesIndex=drivenRow)
            rbfNode.forceEvaluation()
        self.refreshAllTables()

    def updateAllFromTables(self):
        """Update every pose

        Args:
            rbfNode (RBFNode): node for query
            weightInfo (dict): to pull information from, since we have it
        """
        rbfNodes = self.currentRBFSetupNodes
        if not rbfNodes:
            return
        for w in self.rbfTabWidget.count():
            drivenWidget = self.rbfTabWidget.widget(w)
            drivenTableWidget = getattr(drivenWidget, "tableWidget")
        drivenRow = drivenTableWidget.currentRow()
        driverNode = rbfNodes[0].getDriverNode()[0]
        driverAttrs = rbfNodes[0].getDriverNodeAttributes()
        poseInputs = rbf_node.getMultipleAttrs(driverNode, driverAttrs)
        # print("poseInputs: " + str(poseInputs))
        # print("RBF nodes: " + str(rbfNodes))
        nColumns = drivenTableWidget.columnCount()
        entryWidgets = [drivenTableWidget.cellWidget(drivenRow, c) for c in range(nColumns)]
        newValues = [float(w.text()) for w in entryWidgets]
        # print("values: " + str(newValues))
        rbfNode = getattr(drivenWidget, "rbfNode")
        rbfNodes = [rbfNode]
        for rbfNode in rbfNodes:
            # poseValues = rbfNode.getPoseValues()
            # print("Old pose values: " + str(poseValues))
            # print("New pose values: " + str(newValues))
            print("rbfNode: " + str(rbfNode))
            print("poseInputs: " + str(poseInputs))
            print("New pose values: " + str(newValues))
            print("poseIndex: " + str(drivenRow))
            rbfNode.addPose(poseInput=poseInputs,
                            poseValue=newValues,
                            posesIndex=drivenRow)
            rbfNode.forceEvaluation()
        self.refreshAllTables()

    def addPose(self):
        """Add pose to rbf nodes in setup. Additional index on all nodes

        Returns:
            TYPE: Description
        """
        rbfNodes = self.currentRBFSetupNodes
        if not rbfNodes:
            return
        driverNode = rbfNodes[0].getDriverNode()[0]
        driverAttrs = rbfNodes[0].getDriverNodeAttributes()
        poseInputs = rbf_node.getMultipleAttrs(driverNode, driverAttrs)
        for rbfNode in rbfNodes:
            poseValues = rbfNode.getPoseValues(resetDriven=True, absoluteWorld=self.absWorld)
            rbfNode.addPose(poseInput=poseInputs, poseValue=poseValues)
        self.refreshAllTables()

    def updateAllSetupsInfo(self, includeEmpty=False):
        """refresh the instance dictionary of all the setps in the scene.

        Args:
            includeEmpty (bool, optional): there could be rbf nodes with no
            setup names.
        """
        self.allSetupsInfo = {}
        tmp_dict = rbf_node.getRbfSceneSetupsInfo(includeEmpty=includeEmpty)
        for setupName, nodes in tmp_dict.items():
            self.allSetupsInfo[setupName] = [sortRBF(n) for n in nodes]

    def setNodeToField(self, lineEdit, multi=False):
        """take the currently selected node and set its name to the lineedit
        provided

        Args:
            lineEdit (QLineEdit): widget to set the name to
            multi (bool, optional): should multiple nodes be supported

        Returns:
            str: str set to the lineedit
        """
        selected = mc.ls(sl=True)
        if not multi:
            selected = [selected[0]]
        controlNameData = ", ".join(selected)
        lineEdit.setText(controlNameData)
        mc.select(cl=True)
        return controlNameData

    def setDriverControlLineEdit(self):
        selected = mc.ls(sl=True)
        if len(selected) == 2:
            self.controlLineEdit.setText(selected[0])
            self.driverLineEdit.setText(selected[1])
        elif len(selected) == 1:
            self.controlLineEdit.setText(selected[0])
            self.driverLineEdit.setText(selected[0])
        mc.select(cl=True)

    def highlightListEntries(self, listWidget, toHighlight):
        """set the items in a listWidget to be highlighted if they are in list

        Args:
            listWidget (QListWidget): list to highlight items on
            toHighlight (list): of things to highlight
        """
        toHighlight = list(toHighlight)
        scrollToItems = []
        for index in range(listWidget.count()):
            # for qt to check for events like keypress
            item = listWidget.item(index)
            itemText = item.text()
            for desired in toHighlight:
                if desired in itemText:
                    item.setSelected(True)
                    scrollToItems.append(item)
                    toHighlight.remove(desired)
        if scrollToItems:
            listWidget.scrollToItem(scrollToItems[0])

    def setAttributeDisplay(self, attrListWidget, driverName, displayAttrs):
        nodeAttrsToDisplay = ["{}.{}".format(driverName, attr)
                              for attr in displayAttrs]
        attrListWidget.clear()
        attrListWidget.addItems(sorted(nodeAttrsToDisplay))
        self.highlightListEntries(attrListWidget, displayAttrs)

    def setAttributeToAutoSelect(self, attrListWidget):
        selectedItems = attrListWidget.selectedItems()
        selectedTexts = [item.text() for item in selectedItems]
        attributes = [attrPlug.split(".")[-1] for attrPlug in selectedTexts]

        if "driver" in attrListWidget.objectName():
            self.driverAutoAttr = attributes
        elif "driven" in attrListWidget.objectName():
            self.drivenAutoAttr = attributes
        print("driverAutoAttr", self.driverAutoAttr)

    @staticmethod
    def setSelectedForAutoSelect(attrListWidget, itemTexts):
        for i in range(attrListWidget.count()):
            item = attrListWidget.item(i)
            if item.text() in itemTexts:
                item.setSelected(True)

    def updateAttributeDisplay(self,
                               attrListWidget,
                               driverNames,
                               highlight=[],
                               attrType="keyable",
                               force=False):
        """update the provided listwidget with the attrs collected from the
        list of nodes provided

        Args:
            attrListWidget (QListWidget): widget to update
            driverNames (list): of nodes to query for attrs to display
            highlight (list, optional): of item entries to highlight
            keyable (bool, optional): should the displayed attrs be keyable

        Returns:
            n/a: n/a
        """
        nodeAttrsToDisplay = []
        if not driverNames:
            return
        elif type(driverNames) != list:
            driverNames = [driverNames]

        if not force:
            attrType = self.determineAttrType(driverNames[0])

        nodeAttrsToDisplay = getPlugAttrs(driverNames, attrType=attrType)
        attrListWidget.clear()
        attrListWidget.addItems(nodeAttrsToDisplay)

        objName = attrListWidget.objectName()
        autoAttrs = {
            "driverListWidget": self.driverAutoAttr, "drivenListWidget": self.drivenAutoAttr
        }

        if autoAttrs[objName]:
            attrPlugs = ["{}.{}".format(driverNames[0], attr) for attr in autoAttrs[objName]]
            print(attrPlugs)
            self.setSelectedForAutoSelect(attrListWidget, attrPlugs)

        if highlight:
            self.highlightListEntries(attrListWidget, highlight)

    @staticmethod
    def __deleteAssociatedWidgetsMaya(widget, attrName="associatedMaya"):
        """delete core ui items 'associated' with the provided widgets

        Args:
            widget (QWidget): Widget that has the associated attr set
            attrName (str, optional): class attr to query
        """
        if hasattr(widget, attrName):
            for t in getattr(widget, attrName):
                try:
                    mc.deleteUI(t, ctl=True)
                except Exception:
                    pass
        else:
            setattr(widget, attrName, [])

    @staticmethod
    def __deleteAssociatedWidgets(widget, attrName="associated"):
        """delete widget items 'associated' with the provided widgets

        Args:
            widget (QWidget): Widget that has the associated attr set
            attrName (str, optional): class attr to query
        """
        if hasattr(widget, attrName):
            for t in getattr(widget, attrName):
                try:
                    t.deleteLater()
                except Exception:
                    pass
        else:
            setattr(widget, attrName, [])

    def syncDriverTableCells(self, attrEdit, rbfAttrPlug):
        """When you edit the driver table, it will update all the sibling
        rbf nodes in the setup.

        Args:
            attrEdit (QLineEdit): cell that was edited in the driver table
            rbfAttrPlug (str): node.attr the cell represents
            *args: signal throws additional args
        """
        attr = rbfAttrPlug.partition(".")[2]
        value = attrEdit.text()
        for rbfNode in self.currentRBFSetupNodes:
            attrPlug = "{}.{}".format(rbfNode, attr)
            mc.setAttr(attrPlug, float(value))
            rbfNode.forceEvaluation()

    def initializePoseControlWidgets(self):
        """Initialize UI widgets for each pose input based on the information from RBF nodes.
        This dynamically creates widgets for the control attributes associated with each pose.
        """
        # Retrieve all the RBF nodes from the stored setups info
        rbfNodes = self.allSetupsInfo.values()

        # Loop through each RBF node to extract its weight information
        for rbfNode in rbfNodes:
            weightInfo = rbfNode[0].getNodeInfo()

            # Extract pose information from the weight data
            poses = weightInfo.get("poses", None)
            if not poses:
                continue
            # Enumerate through each pose input for this RBF node
            for rowIndex, poseInput in enumerate(poses["poseInput"]):
                for columnIndex, pValue in enumerate(poseInput):
                    rbfAttrPlug = "{}.poses[{}].poseInput[{}]".format(rbfNode[0], rowIndex, columnIndex)

                    # Create a control widget for this pose input attribute
                    getControlAttrWidget(rbfAttrPlug, label="")

    def setDriverTable(self, rbfNode, weightInfo):
        """Set the driverTable widget with the information from the weightInfo

        Args:
            rbfNode (RBFNode): node to query additional info from
            weightInfo (dict): to pull information from

        Returns:
            n/a: n/a
        """
        poses = weightInfo["poses"]

        # ensure deletion of associated widgets with this parent widget
        self.__deleteAssociatedWidgetsMaya(self.driverPoseTableWidget)
        self.__deleteAssociatedWidgets(self.driverPoseTableWidget)
        self.driverPoseTableWidget.clear()

        # Configure columns and headers
        columnLen = len(weightInfo["driverAttrs"])
        headerNames = weightInfo["driverAttrs"]
        self.driverPoseTableWidget.setColumnCount(columnLen)
        self.driverPoseTableWidget.setHorizontalHeaderLabels(headerNames)

        # Configure rows
        poseInputLen = len(poses["poseInput"])
        self.driverPoseTableWidget.setRowCount(poseInputLen)
        if poseInputLen == 0:
            return

        verticalLabels = ["Pose {}".format(index) for index in range(poseInputLen)]
        self.driverPoseTableWidget.setVerticalHeaderLabels(verticalLabels)

        # Populate table cells
        tmpWidgets, mayaUiItems = [], []
        for rowIndex, poseInput in enumerate(poses["poseInput"]):
            for columnIndex, pValue in enumerate(poseInput):
                rbfAttrPlug = "{}.poses[{}].poseInput[{}]".format(rbfNode, rowIndex, columnIndex)
                attrEdit, mAttrField = getControlAttrWidget(rbfAttrPlug, label="")

                self.driverPoseTableWidget.setCellWidget(rowIndex, columnIndex, attrEdit)
                func = partial(self.syncDriverTableCells, attrEdit, rbfAttrPlug)
                attrEdit.returnPressed.connect(func)

                tmpWidgets.append(attrEdit)
                mayaUiItems.append(mAttrField)
        setattr(self.driverPoseTableWidget, "associated", tmpWidgets)
        setattr(self.driverPoseTableWidget, "associatedMaya", mayaUiItems)

    def lockDriverWidgets(self, lock=True):
        """toggle the ability to edit widgets after they have been set

        Args:
            lock (bool, optional): should it be locked
        """
        self.setDriverButton.blockSignals(lock)
        self.setDrivenButton.blockSignals(lock)
        if lock:
            self.driverAttributesWidget.setEnabled(False)
            self.drivenAttributesWidget.setEnabled(False)
        else:
            self.driverAttributesWidget.setEnabled(True)
            self.drivenAttributesWidget.setEnabled(True)

    def populateDriverInfo(self, rbfNode, weightInfo):
        """populate the driver widget, driver, control, driving attrs

        Args:
            rbfNode (RBFNode): node for query
            weightInfo (dict): to pull information from, since we have it
        """
        driverNode = weightInfo.get("driverNode", [None])[0]
        driverControl = weightInfo.get("driverControl", "")
        driverAttrs = weightInfo.get("driverAttrs", [])

        self.driverLineEdit.setText(driverNode or "")
        self.controlLineEdit.setText(driverControl)
        self.setAttributeDisplay(self.driverAttributesWidget, driverNode, driverAttrs)
        self.setDriverTable(rbfNode, weightInfo)

    def populateDrivenInfo(self, rbfNode, weightInfo):
        """populate the driver widget, driver, control, driving attrs

        Args:
            rbfNode (RBFNode): node for query
            weightInfo (dict): to pull information from, since we have it
        """
        # Initialize Driven Widget
        drivenWidget = self.createAndTagDrivenWidget()
        self._associateRBFnodeAndWidget(drivenWidget, rbfNode)

        # Populate Driven Widget Info
        self.populateDrivenWidgetInfo(drivenWidget, weightInfo, rbfNode)

        # Set Driven Node and Attributes
        drivenNode = weightInfo.get("drivenNode", [None])[0]
        self.drivenLineEdit.setText(drivenNode or "")
        self.setAttributeDisplay(self.drivenAttributesWidget, drivenNode or "", weightInfo["drivenAttrs"])

        # Add the driven widget to the tab widget.
        drivenWidget.setProperty("drivenNode", drivenNode)
        self.rbfTabWidget.addTab(drivenWidget, rbfNode.name)
        self.setDrivenTable(drivenWidget, rbfNode, weightInfo)

    @staticmethod
    def _associateRBFnodeAndWidget(tabDrivenWidget, rbfNode):
        """associates the RBFNode with a widget for convenience when adding,
        deleting, editing

        Args:
            tabDrivenWidget (QWidget): tab widget
            rbfNode (RBFNode): instance to be associated
        """
        setattr(tabDrivenWidget, "rbfNode", rbfNode)

    def createAndTagDrivenWidget(self):
        """create and associate a widget, populated with the information
        provided by the weightInfo

        Args:

        Returns:
            QWidget: parent widget that houses all the information to display
        """
        drivenWidget, tableWidget = self.createDrivenWidget()
        drivenWidget.tableWidget = tableWidget

        # Set up signals for the table
        header = tableWidget.verticalHeader()
        header.sectionClicked.connect(self.setConsistentHeaderSelection)
        header.sectionClicked.connect(self.recallDriverPose)
        tableWidget.itemSelectionChanged.connect(self.setEditDeletePoseEnabled)
        return drivenWidget

    @staticmethod
    def setDrivenTable(drivenWidget, rbfNode, weightInfo):
        """set the widgets with information from the weightInfo for dispaly

        Args:
            drivenWidget (QWidget): parent widget, the tab to populate
            rbfNode (RBFNode): node associated with widget
            weightInfo (dict): of information to display
        """
        poses = weightInfo["poses"]
        drivenAttrs = weightInfo["drivenAttrs"]
        rowCount = len(poses["poseValue"])
        verticalLabels = ["Pose {}".format(index) for index in range(rowCount)]

        drivenWidget.tableWidget.clear()
        drivenWidget.tableWidget.setRowCount(rowCount)
        drivenWidget.tableWidget.setColumnCount(len(drivenAttrs))
        drivenWidget.tableWidget.setHorizontalHeaderLabels(drivenAttrs)
        drivenWidget.tableWidget.setVerticalHeaderLabels(verticalLabels)

        for rowIndex, poseInput in enumerate(poses["poseValue"]):
            for columnIndex, pValue in enumerate(poseInput):
                rbfAttrPlug = "{}.poses[{}].poseValue[{}]".format(rbfNode, rowIndex, columnIndex)
                attrEdit, mAttrFeild = getControlAttrWidget(rbfAttrPlug, label="")
                drivenWidget.tableWidget.setCellWidget(rowIndex, columnIndex, attrEdit)

    def populateDrivenWidgetInfo(self, drivenWidget, weightInfo, rbfNode):
        """set the information from the weightInfo to the widgets child of
        drivenWidget

        Args:
            drivenWidget (QWidget): parent widget
            weightInfo (dict): of information to display
            rbfNode (RBFNode): instance of the RBFNode

        Returns:
            n/a: n/a
        """
        driverNode = weightInfo["drivenNode"]
        if driverNode:
            driverNode = driverNode[0]
        else:
            return

        self.setDrivenTable(drivenWidget, rbfNode, weightInfo)

    def addNewTab(self, rbfNode):
        """Create a new tab in the setup

        Args:
            rbfNode (RBFNode): to pull information from

        Returns:
            QWidget: created widget
        """
        tabDrivenWidget = self.createAndTagDrivenWidget()
        self._associateRBFnodeAndWidget(tabDrivenWidget, rbfNode)
        self.rbfTabWidget.addTab(tabDrivenWidget, str(rbfNode))
        return tabDrivenWidget

    def addNewDriven(self):
        self.refresh(
            rbfSelection=False,
            driverSelection=False,
            drivenSelection=True,
            currentRBFSetupNodes=False,
            clearDrivenTab=False
            )

        self.setDrivenButton.blockSignals(False)
        self.drivenAttributesWidget.setEnabled(True)

        self.addRbfButton.setText("Add New Driven")

    def recreateDrivenTabs(self, rbfNodes):
        """remove tabs and create ones for each node in rbfNodes provided

        Args:
            rbfNodes (list): [of RBFNodes]
        """
        rbfNodes = sorted(rbfNodes, key=lambda x: x.name)
        self.rbfTabWidget.clear()
        for rbfNode in rbfNodes:
            weightInfo = rbfNode.getNodeInfo()
            drivenWidget = self.createAndTagDrivenWidget()
            self._associateRBFnodeAndWidget(drivenWidget, rbfNode)
            self.populateDrivenWidgetInfo(drivenWidget, weightInfo, rbfNode)
            self.rbfTabWidget.addTab(drivenWidget, rbfNode.name)

        self.addPoseButton.setEnabled(True)

    def displayRBFSetupInfo(self, index):
        """Display the rbfnodes within the desired setups

        Args:
            index (int): signal information

        """
        rbfSelection = str(self.rbf_cbox.currentText())

        # Refresh UI components
        self.refresh(rbfSelection=False,
                     driverSelection=True,
                     drivenSelection=True,
                     currentRBFSetupNodes=False)

        # Handle 'New' selection case
        if rbfSelection.startswith("New "):
            self.currentRBFSetupNodes = []
            self.lockDriverWidgets(lock=False)
            return

        # Fetch RBF nodes for the selected setup
        rbfNodes = self.allSetupsInfo.get(rbfSelection, [])
        if not rbfNodes:
            return

        # Display node info in the UI
        self.currentRBFSetupNodes = rbfNodes
        weightInfo = rbfNodes[0].getNodeInfo()

        self.populateDriverInfo(rbfNodes[0], weightInfo)
        self.populateDrivenInfo(rbfNodes[0], weightInfo)
        self.lockDriverWidgets(lock=True)

        try:
            self.recreateDrivenTabs(self.allSetupsInfo[rbfSelection])
        except AttributeError:
            print("Forcing refresh on UI due to error.")
            self.refresh(rbfSelection=True,
                         driverSelection=True,
                         drivenSelection=True,
                         currentRBFSetupNodes=True)

    def attrListMenu(self,
                     attributeListWidget,
                     driverLineEdit,
                     attributeListType,
                     QPos,
                     nodeToQuery=None):
        """right click menu for queie qlistwidget

        Args:
            attributeListWidget (QListWidget): widget to display menu over
            driverLineEdit (QLineEdit): widget to query the attrs from
            QPos (QtCore.QPos): due to the signal, used
            nodeToQuery (None, optional): To display attrs from this nodes
            for menu placement

        No Longer Returned:
            n/a: n/a
        """
        if nodeToQuery is None:
            nodeToQuery = str(driverLineEdit.text())
        self.attrMenu = QtWidgets.QMenu()
        parentPosition = attributeListWidget.mapToGlobal(QtCore.QPoint(0, 0))
        menu_item_01 = self.attrMenu.addAction("Display Keyable")
        menu_item_01.setToolTip("Show Keyable Attributes")
        menu_item_01.triggered.connect(partial(self.updateAttributeDisplay,
                                               attributeListWidget,
                                               nodeToQuery,
                                               attrType="keyable",
                                               force=True))
        menu2Label = "Display ChannelBox (Non Keyable)"
        menu_item_02 = self.attrMenu.addAction(menu2Label)
        menu2tip = "Show attributes in ChannelBox that are not keyable."
        menu_item_02.setToolTip(menu2tip)
        menu_item_02.triggered.connect(partial(self.updateAttributeDisplay,
                                               attributeListWidget,
                                               nodeToQuery,
                                               attrType="cb",
                                               force=True))
        menu_item_03 = self.attrMenu.addAction("Display All")
        menu_item_03.setToolTip("GIVE ME ALL!")
        menu_item_03.triggered.connect(partial(self.updateAttributeDisplay,
                                               attributeListWidget,
                                               nodeToQuery,
                                               attrType="all",
                                               force=True))

        self.attrMenu.addSeparator()

        menu_item_04 = self.attrMenu.addAction("Set attribute to auto select")
        menu_item_04.setToolTip("Set your attribute to be automatically highlighted up in the next operations")
        menu_item_04.triggered.connect(partial(self.setAttributeToAutoSelect,
                                               attributeListWidget))
        self.attrMenu.move(parentPosition + QPos)
        self.attrMenu.show()

    def refreshRbfSetupList(self, setToSelection=False):
        """refresh the list of setups the user may select from

        Args:
            setToSelection (bool, optional): after refresh, set to desired
        """
        self.rbf_cbox.blockSignals(True)

        # Clear the combo box and populate with new setup options
        self.rbf_cbox.clear()
        self.updateAllSetupsInfo()
        allSetups = sorted(self.allSetupsInfo.keys())
        newSetupOptions = ["New {} setup".format(rbf) for rbf in rbf_node.SUPPORTED_RBF_NODES]
        self.rbf_cbox.addItems(newSetupOptions + allSetups)

        if setToSelection:
            selectionIndex = self.rbf_cbox.findText(setToSelection)
            self.rbf_cbox.setCurrentIndex(selectionIndex)
        else:
            self.lockDriverWidgets(lock=False)
        self.rbf_cbox.blockSignals(False)

    def clearDriverTabs(self):
        """force deletion on tab widgets
        """
        toRemove = []
        tabIndicies = self.driverPoseTableWidget.count()
        for index in range(tabIndicies):
            tabWidget = self.driverPoseTableWidget.widget(index)
            toRemove.append(tabWidget)
        self.driverPoseTableWidget.clear()
        [t.deleteLater() for t in toRemove]

    def clearDrivenTabs(self):
        """force deletion on tab widgets
        """
        toRemove = []
        tabIndicies = self.rbfTabWidget.count()
        for index in range(tabIndicies):
            tabWidget = self.rbfTabWidget.widget(index)
            toRemove.append(tabWidget)
        self.rbfTabWidget.clear()
        [t.deleteLater() for t in toRemove]

    def refresh(self,
                rbfSelection=True,
                driverSelection=True,
                drivenSelection=True,
                currentRBFSetupNodes=True,
                clearDrivenTab=True,
                *args):
        """Refreshes the UI

        Args:
            rbfSelection (bool, optional): desired section to refresh
            driverSelection (bool, optional): desired section to refresh
            drivenSelection (bool, optional): desired section to refresh
            currentRBFSetupNodes (bool, optional): desired section to refresh
            clearDrivenTab (bool, optional): desired section to refresh
        """
        self.addRbfButton.setText("New RBF")
        self.addPoseButton.setEnabled(False)
        if rbfSelection:
            self.refreshRbfSetupList()
        if driverSelection:
            self.controlLineEdit.clear()
            self.driverLineEdit.clear()
            self.driverAttributesWidget.clear()
            self.__deleteAssociatedWidgetsMaya(self.driverPoseTableWidget)
            self.__deleteAssociatedWidgets(self.driverPoseTableWidget)
        if drivenSelection:
            self.drivenLineEdit.clear()
            self.drivenAttributesWidget.clear()
            if clearDrivenTab:
                self.clearDrivenTabs()
        if currentRBFSetupNodes:
            self.currentRBFSetupNodes = []

    def recallDriverPose(self, indexSelected):
        """recall a pose recorded from one of the RBFNodes in currentSelection
        it should not matter when RBFNode in setup is selected as they
        should all be in sync

        Args:
            indexSelected (int): index of the pose to recall

        Returns:
            n/a: nada
        """
        if not self.currentRBFSetupNodes:
            return
        self.currentRBFSetupNodes[0].recallDriverPose(indexSelected)

    def setConsistentHeaderSelection(self, headerIndex):
        """when a pose is selected in one table, ensure the selection in all
        other tables, to avoid visual confusion

        Args:
            headerIndex (int): desired header to highlight
        """
        self.driverPoseTableWidget.blockSignals(True)
        self.driverPoseTableWidget.selectRow(headerIndex)
        self.driverPoseTableWidget.blockSignals(False)
        for index in range(self.rbfTabWidget.count()):
            drivenWidget = self.rbfTabWidget.widget(index)
            drivenTableWidget = getattr(drivenWidget, "tableWidget")
            drivenTableWidget.blockSignals(True)
            drivenTableWidget.selectRow(headerIndex)
            drivenTableWidget.blockSignals(False)
        self.setEditDeletePoseEnabled(enable=True)

    def setEditDeletePoseEnabled(self, enable=False):
        """toggle buttons that can or cannot be selected

        Args:
            enable (bool, optional): to disable vs not
        """
        self.editPoseButton.setEnabled(enable)
        self.editPoseValuesButton.setEnabled(enable)
        self.deletePoseButton.setEnabled(enable)

    def setDriverControlOnSetup(self, controlName):
        """make sure to set the driverControlAttr when the user supplies one

        Args:
            controlName (str): name of the control to set in an attr
        """
        for rbfNode in self.currentRBFSetupNodes:
            rbfNode.setDriverControlAttr(controlName)

    def setSetupDriverControl(self, lineEditWidget):
        """should the user wish to set a different driverControl pose setup
        creation, prompt them prior to proceeding

        Args:
            lineEditWidget (QLineEdit): to query for the name

        Returns:
            n/a: nada
        """
        if not self.currentRBFSetupNodes:
            self.setNodeToField(lineEditWidget)
        elif self.currentRBFSetupNodes:
            textA = "Do you want to change the Control for setup?"
            textB = "This Control that will be used for recalling poses."
            decision = promptAcceptance(self, textA, textB)
            if decision in [QtWidgets.QMessageBox.Discard,
                            QtWidgets.QMessageBox.Cancel]:
                return
            controlName = self.setNodeToField(lineEditWidget)
            self.setDriverControlOnSetup(controlName)

    @staticmethod
    def getRBFNodesInfo(rbfNodes):
        """create a dictionary of all the RBFInfo(referred to as
        weightNodeInfo a lot) for export

        Args:
            rbfNodes (list): [of RBFNodes]

        Returns:
            dict: of all the rbfNodes provided
        """
        weightNodeInfo_dict = {}
        for rbf in rbfNodes:
            weightNodeInfo_dict[rbf.name] = rbf.getNodeInfo()
        return weightNodeInfo_dict

    def importNodes(self):
        """import a setup(s) from file select by user

        Returns:
            n/a: nada
        """
        # sceneFilePath = mc.file(sn=True, q=True)
        # startDir = os.path.dirname(sceneFilePath)
        filePath = rbf_io.fileDialog(mode=1)
        if filePath is None:
            return
        rbf_io.importRBFs(filePath)
        mc.select(cl=True)
        self.refresh()
        print("RBF setups imported: {}".format(filePath))

    def exportNodes(self, allSetups=True):
        """export all nodes or nodes from current setup

        Args:
            allSetups (bool, optional): If all or setup

        Returns:
            n/a: nada
        """
        # TODO WHEN NEW RBF NODE TYPES ARE ADDED, THIS WILL NEED TO BE RETOOLED
        nodesToExport = []
        if allSetups:
            [nodesToExport.extend(v) for k, v,
             in self.allSetupsInfo.items()]
        else:
            nodesToExport = self.currentRBFSetupNodes

        nodesToExport = [n.name for n in nodesToExport]
        # sceneFilePath = mc.file(sn=True, q=True)
        # startDir = os.path.dirname(sceneFilePath)
        filePath = rbf_io.fileDialog(mode=0)
        if filePath is None:
            return
        rbf_io.exportRBFs(nodesToExport, filePath)

    @staticmethod
    def gatherMirroredInfo(rbfNodes):
        """gather all the info from the provided nodes and string replace
        side information for its mirror. Using mGear standard
        naming convections

        Args:
            rbfNodes (list): [of RBFNodes]

        Returns:
            dict: with all the info mirrored
        """
        mirrorWeightInfo = {}
        for rbfNode in rbfNodes:
            weightInfo = rbfNode.getNodeInfo()
            # connections -----------------------------------------------------
            mrConnections = []
            for pairs in weightInfo["connections"]:
                mrConnections.append([mString.convertRLName(pairs[0]),
                                      mString.convertRLName(pairs[1])])

            weightInfo["connections"] = mrConnections
            weightInfo["drivenControlName"] = mString.convertRLName(weightInfo["drivenControlName"])
            weightInfo["drivenNode"] = [mString.convertRLName(n) for n in weightInfo["drivenNode"]]
            weightInfo["driverControl"] = mString.convertRLName(weightInfo["driverControl"])
            weightInfo["driverNode"] = [mString.convertRLName(n) for n in weightInfo["driverNode"]]

            # setupName -------------------------------------------------------
            mrSetupName = mString.convertRLName(weightInfo["setupName"])
            if mrSetupName == weightInfo["setupName"]:
                mrSetupName = "{}{}".format(mrSetupName, MIRROR_SUFFIX)
            weightInfo["setupName"] = mrSetupName
            # transformNode ---------------------------------------------------
            tmp = weightInfo["transformNode"]["name"]
            mrTransformName = mString.convertRLName(tmp)
            weightInfo["transformNode"]["name"] = mrTransformName

            tmp = weightInfo["transformNode"]["parent"]
            if tmp is None:
                mrTransformPar = None
            else:
                mrTransformPar = mString.convertRLName(tmp)
            weightInfo["transformNode"]["parent"] = mrTransformPar
            # name ------------------------------------------------------------
            mirrorWeightInfo[mString.convertRLName(rbfNode.name)] = weightInfo
        return mirrorWeightInfo

    def getMirroredSetupTargetsInfo(self):
        """convenience function to get all the mirrored info for the new side

        Returns:
            dict: mirrored dict information
        """
        setupTargetInfo_dict = {}
        for rbfNode in self.currentRBFSetupNodes:
            mrRbfNode = mString.convertRLName(rbfNode.name)
            mrRbfNode = sortRBF(mrRbfNode)
            drivenNode = rbfNode.getDrivenNode()[0]
            drivenControlNode = rbfNode.getConnectedRBFToggleNode()
            mrDrivenControlNode = mString.convertRLName(drivenControlNode)
            mrDrivenControlNode = pm.PyNode(mrDrivenControlNode)
            setupTargetInfo_dict[pm.PyNode(drivenNode)] = [mrDrivenControlNode, mrRbfNode]
        return setupTargetInfo_dict

    def mirrorSetup(self):
        """gather all info on current setup, mirror the info, use the creation
        func from that rbf module type to create the nodes in the setup with
        mirrored information.

        THE ONLY nodes created will be the ones created during normal
        "add pose" creation. Assumption is that all nodes that need drive,
        driven by the setup exist.

        Returns:
            n/a: nada
        """
        if not self.currentRBFSetupNodes:
            return
        aRbfNode = self.currentRBFSetupNodes[0]
        mirrorWeightInfo = self.gatherMirroredInfo(self.currentRBFSetupNodes)
        mrRbfType = aRbfNode.rbfType
        poseIndices = len(aRbfNode.getPoseInfo()["poseInput"])
        rbfModule = rbf_io.RBF_MODULES[mrRbfType]
        rbfModule.createRBFFromInfo(mirrorWeightInfo)
        setupTargetInfo_dict = self.getMirroredSetupTargetsInfo()
        nameSpace = anim_utils.getNamespace(aRbfNode.name)
        mrRbfNodes = [v[1] for k, v in setupTargetInfo_dict.items()]
        [v.setToggleRBFAttr(0) for v in mrRbfNodes]
        mrDriverNode = mrRbfNodes[0].getDriverNode()[0]
        mrDriverAttrs = mrRbfNodes[0].getDriverNodeAttributes()
        driverControl = aRbfNode.getDriverControlAttr()
        driverControl = pm.PyNode(driverControl)
        # Sanity check: make sure mirror attributes are set up properly
        for targetInfo in setupTargetInfo_dict.items():
            driven = targetInfo[0]
            ctrl = driven.name().replace("_driven", "_ctl")
            for attr in ["invTx", "invTy", "invTz", "invRx", "invRy", "invRz"]:
                pm.setAttr(driven + "." + attr, pm.getAttr(ctrl + "." + attr))
        for index in range(poseIndices):
            # Apply mirror pose to control
            aRbfNode.recallDriverPose(index)
            anim_utils.mirrorPose(flip=False, nodes=[driverControl])
            mrData = []
            for srcNode, dstValues in setupTargetInfo_dict.items():
                mrData.extend(anim_utils.calculateMirrorDataRBF(srcNode,
                                                             dstValues[0]))
            for entry in mrData:
                anim_utils.applyMirror(nameSpace, entry)
            poseInputs = rbf_node.getMultipleAttrs(mrDriverNode, mrDriverAttrs)
            for mrRbfNode in mrRbfNodes:
                poseValues = mrRbfNode.getPoseValues(resetDriven=False)
                mrRbfNode.addPose(poseInput=poseInputs,
                                  poseValue=poseValues,
                                  posesIndex=index)
                mrRbfNode.forceEvaluation()
        [v.setToggleRBFAttr(1) for v in mrRbfNodes]
        setupName, rbfType = self.getSelectedSetup()
        self.refreshRbfSetupList(setToSelection=setupName)
        for mrRbfNode in mrRbfNodes:
            rbf_node.resetDrivenNodes(str(mrRbfNode))
        pm.select(cl=True)

    def hideMenuBar(self, x, y):
        """rules to hide/show the menubar when hide is enabled

        Args:
            x (int): coord X of the mouse
            y (int): coord Y of the mouse
        """
        if x < 100 and y < 50:
            self.menuBar().show()
        else:
            self.menuBar().hide()

    def tabConextMenu(self, qPoint):
        """create a pop up menu over the tabs when right clicked

        Args:
            qPoint (int): the mouse position when menu requested

        Returns:
            n/a: diddly
        """
        tabIndex = self.rbfTabWidget.tabBar().tabAt(qPoint)
        if tabIndex == -1:
            return
        selWidget = self.rbfTabWidget.widget(tabIndex)
        rbfNode = getattr(selWidget, "rbfNode")
        tabMenu = QtWidgets.QMenu(self)
        parentPosition = self.rbfTabWidget.mapToGlobal(QtCore.QPoint(0, 0))
        menu_item_01 = tabMenu.addAction("Select {}".format(rbfNode))
        menu_item_01.triggered.connect(partial(mc.select, rbfNode))
        partialObj_selWdgt = partial(self.rbfTabWidget.setCurrentWidget,
                                     selWidget)
        menu_item_01.triggered.connect(partialObj_selWdgt)
        tabMenu.move(parentPosition + qPoint)
        tabMenu.show()

    def reevalluateAllNodes(self):
        """for evaluation on all nodes in any setup. In case of manual editing
        """
        for name, rbfNodes in self.allSetupsInfo.items():
            [rbfNode.forceEvaluation() for rbfNode in rbfNodes]
        print("All Nodes have been Re-evaluated")

    def toggleGetPoseType(self, toggleState):
        """records whether the user wants poses recorded in worldSpace or check
        local space

        Args:
            toggleState (bool): default True
        """
        self.absWorld = toggleState

    def toggleDefaultType(self, toggleState):
        """records whether the user wants default poses to be zeroed

        Args:
            toggleState (bool): default True
        """
        self.zeroedDefaults = toggleState

    # signal management -------------------------------------------------------
    def connectSignals(self):
        """connect all the signals in the UI
        Exceptions being MenuBar and Table header signals
        """
        # RBF ComboBox and Refresh Button
        self.rbf_cbox.currentIndexChanged.connect(self.displayRBFSetupInfo)
        self.rbf_refreshButton.clicked.connect(self.refresh)

        # Driver Line Edit and Control Line Edit
        self.driverLineEdit.clicked.connect(selectNode)
        self.controlLineEdit.clicked.connect(selectNode)
        self.driverLineEdit.textChanged.connect(partial(self.updateAttributeDisplay,
                                                        self.driverAttributesWidget))
        self.drivenLineEdit.textChanged.connect(partial(self.updateAttributeDisplay,
                                                        self.drivenAttributesWidget))

        # Table Widget
        header = self.driverPoseTableWidget.verticalHeader()
        header.sectionClicked.connect(self.setConsistentHeaderSelection)
        header.sectionClicked.connect(self.recallDriverPose)
        selDelFunc = self.setEditDeletePoseEnabled
        self.driverPoseTableWidget.itemSelectionChanged.connect(selDelFunc)

        # Buttons Widget
        self.addRbfButton.clicked.connect(self.addRBFToSetup)
        self.addPoseButton.clicked.connect(self.addPose)
        self.editPoseButton.clicked.connect(self.editPose)
        self.editPoseValuesButton.clicked.connect(self.editPoseValues)
        self.deletePoseButton.clicked.connect(self.deletePose)
        self.setControlButton.clicked.connect(partial(self.setSetupDriverControl, self.controlLineEdit))
        self.setDriverButton.clicked.connect(partial(self.setNodeToField, self.driverLineEdit))
        self.allButton.clicked.connect(self.setDriverControlLineEdit)
        self.setDrivenButton.clicked.connect(partial(self.setNodeToField, self.drivenLineEdit))
        self.addDrivenButton.clicked.connect(self.addNewDriven)

        # Custom Context Menus
        customMenu = self.driverAttributesWidget.customContextMenuRequested
        customMenu.connect(
            partial(self.attrListMenu,
                    self.driverAttributesWidget,
                    self.driverLineEdit,
                    "driver")
        )
        customMenu = self.drivenAttributesWidget.customContextMenuRequested
        customMenu.connect(
            partial(self.attrListMenu,
                    self.drivenAttributesWidget,
                    self.driverLineEdit,
                    "driven")
        )

        # Tab Widget
        tabBar = self.rbfTabWidget.tabBar()
        tabBar.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tabBar.customContextMenuRequested.connect(self.tabConextMenu)
        tabBar.tabCloseRequested.connect(self.removeRBFFromSetup)

    # broken down widgets -----------------------------------------------------
    def createSetupSelectorWidget(self):
        """create the top portion of the weidget, select setup + refresh

        Returns:
            list: QLayout, QCombobox, QPushButton
        """
        setRBFLayout = QtWidgets.QHBoxLayout()
        rbfLabel = QtWidgets.QLabel("Select RBF Setup:")
        rbf_cbox = QtWidgets.QComboBox()
        rbf_refreshButton = self.createCustomButton("Refresh", (60, 25), "Refresh the UI")
        rbf_cbox.setFixedHeight(self.genericWidgetHight)
        rbf_refreshButton.setMaximumWidth(80)
        rbf_refreshButton.setFixedHeight(self.genericWidgetHight - 1)
        setRBFLayout.addWidget(rbfLabel)
        setRBFLayout.addWidget(rbf_cbox, 1)
        setRBFLayout.addWidget(rbf_refreshButton)
        return setRBFLayout, rbf_cbox, rbf_refreshButton

    @staticmethod
    def createCustomButton(label, size=(35, 27), tooltip=""):
        stylesheet = (
            "QPushButton {background-color: #5D5D5D; border-radius: 4px;}"
            "QPushButton:pressed { background-color: #00A6F3;}"
            "QPushButton:hover:!pressed { background-color: #707070;}"
            "QPushButton:disabled { background-color: #4a4a4a;}"
        )
        button = QtWidgets.QPushButton(label)
        button.setMinimumSize(QtCore.QSize(*size))
        button.setStyleSheet(stylesheet)
        button.setToolTip(tooltip)
        return button

    @staticmethod
    def createSetupSelector2Widget():
        rbfVLayout = QtWidgets.QVBoxLayout()
        rbfListWidget = QtWidgets.QListWidget()
        rbfVLayout.addWidget(rbfListWidget)
        return rbfVLayout, rbfListWidget

    def selectNodeWidget(self, label, buttonLabel="Select"):
        """create a lout with label, lineEdit, QPushbutton for user input
        """
        stylesheet = (
            "QLineEdit { background-color: #404040;"
            "border-radius: 4px;"
            "border-color: #505050;"
            "border-style: solid;"
            "border-width: 1.4px;}"
        )

        nodeLayout = QtWidgets.QHBoxLayout()
        nodeLayout.setSpacing(4)

        nodeLabel = QtWidgets.QLabel(label)
        nodeLabel.setFixedWidth(40)
        nodeLineEdit = ClickableLineEdit()
        nodeLineEdit.setStyleSheet(stylesheet)
        nodeLineEdit.setReadOnly(True)
        nodeSelectButton = self.createCustomButton(buttonLabel)
        nodeSelectButton.setFixedWidth(40)
        nodeLineEdit.setFixedHeight(self.genericWidgetHight)
        nodeSelectButton.setFixedHeight(self.genericWidgetHight)
        nodeLayout.addWidget(nodeLabel)
        nodeLayout.addWidget(nodeLineEdit, 1)
        nodeLayout.addWidget(nodeSelectButton)
        return nodeLayout, nodeLineEdit, nodeSelectButton

    @staticmethod
    def labelListWidget(label, attrListType, horizontal=True):
        """create the listAttribute that users can select their driver/driven
        attributes for the setup

        Args:
            label (str): to display above the listWidget
            horizontal (bool, optional): should the label be above or infront
            of the listWidget

        Returns:
            list: QLayout, QListWidget
        """
        if horizontal:
            attributeLayout = QtWidgets.QHBoxLayout()
        else:
            attributeLayout = QtWidgets.QVBoxLayout()
        attributeLabel = QtWidgets.QLabel(label)
        attributeListWidget = QtWidgets.QListWidget()
        attributeListWidget.setObjectName("{}ListWidget".format(attrListType))
        attributeLayout.addWidget(attributeLabel)
        attributeLayout.addWidget(attributeListWidget)
        return attributeLayout, attributeListWidget

    @staticmethod
    def addRemoveButtonWidget(label1, label2, horizontal=True):
        if horizontal:
            addRemoveLayout = QtWidgets.QHBoxLayout()
        else:
            addRemoveLayout = QtWidgets.QVBoxLayout()
        addAttributesButton = QtWidgets.QPushButton(label1)
        removeAttributesButton = QtWidgets.QPushButton(label2)
        addRemoveLayout.addWidget(addAttributesButton)
        addRemoveLayout.addWidget(removeAttributesButton)
        return addRemoveLayout, addAttributesButton, removeAttributesButton

    def createDriverAttributeWidget(self):
        """widget where the user inputs information for the setups

        Returns:
            list: [of widgets]
        """
        driverControlVLayout = QtWidgets.QVBoxLayout()
        driverControlHLayout = QtWidgets.QHBoxLayout()

        # driverMainLayout.setStyleSheet("QVBoxLayout { background-color: #404040;")
        driverControlHLayout.setSpacing(3)
        #  --------------------------------------------------------------------
        (controlLayout,
         controlLineEdit,
         setControlButton) = self.selectNodeWidget("Control", buttonLabel="Set")
        controlLineEdit.setToolTip("The node driving the setup. (Click me!)")
        #  --------------------------------------------------------------------
        (driverLayout,
         driverLineEdit,
         driverSelectButton) = self.selectNodeWidget("Driver", buttonLabel="Set")
        driverLineEdit.setToolTip("The node driving the setup. (Click me!)")
        #  --------------------------------------------------------------------
        allButton = self.createCustomButton("All", (20, 53), "")

        (attributeLayout, attributeListWidget) = self.labelListWidget(
            label="Select Driver Attributes:", attrListType="driver", horizontal=False)

        attributeListWidget.setToolTip("List of attributes driving setup.")
        selType = QtWidgets.QAbstractItemView.ExtendedSelection
        attributeListWidget.setSelectionMode(selType)
        attributeListWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        #  --------------------------------------------------------------------
        driverControlVLayout.addLayout(controlLayout, 0)
        driverControlVLayout.addLayout(driverLayout, 0)
        driverControlHLayout.addLayout(driverControlVLayout, 0)
        driverControlHLayout.addWidget(allButton, 0)
        return [controlLineEdit,
                setControlButton,
                driverLineEdit,
                driverSelectButton,
                allButton,
                attributeListWidget,
                attributeLayout,
                driverControlHLayout]

    def createDrivenAttributeWidget(self):
        """the widget that displays the driven information

        Returns:
            list: [of widgets]
        """
        drivenWidget = QtWidgets.QWidget()
        drivenMainLayout = QtWidgets.QVBoxLayout()
        drivenMainLayout.setContentsMargins(0, 10, 0, 2)
        drivenMainLayout.setSpacing(9)
        drivenSetLayout = QtWidgets.QVBoxLayout()
        drivenMainLayout.addLayout(drivenSetLayout)
        drivenWidget.setLayout(drivenMainLayout)
        #  --------------------------------------------------------------------
        (drivenLayout,
         drivenLineEdit,
         drivenSelectButton) = self.selectNodeWidget("Driven", buttonLabel="Set")
        drivenTip = "The node being driven by setup. (Click me!)"
        drivenLineEdit.setToolTip(drivenTip)

        addDrivenButton = self.createCustomButton("+", (20, 26), "")
        addDrivenButton.setToolTip("Add a new driven to the current rbf node")
        #  --------------------------------------------------------------------
        (attributeLayout,
         attributeListWidget) = self.labelListWidget(label="Select Driven Attributes:",
                                                     attrListType="driven",
                                                     horizontal=False)
        attributeListWidget.setToolTip("Attributes being driven by setup.")
        attributeLayout.setSpacing(1)
        selType = QtWidgets.QAbstractItemView.ExtendedSelection
        attributeListWidget.setSelectionMode(selType)
        attributeListWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        #  --------------------------------------------------------------------
        drivenSetLayout.addLayout(drivenLayout, 0)
        drivenSetLayout.addLayout(attributeLayout, 0)
        drivenLayout.addWidget(addDrivenButton)
        drivenSetLayout.addLayout(drivenLayout, 0)
        drivenSetLayout.addLayout(attributeLayout, 0)
        drivenMainLayout.addLayout(drivenSetLayout)
        drivenWidget.setLayout(drivenMainLayout)
        return [drivenLineEdit,
                drivenSelectButton,
                addDrivenButton,
                attributeListWidget,
                drivenWidget,
                drivenMainLayout]

    def createDrivenWidget(self):
        """the widget that displays the driven information

        Returns:
            list: [of widgets]
        """
        drivenWidget = QtWidgets.QWidget()
        drivenMainLayout = QtWidgets.QHBoxLayout()
        drivenMainLayout.setContentsMargins(0, 0, 0, 0)
        drivenMainLayout.setSpacing(9)
        drivenWidget.setLayout(drivenMainLayout)

        tableWidget = self.createTableWidget()
        drivenMainLayout.addWidget(tableWidget, 1)
        return drivenWidget, tableWidget

    def createTableWidget(self):
        """create table widget used to display poses, set tooltips and colum

        Returns:
            QTableWidget: QTableWidget
        """
        stylesheet = """
        QTableWidget QHeaderView::section {
            background-color: #3a3b3b;
            padding: 2px;
            text-align: center;
        }
        QTableCornerButton::section {
            background-color: #3a3b3b;
            border: none; 
        }
        """
        tableWidget = QtWidgets.QTableWidget()
        tableWidget.insertColumn(0)
        tableWidget.insertRow(0)
        tableWidget.setHorizontalHeaderLabels(["Pose Value"])
        tableWidget.setVerticalHeaderLabels(["Pose #0"])
        # tableWidget.setStyleSheet(stylesheet)
        tableTip = "Live connections to the RBF Node in your setup."
        tableTip = tableTip + "\nSelect the desired Pose # to recall pose."
        tableWidget.setToolTip(tableTip)
        return tableWidget

    def createTabWidget(self):
        """Tab widget to add driven widgets too. Custom TabBar so the tab is
        easier to select

        Returns:
            QTabWidget:
        """
        tabLayout = QtWidgets.QTabWidget()
        tabLayout.setContentsMargins(0, 0, 0, 0)
        tabBar = TabBar()
        tabLayout.setTabBar(tabBar)
        tabBar.setTabsClosable(True)
        return tabLayout

    def createOptionsButtonsWidget(self):
        """add, edit, delete buttons for modifying rbf setups.

        Returns:
            list: [QPushButtons]
        """
        optionsLayout = QtWidgets.QHBoxLayout()
        optionsLayout.setSpacing(5)
        addTip = "After positioning all controls in the setup, add new pose."
        addTip = addTip + "\nEnsure the driver node has a unique position."
        addPoseButton = self.createCustomButton("Add Pose", size=(80, 26), tooltip=addTip)
        EditPoseButton = self.createCustomButton("Update Pose", size=(80, 26))
        EditPoseButton.setToolTip("Recall pose, adjust controls and Edit.")
        EditPoseValuesButton = self.createCustomButton("Update Pose Values", size=(80, 26))
        EditPoseValuesButton.setToolTip("Set pose based on values in table")
        deletePoseButton = self.createCustomButton("Delete Pose", size=(80, 26))
        deletePoseButton.setToolTip("Recall pose, then Delete")
        optionsLayout.addWidget(addPoseButton)
        optionsLayout.addWidget(EditPoseButton)
        optionsLayout.addWidget(EditPoseValuesButton)
        optionsLayout.addWidget(deletePoseButton)
        return (optionsLayout,
                addPoseButton,
                EditPoseButton,
                EditPoseValuesButton,
                deletePoseButton)

    def createMenuBar(self, hideMenuBar=False):
        """Create the UI menubar, with option to hide based on mouse input

        Args:
            hideMenuBar (bool, optional): should it autoHide

        Returns:
            QMenuBar: for parenting
        """
        mainMenuBar = QtWidgets.QMenuBar()
        mainMenuBar.setContentsMargins(0, 0, 0, 0)
        file = mainMenuBar.addMenu("File")
        menu1 = file.addAction("Re-evaluate Nodes", self.reevalluateAllNodes)
        menu1.setToolTip("Force all RBF nodes to re-revaluate.")
        file.addAction("Export All", self.exportNodes)
        file.addAction("Export current setup", partial(self.exportNodes,
                                                       allSetups=False))
        file.addAction("Import RBFs", partial(self.importNodes))
        file.addSeparator()
        file.addAction("Delete Current Setup", self.__deleteSetup)
        # mirror --------------------------------------------------------------
        mirrorMenu = mainMenuBar.addMenu("Mirror")
        mirrorMenu1 = mirrorMenu.addAction("Mirror Setup", self.mirrorSetup)
        mirrorMenu1.setToolTip("This will create a new setup.")

        # settings ------------------------------------------------------------
        settingsMenu = mainMenuBar.addMenu("Settings")
        menuLabel = "Add poses in worldSpace"
        worldSpaceMenuItem = settingsMenu.addAction(menuLabel)
        worldSpaceMenuItem.toggled.connect(self.toggleGetPoseType)

        worldSpaceMenuItem.setCheckable(True)
        worldSpaceMenuItem.setChecked(True)
        toolTip = "When ADDING NEW pose, should it be recorded in worldSpace."

        menuLabel = "Default Poses is Zeroed"
        zeroedDefaultsMenuItem = settingsMenu.addAction(menuLabel)
        zeroedDefaultsMenuItem.toggled.connect(self.toggleDefaultType)

        zeroedDefaultsMenuItem.setCheckable(True)
        zeroedDefaultsMenuItem.setChecked(True)

        worldSpaceMenuItem.setToolTip(toolTip)

        # show override -------------------------------------------------------
        additionalFuncDict = getEnvironModules()
        if additionalFuncDict:
            showOverridesMenu = mainMenuBar.addMenu("Local Overrides")
            for k, v in additionalFuncDict.items():
                showOverridesMenu.addAction(k, v)

        if hideMenuBar:
            mainMenuBar.hide()
            self.setMouseTracking(True)
            self.mousePosition.connect(self.hideMenuBar)
        return mainMenuBar

    def createDarkContainerWidget(self):
        darkContainer = QtWidgets.QWidget()
        driverMainLayout = QtWidgets.QVBoxLayout()
        driverMainLayout.setContentsMargins(10, 10, 10, 10)  # Adjust margins as needed
        driverMainLayout.setSpacing(5)  # Adjust spacing between widgets

        # Setting the dark color (Example: dark gray)
        # darkContainer.setStyleSheet("background-color: #323232;")

        # Driver section
        (self.controlLineEdit,
         self.setControlButton,
         self.driverLineEdit,
         self.setDriverButton,
         self.allButton,
         self.driverAttributesWidget,
         self.driverAttributesLayout,
         driverControlLayout) = self.createDriverAttributeWidget()

        # Driven section
        (self.drivenLineEdit,
         self.setDrivenButton,
         self.addDrivenButton,
         self.drivenAttributesWidget,
         self.drivenWidget,
         self.drivenMainLayout) = self.createDrivenAttributeWidget()

        self.addRbfButton = self.createCustomButton("New RBF")
        self.addRbfButton.setToolTip("Select node to be driven by setup.")
        stylesheet = (
            "QPushButton {background-color: #179e83; border-radius: 4px;}"
            "QPushButton:hover:!pressed { background-color: #2ea88f;}"
        )
        self.addRbfButton.setStyleSheet(stylesheet)

        # Setting up the main layout for driver and driven sections
        driverMainLayout = QtWidgets.QVBoxLayout()
        driverMainLayout.addLayout(driverControlLayout)
        driverMainLayout.addLayout(self.driverAttributesLayout)
        driverMainLayout.addWidget(self.drivenWidget)
        driverMainLayout.addWidget(self.addRbfButton)
        darkContainer.setLayout(driverMainLayout)

        return darkContainer

    def createDriverDrivenTableWidget(self):
        tableContainer = QtWidgets.QWidget()

        # Setting up the main layout for driver and driven sections
        driverDrivenTableLayout = QtWidgets.QVBoxLayout()
        self.driverPoseTableWidget = self.createTableWidget()
        self.rbfTabWidget = self.createTabWidget()

        # Options buttons section
        (optionsLayout,
         self.addPoseButton,
         self.editPoseButton,
         self.editPoseValuesButton,
         self.deletePoseButton) = self.createOptionsButtonsWidget()
        self.addPoseButton.setEnabled(False)
        self.editPoseButton.setEnabled(False)
        self.editPoseValuesButton.setEnabled(False)
        self.deletePoseButton.setEnabled(False)

        driverDrivenTableLayout.addWidget(self.driverPoseTableWidget, 1)
        driverDrivenTableLayout.addWidget(self.rbfTabWidget, 1)
        driverDrivenTableLayout.addLayout(optionsLayout)
        tableContainer.setLayout(driverDrivenTableLayout)

        return tableContainer

    # main assebly ------------------------------------------------------------
    def createCentralWidget(self):
        """main UI assembly

        Returns:
            QtWidget: main UI to be parented to as the centralWidget
        """
        centralWidget = QtWidgets.QWidget()
        centralWidgetLayout = QtWidgets.QVBoxLayout()
        centralWidget.setLayout(centralWidgetLayout)

        splitter = QtWidgets.QSplitter()

        # Setup selector section
        (rbfLayout,
         self.rbf_cbox,
         self.rbf_refreshButton) = self.createSetupSelectorWidget()
        self.rbf_cbox.setToolTip("List of available setups in the scene.")
        self.rbf_refreshButton.setToolTip("Refresh the UI")

        driverDrivenWidget = self.createDarkContainerWidget()
        allTableWidget = self.createDriverDrivenTableWidget()

        centralWidgetLayout.addLayout(rbfLayout)
        centralWidgetLayout.addWidget(HLine())
        splitter.addWidget(driverDrivenWidget)
        splitter.addWidget(allTableWidget)
        centralWidgetLayout.addWidget(splitter)

        # Assuming a ratio of 2:1 for settingWidth to tableWidth
        totalWidth = splitter.width()
        attributeWidth = (1/3) * totalWidth
        tableWidth = (2/3) * totalWidth
        splitter.setSizes([int(attributeWidth), int(tableWidth)])
        return centralWidget

    # overrides ---------------------------------------------------------------
    def mouseMoveEvent(self, event):
        """used for tracking the mouse position over the UI, in this case for
        menu hiding/show

        Args:
            event (Qt.QEvent): events to filter
        """
        if event.type() == QtCore.QEvent.MouseMove:
            if event.buttons() == QtCore.Qt.NoButton:
                pos = event.pos()
                self.mousePosition.emit(pos.x(), pos.y())

    def closeEvent(self, evnt):
        """on UI close, ensure that all attrControlgrps are destroyed in case
        the user is just reopening the UI. Properly severs ties to the attrs

        Args:
            evnt (Qt.QEvent): Close event called
        """
        self.__deleteAssociatedWidgetsMaya(self.driverPoseTableWidget)
        self.__deleteAssociatedWidgets(self.driverPoseTableWidget)
        if self.callBackID is not None:
            self.removeSceneCallback()
        super(RBFManagerUI, self).closeEvent(evnt)
