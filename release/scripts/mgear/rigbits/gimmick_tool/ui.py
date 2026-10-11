"""Gimmick Joints - Create, mirror and manage blend and support joints.

Dockable window over :mod:`mgear.rigbits.gimmick_tool.core`: add deformer,
blend and support joints to the selection, mirror them to the other side,
flip support orientations, select or delete them by side, and import or
export ``.gst`` files.
"""

import os
from functools import partial

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from mgear import rigbits
from mgear.core import pyqt
from mgear.core import utils

from maya import cmds
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from . import core

MIRROR_LABELS = (
    ("Left to Right", core.LEFT_TO_RIGHT),
    ("Right to Left", core.RIGHT_TO_LEFT),
)


class GimmickJointsUI(MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin):
    """Dockable window to create and manage gimmick joints."""

    toolName = "GimmickJoints"

    def __init__(self, parent=None):
        """Initialize the window.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(GimmickJointsUI, self).__init__(parent)
        pyqt.SettingsMixin.__init__(self)

        self.setObjectName(self.toolName)
        self.setWindowTitle("Gimmick Joints")
        self.setWindowIcon(QtGui.QIcon(pyqt.get_icon("mgear_gimmick_joints")))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setMinimumWidth(260)

        if cmds.about(ntOS=True):
            flags = self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
            self.setWindowFlags(flags)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.setup_ui()

        self.user_settings = {
            "gimmick_joints_blend": (self.blend_spin, 0.5),
            "gimmick_joints_mirror": (self.mirror_combo, 0),
            "gimmick_joints_mirror_replace": (self.replace_check, False),
        }
        for side in core.SIDES:
            key = "gimmick_joints_" + side.lower()
            self.user_settings[key] = (self.side_checks[side], True)
        self.load_settings()

    # =========================================================
    # UI SETUP
    # =========================================================

    def setup_ui(self):
        """Build the window."""
        self.create_actions()
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_actions(self):
        """Create the File menu actions."""
        self.import_action = QtWidgets.QAction("Import...", self)
        self.import_action.setIcon(pyqt.get_icon("mgear_log-in"))
        self.export_all_action = QtWidgets.QAction("Export All...", self)
        self.export_all_action.setIcon(pyqt.get_icon("mgear_log-out"))
        self.export_selected_action = QtWidgets.QAction("Export Selected...", self)

    def create_widgets(self):
        """Create the widgets."""
        self.menu_bar = QtWidgets.QMenuBar()
        file_menu = self.menu_bar.addMenu("File")
        file_menu.addAction(self.import_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_all_action)
        file_menu.addAction(self.export_selected_action)

        self.add_joint_btn = QtWidgets.QPushButton("Add Joint")
        self.add_joint_btn.setToolTip(
            "Add a deformer joint driven by each selected object"
        )
        self.add_blend_btn = QtWidgets.QPushButton("Add Blended Joint")
        self.add_blend_btn.setToolTip(
            "Add a joint that follows a part of the rotation of each selected joint"
        )
        self.blend_spin = QtWidgets.QDoubleSpinBox()
        self.blend_spin.setRange(0.0, 1.0)
        self.blend_spin.setSingleStep(0.05)
        self.blend_spin.setDecimals(2)
        self.blend_spin.setToolTip("Rotation blend of new blended joints")
        self.add_support_btn = QtWidgets.QPushButton("Add Support Joint")
        self.add_support_btn.setToolTip(
            "Add a support joint under each selected blended joint"
        )

        self.mirror_combo = QtWidgets.QComboBox()
        for label, _direction in MIRROR_LABELS:
            self.mirror_combo.addItem(label)
        self.replace_check = QtWidgets.QCheckBox("Replace")
        self.replace_check.setToolTip("Rebuild the mirrored joints that already exist")
        self.mirror_btn = QtWidgets.QPushButton("Mirror")
        self.mirror_btn.setToolTip(
            "Mirror the selected gimmick joints, or all of the side when "
            "nothing is selected"
        )

        self.flip_btns = {}
        for axis in core.AXES:
            self.flip_btns[axis] = QtWidgets.QPushButton(axis)
            self.flip_btns[axis].setToolTip(
                "Flip the orientation of the selected support joints on "
                "{}".format(axis)
            )

        self.side_checks = {}
        for side in core.SIDES:
            self.side_checks[side] = QtWidgets.QCheckBox(side)
        self.select_btn = QtWidgets.QPushButton("Select")
        self.delete_btn = QtWidgets.QPushButton("Delete")

    def create_layout(self):
        """Arrange the widgets."""
        blend_layout = QtWidgets.QHBoxLayout()
        blend_layout.addWidget(self.add_blend_btn, 1)
        blend_layout.addWidget(QtWidgets.QLabel("Blend"))
        blend_layout.addWidget(self.blend_spin)

        create_layout = QtWidgets.QVBoxLayout()
        create_layout.addWidget(self.add_joint_btn)
        create_layout.addLayout(blend_layout)
        create_layout.addWidget(self.add_support_btn)
        create_group = QtWidgets.QGroupBox("Create")
        create_group.setLayout(create_layout)

        mirror_layout = QtWidgets.QHBoxLayout()
        mirror_layout.addWidget(self.mirror_combo, 1)
        mirror_layout.addWidget(self.replace_check)
        mirror_layout.addWidget(self.mirror_btn)
        mirror_group = QtWidgets.QGroupBox("Mirror")
        mirror_group.setLayout(mirror_layout)

        flip_layout = QtWidgets.QHBoxLayout()
        for btn in self.flip_btns.values():
            flip_layout.addWidget(btn)
        flip_group = QtWidgets.QGroupBox("Flip Support Orientation")
        flip_group.setLayout(flip_layout)

        side_layout = QtWidgets.QHBoxLayout()
        for side in core.SIDES:
            side_layout.addWidget(self.side_checks[side])
        side_btn_layout = QtWidgets.QHBoxLayout()
        side_btn_layout.addWidget(self.select_btn)
        side_btn_layout.addWidget(self.delete_btn)
        side_group_layout = QtWidgets.QVBoxLayout()
        side_group_layout.addLayout(side_layout)
        side_group_layout.addLayout(side_btn_layout)
        side_group = QtWidgets.QGroupBox("Select / Delete")
        side_group.setLayout(side_group_layout)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setMenuBar(self.menu_bar)
        main_layout.addWidget(create_group)
        main_layout.addWidget(mirror_group)
        main_layout.addWidget(flip_group)
        main_layout.addWidget(side_group)
        main_layout.addStretch()

    def create_connections(self):
        """Connect the signals."""
        self.add_joint_btn.clicked.connect(self.add_joint)
        self.add_blend_btn.clicked.connect(self.add_blend_joint)
        self.add_support_btn.clicked.connect(self.add_support_joint)
        self.mirror_btn.clicked.connect(self.mirror)
        for axis, btn in self.flip_btns.items():
            btn.clicked.connect(partial(self.flip, axis))
        self.select_btn.clicked.connect(self.select_by_side)
        self.delete_btn.clicked.connect(self.delete_by_side)
        self.import_action.triggered.connect(self.import_file)
        self.export_all_action.triggered.connect(partial(self.export_file, False))
        self.export_selected_action.triggered.connect(partial(self.export_file, True))

    # =========================================================
    # HELPERS
    # =========================================================

    def selected_sides(self):
        """Get the sides checked in the Select / Delete section.

        Returns:
            list of str: Checked sides.
        """
        return [s for s in core.SIDES if self.side_checks[s].isChecked()]

    def _selected(self, kinds=None):
        """Get the selected joints.

        Args:
            kinds (tuple of str, optional): Keep only gimmick joints of these
                kinds, i.e. ``core.KINDS`` for any gimmick joint.

        Returns:
            list of str: Selected joints.
        """
        selection = cmds.ls(selection=True, type="joint") or []
        if kinds:
            selection = [j for j in selection if core.get_kind(j) in kinds]
        return selection

    def _start_dir(self):
        """Get the folder the file dialogs open in.

        Returns:
            str: The scene folder, or the project's scenes folder.
        """
        scene = cmds.file(query=True, sceneName=True)
        if scene:
            return os.path.dirname(scene)
        return utils.get_workspace_folder(rule="scenes")

    # =========================================================
    # ACTIONS
    # =========================================================

    def add_joint(self):
        """Add a deformer joint to each selected object."""
        if not cmds.ls(selection=True, transforms=True):
            cmds.warning("Select one or more objects to add joints to")
            return
        with utils.undo_chunk("gimmickAddJoint"):
            rigbits.addJnt()

    def add_blend_joint(self):
        """Add a blended joint to each selected joint."""
        joints = self._selected()
        if not joints:
            cmds.warning("Select one or more joints to add blended joints to")
            return
        with utils.undo_chunk("gimmickAddBlendJoint"):
            created = [
                core.create_blend_joint(j, blend=self.blend_spin.value())
                for j in joints
            ]
            created = [c for c in created if c]
            if created:
                cmds.select(created)

    def add_support_joint(self):
        """Add a support joint under each selected blended joint."""
        joints = self._selected((core.BLEND,))
        if not joints:
            cmds.warning("Select one or more blended joints")
            return
        with utils.undo_chunk("gimmickAddSupportJoint"):
            cmds.select([core.create_support_joint(j) for j in joints])

    def mirror(self):
        """Mirror the selected gimmick joints, or all of the source side."""
        direction = MIRROR_LABELS[self.mirror_combo.currentIndex()][1]
        joints = self._selected(core.KINDS) or None
        with utils.undo_chunk("gimmickMirror"):
            created = core.mirror_gimmick_joints(
                joints=joints,
                direction=direction,
                replace=self.replace_check.isChecked(),
            )
        if not created:
            cmds.warning("No gimmick joints were mirrored")
            return
        cmds.select(created)

    def flip(self, axis):
        """Flip the orientation of the selected support joints.

        Args:
            axis (str): ``X``, ``Y`` or ``Z``.
        """
        joints = self._selected((core.SUPPORT,))
        if not joints:
            cmds.warning("Select one or more support joints")
            return
        with utils.undo_chunk("gimmickFlip"):
            core.flip_orientation(joints, axis)

    def select_by_side(self):
        """Select the gimmick joints of the checked sides."""
        joints = core.list_gimmick_joints(side=self.selected_sides())
        if not joints:
            cmds.warning("No gimmick joints on the checked sides")
            cmds.select(clear=True)
            return
        cmds.select(joints)

    def delete_by_side(self):
        """Delete the gimmick joints of the checked sides."""
        joints = core.list_gimmick_joints(side=self.selected_sides())
        if not joints:
            cmds.warning("No gimmick joints on the checked sides")
            return
        with utils.undo_chunk("gimmickDelete"):
            core.delete_gimmick_joints(joints)

    def import_file(self):
        """Import a ``.gst`` file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Gimmick Joints", self._start_dir(), core.FILE_FILTER
        )
        if not path:
            return
        try:
            with utils.undo_chunk("gimmickImport"):
                created = core.import_file(path)
        except ValueError as e:
            cmds.warning(str(e))
            return
        if created:
            cmds.select(created)

    def export_file(self, selected_only=False):
        """Export gimmick joints to a ``.gst`` file.

        Args:
            selected_only (bool, optional): Export only the selected gimmick
                joints (and the supports of selected blended joints).
        """
        if selected_only:
            joints = self._selected(core.KINDS)
            if not joints:
                cmds.warning("Select one or more gimmick joints to export")
                return
        else:
            joints = core.list_gimmick_joints()
            if not joints:
                cmds.warning("No gimmick joints to export")
                return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Gimmick Joints", self._start_dir(), core.FILE_FILTER
        )
        if not path:
            return
        path = core.export_file(path, joints=joints)
        if path:
            cmds.inViewMessage(
                assistMessage="Gimmick joints exported: {}".format(path),
                position="topCenter",
                fade=True,
            )

    # =========================================================
    # MAYA INTEGRATION
    # =========================================================

    def closeEvent(self, event):
        """Save the settings when the window is closed.

        Args:
            event (QtGui.QCloseEvent): Close event.
        """
        self.save_settings()
        super(GimmickJointsUI, self).closeEvent(event)

    def dockCloseEventTriggered(self):
        """Save the settings when the docked window is closed."""
        self.save_settings()


def show(*args):
    """Show the Gimmick Joints window.

    Returns:
        GimmickJointsUI: The window.
    """
    return pyqt.showDialog(GimmickJointsUI, dockable=True)
