import pymel.core as pm
import maya.cmds as cmds
import json
import sys
from functools import partial
import traceback
import os.path

import mgear.core.utils as mutils
from mgear.core import string

import mgear.shifter.game_tools_ui as gtUI

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from mgear.core import pyqt
from mgear.vendor.Qt import QtCore, QtWidgets

if sys.version_info[0] == 2:
    string_types = (basestring, )
else:
    string_types = (str,)

SRT_CHANNELS = ["translate",
                "translate.translateX",
                "translate.translateY",
                "translate.translateZ",
                "rotate",
                "rotate.rotateX",
                "rotate.rotateY",
                "rotate.rotateZ",
                "scale",
                "scale.scaleX",
                "scale.scaleY",
                "scale.scaleZ",
                "shear"]


@mutils.one_undo
def disconnect(cnxDict):
    """Disconnect the joints using the connections dictionary

    Args:
        cnxDict (dict): Description of the deconections to remove
    """
    for i, jnt in enumerate(cnxDict["joints"]):
        # we don't need to disconnect blended joint since the connection is
        # from other joints
        if not jnt.startswith("blend_"):
            oJnt = pm.PyNode(jnt)

            for e, chn in enumerate(SRT_CHANNELS):
                plug = oJnt.attr(chn)
                if cnxDict["attrs"][i][e]:
                    pm.disconnectAttr(cnxDict["attrs"][i][e], plug)
            if cnxDict["attrs"][i][13]:
                pm.disconnectAttr(
                    oJnt.parentInverseMatrix[0], cnxDict["attrs"][i][13])


def connect(cnxDict, nsRig=None, nsSkin=None):
    """Connect the joints using the connections dictionary.

    Args:
        cnxDict (dict): Description of the deconections to remove
        nsRig (string, optional): rig namespace
        nsSkin (None, optional): model namespace
    """
    for i, jnt in enumerate(cnxDict["joints"]):
        # try:
        if nsSkin:
            oJnt = pm.PyNode(nsSkin + ":" + jnt)
        else:
            oJnt = pm.PyNode(jnt)
        for e, chn in enumerate(SRT_CHANNELS):
            plug = oJnt.attr(chn)
            if cnxDict["attrs"][i][e]:
                if nsRig:
                    pm.connectAttr(
                        nsRig + ":" + cnxDict["attrs"][i][e], plug, f=True)
                else:
                    pm.connectAttr(cnxDict["attrs"][i][e], plug, f=True)

        if cnxDict["attrs"][i][13]:
            if nsRig:
                pm.connectAttr(
                    oJnt.parentInverseMatrix[0], nsRig + ":"
                    + cnxDict["attrs"][i][13], f=True)
            else:
                pm.connectAttr(
                    oJnt.parentInverseMatrix[0],
                    cnxDict["attrs"][i][13],
                    f=True)

        # except Exception:
            # pm.displayError("{} is not found in the scene".format(jnt))


def connectCns(cnxDict, nsRig=None, nsSkin=None):
    """Connect the joints using constraints

    Args:
        cnxDict (dict): Description of the deconections to remove
        nsRig (string, optional): rig namespace
        nsSkin (None, optional): model namespace
    """
    for i, jnt in enumerate(cnxDict["joints"]):
        if nsSkin:
            oJnt = pm.PyNode(nsSkin + ":" + jnt)
        else:
            oJnt = pm.PyNode(jnt)

        if cnxDict["attrs"][i][0]:
            if nsRig:
                oAttr = pm.PyNode(nsRig + ":" + cnxDict["attrs"][i][0])
            else:
                oAttr = pm.PyNode(cnxDict["attrs"][i][0])

            oNode = oAttr.node()
            oTrans = pm.listConnections(
                pm.listConnections(oNode.inputMatrix)[0].matrixIn[0])
            pm.parentConstraint(oTrans, oJnt, mo=True)
            pm.scaleConstraint(oTrans, oJnt, mo=True)


def exportConnections(source=None, filePath=None, disc=False):
    """Export connection to a json file wiht .jnn extension

    Args:
        source (list, optional): List of Joints
        filePath (None, optional): Directory path to save the file
        disc (bool, optional): If True, will disconnect the joints.

    Returns:
        set: Decompose matrix nodes. We need to return the decompose
            matrix nodes to track it at export time.
    """
    connections = {}
    connections["joints"] = []
    connections["attrs"] = []
    dm_nodes = []
    if not source:
        source = pm.selected()
    for x in source:
        if not x.name().startswith("blend_"):
            connections["joints"].append(x.name())
            attrs_list = []
            for chn in SRT_CHANNELS:
                at = x.attr(chn)
                at_cnx = pm.listConnections(
                    at, p=True, type="mgear_matrixConstraint")
                if not at_cnx:
                    at_cnx = pm.listConnections(
                        at, p=True, type="decomposeMatrix")
                attrs_list.append(at_cnx)

            parentInv_attr = pm.listConnections(
                x.parentInverseMatrix[0], d=True, p=True)
            attrs_list.append(parentInv_attr)

            attrs_list_checked = []
            for at in attrs_list:
                if at:
                    attrs_list_checked.append(at[0].name())
                    dm_nodes.append(at[0].node())
                else:
                    attrs_list_checked.append(None)

            connections["attrs"].append(attrs_list_checked)

    data_string = json.dumps(connections, indent=4, sort_keys=True)
    if not filePath:
        filePath = pm.fileDialog2(fileMode=0,
                                  fileFilter=' Shifter joint cnx matrix'
                                  '  .jmm (*%s)' % ".jmm")
        if not filePath:
            return
        if not isinstance(filePath, string_types):
            filePath = filePath[0]

    if connections["joints"]:
        with open(filePath, 'w') as f:
            f.write(data_string)

        if disc:
            disconnect(connections)
    # we need to return the decompose matrix nodes to track it at export time.
    return set(dm_nodes)


def importConnections(filePath=None, nsRig=None, nsSkin=None, useMtx=True):
    """import connections  from file

    Args:
        filePath (str, optional): Connection json file pth
        nsRig (str, optional): Rig namespace
        nsSkin (str, optional): mMdel namespace
        useMtx (bool, optional): If True will use matrix multiplication, if
            False, will use constraint connections

    Returns:
        None: None
    """
    if not filePath:
        startDir = pm.workspace(q=True, rootDirectory=True)
        filePath = pm.fileDialog2(fileMode=1,
                                  startingDirectory=startDir,
                                  fileFilter=' Shifter joint cnx matrix '
                                  ' .jmm (*%s)' % ".jmm")
    if not filePath:
        return
    if not isinstance(filePath, string_types):
        filePath = filePath[0]
    with open(filePath) as fp:
        configDict = json.load(fp)

    if useMtx:
        connect(configDict, nsRig=nsRig, nsSkin=nsSkin)
    else:
        connectCns(configDict, nsRig=nsRig, nsSkin=nsSkin)


def getRigTopNode(node=None):
    """Checker to ensure the top rig node is valid

    Args:
        node (dagNode, optional):Rig top node

    Returns:
        str: Rig top node name
    """
    if not node and pm.selected():
        node = pm.selected()[0]
        if not node.hasAttr("is_rig"):
            pm.displayWarning(
                "Please select a valid rig top node!. '{}' "
                "is not a rig top node".format(node.name()))
            return False
        return node.name()
    else:
        pm.displayWarning("Please select a rig top node!")
        return False


def runScript(path=None):
    """Run a custom script file

    Args:
        path (str, optional): Path to the python file
    """
    if path:
        exec(compile(open(path, "rb").read(), path, 'exec'))


@mutils.one_undo
def exportAssetAssembly(name, rigTopNode, meshTopNode, path, postScript=None):
    """Export the asset assembly. Model, rig and connections dict.

    Args:
        name (str): Name of the asset
        rigTopNode (str): Name of the rig top node
        meshTopNode (str): Name of the model top node
        path (str): Pestination directory
        postScript (path, optional): Script to run before export

    Returns:
        None: None
    """
    if pm.ls(rigTopNode):
        rigTopNode = pm.PyNode(rigTopNode)
    else:
        pm.displayError(
            "{} doesn't exist or duplicated. Please check your "
            "scene".format(rigTopNode))
        return

    if pm.ls(meshTopNode):
        meshTopNode = pm.PyNode(meshTopNode)
    else:
        pm.displayError(
            "{} doesn't exist or duplicated. Please check "
            "your scene".format(meshTopNode))
        return
    # check the folder and script
    # if the target name exist abort and request another name

    deformer_jnts = rigTopNode.rigGroups[3].connections()[0].members()
    if not deformer_jnts:
        pm.displayError(
            "{} is empty. The tool can't find any joint".format(meshTopNode))

    # export connections and cut joint connections
    file_path = os.path.join(path, name + ".jmm")
    dm_nodes = exportConnections(source=deformer_jnts,
                                 filePath=file_path,
                                 disc=True)

    # cut al possible remaining connection and adjust hierarchy
    # joint or visibility
    jnt_org = pm.PyNode("jnt_org")
    pm.disconnectAttr(rigTopNode.jnt_vis, jnt_org.visibility)

    # restructure model
    model = pm.createNode("transform",
                          n="model",
                          p=None,
                          ss=True)
    pm.addAttr(model, ln="rigGroups", at='message', m=1)
    pm.parent(meshTopNode, jnt_org, model)

    # disconnect jnt set
    sets = rigTopNode.listConnections(type="objectSet")

    deformersGrp = None
    for oSet in sets:
        if "deformers_grp" in oSet.name():
            deformersGrp = oSet

    if deformersGrp:
        for cnx in deformersGrp.message.listConnections(p=True):
            pm.disconnectAttr(deformersGrp.message, cnx)
        pm.connectAttr(deformersGrp.message, model.attr("rigGroups[0]"))

    # disconnect bindPoses
    dg_poses = rigTopNode.message.listConnections(type="dagPose", p=True)
    for dgp in dg_poses:
        if dgp.node().name().startswith("bindPose"):
            pm.disconnectAttr(rigTopNode.message, dgp)

    # post script
    if postScript:
        try:
            exec(compile(open(postScript, "rb").read(), postScript, 'exec'))
        except Exception as ex:
            template = "An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            pm.displayError(message)
            cont = pm.confirmBox("FAIL: Script Fail",
                                 "Do you want to export anyway?" + "\n\n"
                                 + message + "\n\n" + traceback.format_exc(),
                                 "Continue", "Cancel")
            if not cont:
                pm.undo()
                return

    # export rig model
    pm.select(dm_nodes, r=True)
    pm.select(rigTopNode, add=True)
    file_path = os.path.join(path, name + "_rig.ma")
    exp = pm.exportSelected(file_path, f=True, type="mayaAscii")
    pm.displayInfo(exp)

    # export mesh and joints
    pm.select(model, r=True)
    file_path = os.path.join(path, name + "_model.ma")
    exp = pm.exportSelected(file_path, f=True, type="mayaAscii")
    pm.displayInfo(exp)


def createAssetAssembly(filePath=None, reference=False):
    """Create the asset assembly.

    The assets for asset assembly can be imported o referenced.
    The namespace will be the name of the asset.

    Args:
        filePath (str, optional): Path to the connection dictionary
        reference (bool, optional): If True will create references

    Returns:
        None: None
    """
    if not filePath:
        startDir = pm.workspace(q=True, rootDirectory=True)
        filePath = pm.fileDialog2(fileMode=1,
                                  startingDirectory=startDir,
                                  fileFilter=' Shifter joint cnx matrix '
                                  ' .jmm (*%s)' % ".jmm")

    if not filePath:
        return
    if not isinstance(filePath, string_types):
        filePath = filePath[0]

    asset_name = os.path.basename(filePath).split(".")[0]
    dir_path = os.path.dirname(filePath)

    for part in ["model.ma", "rig.ma"]:
        asset_path = os.path.join(dir_path, "_".join([asset_name, part]))
        if reference:
            ref = True
            imp = False
            message = "Reference"
        else:
            ref = False
            imp = True
            message = "Import"
        pm.displayInfo("{} asset: {} ".format(message, asset_path))
        cmds.file(asset_path,
                  i=imp,
                  reference=ref,
                  type="mayaAscii",
                  ignoreVersion=True,
                  mergeNamespacesOnClash=True,
                  namespace=asset_name)

    # import cnx
    pm.displayInfo("Import connections dictionary ".format(filePath))
    importConnections(filePath, nsRig=asset_name, nsSkin=asset_name)

    # reconnect jont_vis
    root = [x for x in pm.ls(type="transform") if x.hasAttr("is_rig")]
    if root:
        jnt_org = pm.PyNode(asset_name + ":jnt_org")
        pm.connectAttr(root[0].jnt_vis, jnt_org.visibility)


####################################
# Soft tweaks Manager dialog
####################################

class gameToolsUI(QtWidgets.QDialog, gtUI.Ui_gameTools):

    """Game tools UI layout
    """

    def __init__(self, parent=None):
        super(gameToolsUI, self).__init__(parent)
        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.installEventFilter(self)

    def keyPressEvent(self, event):
        if not event.key() == QtCore.Qt.Key_Escape:
            super(gameToolsUI, self).keyPressEvent(event)


class gameTools(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    """Game Tools UI

    Attributes:
        gt_layout (object): Ui Layout

    """

    def __init__(self, parent=None):
        self.toolName = "shifterGameTools"
        super(self.__class__, self).__init__(parent=parent)
        self.gtUIInst = gameToolsUI()

        self.startDir = pm.workspace(q=True, rootDirectory=True)

        self.gameTools_window()
        self.gameTools_layout()
        self.createConnections()

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.installEventFilter(self)

    def keyPressEvent(self, event):
        if not event.key() == QtCore.Qt.Key_Escape:
            super(gameTools, self).keyPressEvent(event)

    def gameTools_window(self):
        """Game tools window
        """
        self.setObjectName(self.toolName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle("Shifter Game Tools")
        self.resize(300, 330)

    def gameTools_layout(self):

        self.gt_layout = QtWidgets.QVBoxLayout()
        self.gt_layout.addWidget(self.gtUIInst)

        self.setLayout(self.gt_layout)

    # Slots
    @staticmethod
    def _validCharacters(lEdit):
        """Validate name charactes

        Args:
            lEdit (object): Qt line edit with name information
        """
        name = string.removeInvalidCharacter(lEdit.text())
        lEdit.setText(name)

    def populateRigTopNode(self):
        """Populate the rig top node information
        """
        topNode = getRigTopNode()
        if topNode:
            self.gtUIInst.rigNode_lineEdit.setText(topNode)

    def populateMeshTopNode(self):
        """Populate the geometry top node information

        Returns:
            bool
        """
        if pm.selected():
            node = pm.selected()[0]
            self.gtUIInst.meshNode_lineEdit.setText(node.name())
        else:
            pm.displayWarning("Please select a Mesh top node!")
            return False

    def populateOutputFolder(self):
        """Populate output path folder

        Returns:
            None: None
        """
        filePath = pm.fileDialog2(fileMode=2,
                                  startingDirectory=self.startDir,
                                  fileFilter=' Shifter Game Assembly folder')
        if not filePath:
            return
        if not isinstance(filePath, string_types):
            filePath = filePath[0]
        self.gtUIInst.path_lineEdit.setText(filePath)

    def populateScript(self):
        """Populate custom script path

        Returns:
            None: None
        """
        filePath = pm.fileDialog2(fileMode=1,
                                  startingDirectory=self.startDir,
                                  fileFilter=' Post Script  .py (*%s)' % ".py")
        if not filePath:
            return
        if not isinstance(filePath, string_types):
            filePath = filePath[0]
        self.gtUIInst.script_lineEdit.setText(filePath)

    def disconnectExport(self):
        """Collect all the information and export the asset assembly
        """
        name = self.gtUIInst.assetName_lineEdit.text()
        rigTopNode = self.gtUIInst.rigNode_lineEdit.text()
        meshTopNode = self.gtUIInst.meshNode_lineEdit.text()
        path = self.gtUIInst.path_lineEdit.text()
        postScript = self.gtUIInst.script_lineEdit.text()

        if name and rigTopNode and meshTopNode and path:
            exportAssetAssembly(
                name, rigTopNode, meshTopNode, path, postScript)
        else:
            pm.displayWarning(
                "Name, Rig Top Node, Mesh Top Node and path "
                "are mandatory fields. Please check it.")

    def importAssembly(self):
        """Import asset assembly
        """
        createAssetAssembly(filePath=None, reference=False)

    def referenceAssembly(self):
        """References the asset assembly
        """
        createAssetAssembly(filePath=None, reference=True)

    # Connect slots
    def createConnections(self):
        """Create slots connections
        """
        self.gtUIInst.assetName_lineEdit.editingFinished.connect(
            partial(gameTools._validCharacters,
                    self.gtUIInst.assetName_lineEdit))
        self.gtUIInst.rigNode_pushButton.clicked.connect(
            self.populateRigTopNode)
        self.gtUIInst.meshNode_pushButton.clicked.connect(
            self.populateMeshTopNode)
        self.gtUIInst.path_pushButton.clicked.connect(
            self.populateOutputFolder)
        self.gtUIInst.script_pushButton.clicked.connect(self.populateScript)
        self.gtUIInst.disconnectExport_pushButton.clicked.connect(
            self.disconnectExport)
        self.gtUIInst.importConnect_pushButton.clicked.connect(
            self.importAssembly)
        self.gtUIInst.referenceConnect_pushButton.clicked.connect(
            self.referenceAssembly)


def openGameTools(*args):
    """Open game tools window

    Args:
        *args: Dummy for Maya
    """
    pyqt.showDialog(gameTools)


if __name__ == "__main__":

    pyqt.showDialog(gameTools)
