import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.cmds as cmds

from mgear.core import callbackManager
import mgear

from mgear.vendor.Qt import QtCore, QtWidgets

from mgear.rigbits.mirror_controls import MirrorController

########################################
#   Load Plugins
########################################
pm.loadPlugin('fbxmaya')
pm.loadPlugin('mayaHIK')

class ConfigureIK():
    HEAD_NAMES = [
        'Head',
        'Neck',
        'Neck1',
        'Neck2',
        'Neck3',
        'Neck4',
        'Neck5',
        'Neck6',
        'Neck7',
        'Neck8',
        'Neck9'
    ]
    SPINE_NAMES = [
        'Hips', 
        'Spine', 
        'Spine1', 
        'Spine2', 
        'Spine3', 
        'Spine4',
        'Spine5',
        'Spine6',
        'Spine7',
        'Spine8',
        'Spine9',
    ]

    LEFT_ARM_NAMES = [
        'LeftShoulder',
        'LeftArm',
        'LeftForeArm',
        'LeftHand'
    ]
    
    LEFT_UPPER_ARM_ROLLS = [
        'LeafLeftArmRoll1',
        'LeafLeftArmRoll2',
        'LeafLeftArmRoll3',
        'LeafLeftArmRoll4',
        'LeafLeftArmRoll5',
    ]
    
    LEFT_LOWER_ARM_ROLLS = [
        'LeafLeftForeArmRoll1',
        'LeafLeftForeArmRoll2',
        'LeafLeftForeArmRoll3',
        'LeafLeftForeArmRoll4',
        'LeafLeftForeArmRoll5',
    ]

    LEFT_LEG_NAMES = [
        'LeftUpLeg',
        'LeftLeg',
        'LeftFoot',
        'LeftToeBase'
    ]

    LEFT_UPPER_LEG_ROLLS = [
        'LeafLegUpLegRoll1',
        'LeafLegUpLegRoll2',
        'LeafLegUpLegRoll3',
        'LeafLegUpLegRoll4',
        'LeafLegUpLegRoll5',
    ]
    LEFT_LOWER_LEG_ROLLS = [
        'LeafLegLegRoll1',
        'LeafLegLegRoll2',
        'LeafLegLegRoll3',
        'LeafLegLegRoll4',
        'LeafLegLegRoll5',
    ]

    # def __init__(self):
    #     selection = cmds.ls(sl=1)[0]
    #     self.hikChar = self.set_character(selection)

    @classmethod
    def set_character(cls):
        selection = cmds.ls(sl=1)
        if not selection:
            cmds.error('Must have reference bone selected')
            return
        reference_bone = selection[-1]

        pm.mel.HIKCharacterControlsTool()
     
        charName = 'MGearIKHuman'
        if pm.mel.hikGetCurrentCharacter() != charName:
            print('doesnt match')
        else:
            print('match')

        tmp = set(pm.ls(type='HIKCharacterNode'))
        pm.mel.hikCreateDefinition()
        hikChar = list(set(pm.ls(type='HIKCharacterNode')) - tmp)[0]
        hikChar.rename(charName)
        pm.mel.hikSetCurrentCharacter(hikChar)
        
        if reference_bone:
            pm.mel.setCharacterObject(reference_bone, hikChar, pm.mel.hikGetNodeIdFromName('Reference'), 0)

        pm.mel.hikUpdateDefinitionUI()
        

    @classmethod
    def set_list_of_bones_from_selection(cls, bones_list, sel, do_mirror=False):
        if do_mirror:
            if 'Left' in bones_list[0]:
                mirror_bone_list = [bone.replace('Left', 'Right') for bone in bones_list]
            elif 'Right' in bones_list[0]:
                mirror_bone_list = [bone.replace('Right', 'Left') for bone in bones_list]
            else:
                do_mirror = False

        hikChar = pm.mel.hikGetCurrentCharacter()
        print(bones_list)
        for index, ctrl in enumerate(sel):
            print(ctrl)
            print(bones_list[index])
            pm.mel.setCharacterObject(ctrl, hikChar, pm.mel.hikGetNodeIdFromName(bones_list[index]), 0)
            if do_mirror:
                opposite_ctrl = MirrorController.get_opposite_control(pm.PyNode(sel[index]))
                pm.mel.setCharacterObject(opposite_ctrl, hikChar, pm.mel.hikGetNodeIdFromName(mirror_bone_list[index]), 0)



        pm.mel.hikUpdateDefinitionUI()
        return





class ConfigureIKUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(ConfigureIKUI, self).__init__(parent)

        # self.func = MirrorController()

        self.setWindowTitle("Configure ikHuman")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)
        self.setMinimumSize(QtCore.QSize(350, 0))
        
        self.create_widgets()
        self.create_layout()
        self.create_connections()

        
    def create_widgets(self):
        self.image_lb = QtWidgets.QLabel()
        self.image_lb.setPixmap(r"D:\gallo\Documents\MGear\humanIk02.png")

        self.initialize_btn = QtWidgets.QPushButton("Initialize")
        
        self.head_btn = QtWidgets.QPushButton("Head")
        self.head_btn.setToolTip("\n".join(ConfigureIK.SPINE_NAMES))
        self.spine_btn = QtWidgets.QPushButton("Spine")

        self.left_arm_btn = QtWidgets.QPushButton("Left Arm")
        self.left_upper_arm_rolls_btn = QtWidgets.QPushButton("Left Upper Arm Rolls")
        self.left_lower_arm_rolls_btn = QtWidgets.QPushButton("Left Lower Arm Rolls")
        self.left_hand_btn = QtWidgets.QPushButton("Left Hand")

        self.right_arm_btn = QtWidgets.QPushButton("Right Arm")
        self.right_upper_arm_rolls_btn = QtWidgets.QPushButton("Right Upper Arm Rolls")
        self.right_lower_arm_rolls_btn = QtWidgets.QPushButton("Right Lower Arm Rolls")
        self.right_hand_btn = QtWidgets.QPushButton("Right Hand")

        self.left_leg_btn = QtWidgets.QPushButton("Left Leg")
        self.left_upper_leg_rolls_btn = QtWidgets.QPushButton("Left Upper Leg Rolls")
        self.left_lower_leg_rolls_btn = QtWidgets.QPushButton("Left Lower Leg Rolls")

        self.right_leg_btn = QtWidgets.QPushButton("Right Leg")
        self.right_upper_leg_rolls_btn = QtWidgets.QPushButton("Right Upper Leg Rolls")
        self.right_lower_leg_rolls_btn = QtWidgets.QPushButton("Right Lower Leg Rolls")
        
        self.mirror_checkbox = QtWidgets.QCheckBox("Apply mirror")
        self.mirror_checkbox.setChecked(True)
        
        self.instructions_tb = QtWidgets.QTextEdit()
        self.instructions_tb.setText("1. Select the Reference Bone Ctrl and click initialize \n"
                                     "2. Click the element you want to configure \n"  
                                     "3. Select the elements in the indicated order and click confirm. \n"
                                     "Note: Bones that have a number in their name are not mandatory. ")
        self.instructions_tb.setReadOnly(True)

        
    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        main_layout.addWidget(self.initialize_btn)
        
        configure_gb = QtWidgets.QGroupBox("Configure")
        main_layout.addWidget(configure_gb)
        configure_layout = QtWidgets.QVBoxLayout()
        configure_gb.setLayout(configure_layout)
        
        configure_layout.addWidget(self.head_btn)
        configure_layout.addLayout(self._group_in_hlayout(self.right_arm_btn, self.left_arm_btn))
        configure_layout.addLayout(self._group_in_hlayout(
                                       self.right_lower_arm_rolls_btn,
                                       self.right_upper_arm_rolls_btn,
                                       self.left_upper_arm_rolls_btn,
                                       self.left_lower_arm_rolls_btn
                                   ))
        configure_layout.addLayout(self._group_in_hlayout(self.right_hand_btn, self.left_hand_btn))
        configure_layout.addWidget(self.spine_btn)
        configure_layout.addLayout(self._group_in_hlayout(self.right_leg_btn, self.left_leg_btn))
        configure_layout.addLayout(self._group_in_hlayout(
                                        self.right_lower_leg_rolls_btn,
                                        self.right_upper_leg_rolls_btn,
                                        self.left_upper_leg_rolls_btn,
                                        self.left_lower_leg_rolls_btn
                                    ))
        
        mirror_layout = QtWidgets.QHBoxLayout()
        mirror_layout.addStretch()
        mirror_layout.addWidget(self.mirror_checkbox)
        configure_layout.addLayout(mirror_layout)
        
        main_layout.addStretch()
        
        instructions_gb = QtWidgets.QGroupBox("Instructions")
        instructions_layout = QtWidgets.QVBoxLayout()
        instructions_gb.setLayout(instructions_layout)
        
        instructions_layout.addWidget(self.instructions_tb)
        
        main_layout.addWidget(instructions_gb)
        
    def create_connections(self):
        self.initialize_btn.clicked.connect(ConfigureIK.set_character)

        self.head_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.HEAD_NAMES))

        self.left_arm_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_ARM_NAMES))
        self.left_upper_arm_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_UPPER_ARM_ROLLS))
        self.left_lower_arm_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_LOWER_ARM_ROLLS))

        self.right_arm_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_ARM_NAMES))
        self.right_upper_arm_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_UPPER_ARM_ROLLS))
        self.right_lower_arm_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_LOWER_ARM_ROLLS))

        self.spine_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.SPINE_NAMES))

        self.left_leg_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_LEG_NAMES))
        self.left_upper_leg_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_UPPER_LEG_ROLLS))
        self.left_lower_leg_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_LOWER_LEG_ROLLS))

        self.right_leg_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_LEG_NAMES))
        self.right_upper_leg_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_UPPER_LEG_ROLLS))
        self.right_lower_leg_rolls_btn.clicked.connect(self.display_list_mb_cb(ConfigureIK.LEFT_LOWER_LEG_ROLLS))

    def _group_in_hlayout(self, *args):
        h_layout = QtWidgets.QHBoxLayout()
        for i in args:
            h_layout.addWidget(i)
            
        return h_layout
    
    def display_list_mb_cb(self, bone_list):
        def display():
            dialog = BoneListDialog(self, bone_list, self.mirror_checkbox.isChecked())
            dialog.show()
            
        return display
        
        
class BoneListDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, bone_list=[], do_mirror=False):
        super(BoneListDialog, self).__init__(parent)

        # self.func = MirrorController()

        self.setWindowTitle("Limb Selection Order")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)
        self.setMinimumSize(QtCore.QSize(350, 250))
        
        self.bone_list = bone_list
        self.do_mirror = do_mirror

        self.create_widgets()
        self.create_layout()
        self.create_connections()
        
        self.cb_manager = callbackManager.CallbackManager()
        self.add_callback()

    def close(self):
        self.cb_manager.removeAllManagedCB()
        self.deleteLater()

    def closeEvent(self, evnt):
        self.close()

    def dockCloseEventTriggered(self):
        self.close()
        
    def create_widgets(self):
        self.bone_te = QtWidgets.QTextEdit()
        self.bone_te.setText("\n".join(self.bone_list))
        self.bone_te.setReadOnly(True)
        
        self.selection_lw = QtWidgets.QListWidget()
        
        self.confirm_btn = QtWidgets.QPushButton("Confirm")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        
    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        
        text_layout = QtWidgets.QHBoxLayout()
        text_layout.addWidget(self.bone_te)
        text_layout.addWidget(self.selection_lw)
        
        main_layout.addLayout(text_layout)
        
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.confirm_btn)
        
        main_layout.addLayout(buttons_layout)
        
    def create_connections(self):
        self.cancel_btn.clicked.connect(self.close)
        self.confirm_btn.clicked.connect(self.confirm_cb)
        
    def add_callback(self):
        self.cb_manager.selectionChangedCB(
            "BoneListDialog_selection_CB", self.selection_changed
        )
        
    def selection_changed(self, *args):
        self.selection_lw.clear()
        selection = cmds.ls(sl=1)
        for i in selection:
            self.selection_lw.addItem(i)

    def confirm_cb(self):
        selection = cmds.ls(sl=1)
        ConfigureIK.set_list_of_bones_from_selection(self.bone_list, selection, self.do_mirror)
        self.close()
    

def show(*args):
    mgear.core.pyqt.showDialog(ConfigureIKUI)


if __name__ == "__main__":
    show()
