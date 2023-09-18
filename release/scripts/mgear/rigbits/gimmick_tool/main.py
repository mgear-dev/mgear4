import os

import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from PySide2 import QtWidgets, QtCore
from PySide2.QtUiTools import QUiLoader

from mgear.core import pyqt
from . import core


def mainUI():
    pyqt.showDialog(GimmickSetupWindow)


class GimmickSetupWindow(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):
    
    def __init__(self, parent=None):
        super(GimmickSetupWindow, self).__init__(parent)
        
        self.widget = self.initUI()
        
        self.toolName = self.widget.windowTitle()
        self.setMenuIcon()
        self.setCentralWidget(self.widget)
        self.setWindowTitle(self.toolName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)
        self.setObjectName(self.toolName)
        self.state = False
        
        self.connectCommand()

    def initUI(self, uiPath=None):
        if not uiPath:
            dirname = os.path.dirname(__file__)
            basename = os.path.basename(dirname)
            uiPath = "{path}/{name}.ui".format(path=dirname, name=basename)

        f = QtCore.QFile(uiPath)
        f.open(QtCore.QFile.ReadOnly)

        widget = QUiLoader().load(f, parentWidget=None)
        return widget
    
    def setMenuIcon(self):
        importIcon = pyqt.get_icon("mgear_log-in")
        exportIcon = pyqt.get_icon("mgear_log-out")
        self.widget.importGimmick_menuAction.setIcon(importIcon)
        self.widget.exportGimmick_menuAction.setIcon(exportIcon)
    
    def connectCommand(self):
        self.widget.blendJoint_pushButton.clicked.connect(self._createBlendJointCmd)
        self.widget.supportJoint_pushButton.clicked.connect(self._createSupportJntCmd)
        self.widget.mirrorGimmick_pushButton.clicked.connect(self._mirrorCmd)
        self.widget.select_pushButton.clicked.connect(self._selectGimmickJntCmd)
        self.widget.delete_pushButton.clicked.connect(self._deleteGimmickJntCmd)
        self.widget.utility_all_checkBox.stateChanged.connect(self._changeAllStateCmd)
        
        # menu
        self.widget.importGimmick_menuAction.triggered.connect(self._importGimmickData)
        self.widget.exportGimmick_menuAction.triggered.connect(self._exportGimmickData)

    def _createBlendJointCmd(self):
        sideStr = self._getGimmickSide()
        gimmickJnt = core.GimmickBlend(side=sideStr, multi=2)
        gimmickJnt.create()
        
    def _createSupportJntCmd(self):
        sideStr = self._getGimmickSide()
        gimmickJnt = core.GimmickSupport(side=sideStr, multi=2)
        gimmickJnt.create()
        
    def _mirrorCmd(self):
        gimmickJnt = core.GimmickBlend(multi=2)
        gimmickJnt.mirror()
        
    def _getGimmickSide(self):
        if self.widget.creation_side_left_radioButton.isChecked():
            return "Left"
        elif self.widget.creation_side_right_radioButton.isChecked():
            return "Right"
        elif self.widget.creation_side_center_radioButton.isChecked():
            return "Center"
        
    def _selectGimmickJntCmd(self):
        joints, sideList = [], []
        if self.widget.utility_left_checkBox.isChecked():
            sideList.append("Left")
        if self.widget.utility_right_checkBox.isChecked():
            sideList.append("Right")
        if self.widget.utility_center_checkBox.isChecked():
            sideList.append("Center")
        
        gimmickJnt = core.GimmickJoint()
        for sideStr in sideList:
            joints.extend(gimmickJnt.select("Blend", side=sideStr))
        pm.select(joints)
        return joints
    
    def _changeAllStateCmd(self):
        if not self.state:
            self.widget.utility_left_checkBox.setChecked(True)
            self.widget.utility_right_checkBox.setChecked(True)
            self.widget.utility_center_checkBox.setChecked(True)
            self.state = True
        else:
            self.widget.utility_left_checkBox.setChecked(False)
            self.widget.utility_right_checkBox.setChecked(False)
            self.widget.utility_center_checkBox.setChecked(False)
            self.state = False

    def _deleteGimmickJntCmd(self):
        gimmick = self._selectGimmickJntCmd()
        pm.delete(gimmick)
        
    def _importGimmickData(self):
        gimmick = core.GimmickJointIO()
        gimmick.importGimmickJoint()
    
    def _exportGimmickData(self):
        gimmick = core.GimmickJointIO()
        gimmick.exportGimmickJoint()
