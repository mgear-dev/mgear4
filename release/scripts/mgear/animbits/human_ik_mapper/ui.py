"""HumanIK Mapper window."""

import os
from functools import partial

from mgear.core import callbackManager
from mgear.core import node_remap
from mgear.core import pyqt

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from maya import cmds
from maya.api import OpenMaya as om2
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from . import batch
from . import constants
from . import core

STATUS_COLORS = {
    constants.STATUS_COMPLETE: "#4f8f4f",
    constants.STATUS_PARTIAL: "#b37d2e",
}
UNMAPPED_COLOR = "#808080"
NONE_SOURCE = "(none)"

# body part rows of the mapping buttons, right side on the left as in a
# front view of the character
BODY_LAYOUT = (
    (("head", "Head"),),
    (("right_arm", "R Arm"), ("left_arm", "L Arm")),
    (
        ("right_lower_arm_rolls", "R ForeArm Rolls"),
        ("right_upper_arm_rolls", "R Arm Rolls"),
        ("left_upper_arm_rolls", "L Arm Rolls"),
        ("left_lower_arm_rolls", "L ForeArm Rolls"),
    ),
    (("right_hand", "R Hand"), ("left_hand", "L Hand")),
    (("spine", "Spine"),),
    (("right_leg", "R Leg"), ("left_leg", "L Leg")),
    (
        ("right_lower_leg_rolls", "R Leg Rolls"),
        ("right_upper_leg_rolls", "R UpLeg Rolls"),
        ("left_upper_leg_rolls", "L UpLeg Rolls"),
        ("left_lower_leg_rolls", "L Leg Rolls"),
    ),
)

# button label of each body part
PART_LABELS = {key: label for row in BODY_LAYOUT for key, label in row}

MIRROR_KEY = "mirror"
MAPPED_ONLY_KEY = "mapped_only"
NEW_LAYER_KEY = "new_layer"
PRE_ROLL_KEY = "pre_roll"
BATCH_MODE_KEY = "batch_mode"
REMOVE_REFS_KEY = "remove_references"


def _all_bones():
    bones = [constants.REFERENCE]
    for part_bones in constants.BODY_PART_BONES.values():
        bones.extend(bone for bone in part_bones if bone not in bones)
    return bones


def _file_dialog(caption, file_filter, mode):
    """Show a Maya file dialog.

    Args:
        caption (str): Dialog caption.
        file_filter (str): File filter.
        mode (int): ``fileDialog2`` file mode (0 save, 1 open, 4 several).

    Returns:
        list: The chosen paths, empty when cancelled.
    """
    return (
        cmds.fileDialog2(caption=caption, fileFilter=file_filter, fileMode=mode) or []
    )


def run_core(parent, func, *args, **kwargs):
    """Run a core function, handling the expected HumanIK Mapper errors.

    Locked channels ask the user to unlock them, then retry with
    ``unlock_channels=True``. Other mapper errors are shown as warnings.
    Unexpected errors propagate.

    Args:
        parent (QtWidgets.QWidget): Parent of the unlock dialog.
        func (callable): Core function.
        *args: Function arguments.
        **kwargs: Function keyword arguments.

    Returns:
        tuple: ``(ok, result)``; ``ok`` is False when cancelled or failed.
    """
    try:
        return True, func(*args, **kwargs)
    except core.LockedChannelsError as error:
        if not LockedCtrlsDialog(error.controls, parent=parent).exec_():
            return False, None
        kwargs["unlock_channels"] = True
        return run_core(parent, func, *args, **kwargs)
    except core.HumanIKMapperError as error:
        cmds.warning("HumanIK Mapper: {}".format(error))
        return False, None


class SourceComboBox(QtWidgets.QComboBox):
    """Combo box that refreshes its items before showing them."""

    aboutToShow = QtCore.Signal()

    def showPopup(self):
        self.aboutToShow.emit()
        super(SourceComboBox, self).showPopup()


class HumanIKMapperUI(MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin):
    """Dockable HumanIK Mapper window."""

    toolName = "mgearHumanIKMapper"

    def __init__(self, parent=None):
        """Initialize the window.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(HumanIKMapperUI, self).__init__(parent)
        pyqt.SettingsMixin.__init__(self)

        self.closed = False
        self.callbacks = callbackManager.CallbackManager()
        self.scene_refresh = pyqt.CoalescedCall(self._scene_changed)
        self.mapping = {}
        self.part_buttons = {}
        self.part_status = {}
        # mapping table row of each bone
        self.table_rows = {}
        self.pairing_dialog = None

        self.setObjectName(self.toolName)
        self.setWindowTitle("HumanIK Mapper")
        self.setMinimumWidth(pyqt.dpi_scale(340))
        if cmds.about(ntOS=True):
            flags = self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
            self.setWindowFlags(flags)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.create_actions()
        self.create_widgets()
        self.create_layout()

        self.user_settings = {
            MIRROR_KEY: (self.mirror_cb, True),
            MAPPED_ONLY_KEY: (self.mapped_only_cb, False),
            NEW_LAYER_KEY: (self.new_layer_cb, False),
            PRE_ROLL_KEY: (self.pre_roll_sb, 0),
            BATCH_MODE_KEY: (self.batch_mode_combo, 0),
            REMOVE_REFS_KEY: (self.remove_refs_cb, True),
        }
        self.load_settings()

        self.create_connections()
        self.refresh()
        self._start_callbacks()

    # -----------------------------------------------------------------
    # Build
    # -----------------------------------------------------------------
    def create_actions(self):
        self.import_action = QtWidgets.QAction("Import Mapping...", self)
        self.export_action = QtWidgets.QAction("Export Mapping...", self)
        self.refresh_action = QtWidgets.QAction("Refresh", self)
        self.hik_window_action = QtWidgets.QAction("Open HumanIK Window", self)
        self.bake_action = QtWidgets.QAction("Bake", self)
        self.bake_timeline_action = QtWidgets.QAction("Bake to Timeline", self)
        self.bake_timeline_action.setToolTip(
            "Bake the source and move the keys into a Time Editor clip"
        )

    def create_widgets(self):
        self.menu_bar = QtWidgets.QMenuBar()
        file_menu = self.menu_bar.addMenu("File")
        file_menu.addAction(self.import_action)
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.refresh_action)
        file_menu.addAction(self.hik_window_action)
        bake_menu = self.menu_bar.addMenu("Bake")
        bake_menu.addAction(self.bake_action)
        bake_menu.addAction(self.bake_timeline_action)

        # character
        self.character_lb = QtWidgets.QLabel()
        self.initialize_btn = QtWidgets.QPushButton("Initialize")
        self.initialize_btn.setToolTip(
            "Select the rig's reference control (world or global control) "
            "to create the HumanIK character, or set its Reference"
        )

        # source and bake
        self.source_combo = SourceComboBox()
        self.source_combo.setToolTip(
            "The HumanIK character (mocap, other character) driving the rig"
        )
        self.bake_btn = QtWidgets.QPushButton("Bake")
        self.bake_btn.setToolTip("Bake the source on the mapped controls")
        self.new_layer_cb = QtWidgets.QCheckBox("New layer")
        self.new_layer_cb.setToolTip("Bake into a new animation layer")
        self.layer_le = QtWidgets.QLineEdit()
        self.layer_le.setPlaceholderText("Layer name (source name)")
        self.pre_roll_sb = QtWidgets.QSpinBox()
        self.pre_roll_sb.setRange(0, 1000)
        self.pre_roll_sb.setPrefix("Pre-roll ")
        self.pre_roll_sb.setToolTip(
            "Frames evaluated before the start, without keys, to settle the "
            "first frames"
        )

        # mapping
        for row in BODY_LAYOUT:
            for key, label in row:
                button = QtWidgets.QPushButton(label)
                button.setMinimumWidth(pyqt.dpi_scale(40))
                self.part_buttons[key] = button
        self.mirror_cb = QtWidgets.QCheckBox("Mirror")
        self.mirror_cb.setToolTip(
            "Also map the opposite side bones to the opposite controls"
        )
        self.filter_le = QtWidgets.QLineEdit()
        self.filter_le.setPlaceholderText("Filter bones or controls")
        self.filter_le.setClearButtonEnabled(True)
        self.mapped_only_cb = QtWidgets.QCheckBox("Mapped only")
        self.mapping_table = QtWidgets.QTableWidget(0, 3)
        self.mapping_table.setHorizontalHeaderLabels(["Bone", "Control", "Sub IK"])
        self.mapping_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.mapping_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.mapping_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.mapping_table.verticalHeader().setVisible(False)
        header = self.mapping_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.mapping_table.setToolTip(
            "Double-click to select the control; right-click for actions"
        )
        for bone in _all_bones():
            self._add_table_row(bone)

        # batch
        self.batch_list = QtWidgets.QListWidget()
        self.batch_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_files_btn = QtWidgets.QPushButton("Add...")
        self.remove_files_btn = QtWidgets.QPushButton("Remove")
        self.load_list_btn = QtWidgets.QPushButton("Load List...")
        self.save_list_btn = QtWidgets.QPushButton("Save List...")
        self.batch_mode_combo = QtWidgets.QComboBox()
        self.batch_mode_combo.addItem("Layer per file", batch.MODE_LAYERS)
        self.batch_mode_combo.addItem("Time Editor clips", batch.MODE_TIMELINE)
        self.remove_refs_cb = QtWidgets.QCheckBox("Remove references")
        self.remove_refs_cb.setToolTip("Remove each file's reference after its bake")
        self.batch_bake_btn = QtWidgets.QPushButton("Batch Bake")
        self.report_tree = QtWidgets.QTreeWidget()
        self.report_tree.setHeaderLabels(["File", "Status", "Range / Message"])
        self.report_tree.setRootIsDecorated(False)

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setMenuBar(self.menu_bar)

        character_box = QtWidgets.QGroupBox("Character")
        character_layout = QtWidgets.QHBoxLayout(character_box)
        character_layout.addWidget(self.character_lb, 1)
        character_layout.addWidget(self.initialize_btn)
        main_layout.addWidget(character_box)

        source_box = QtWidgets.QGroupBox("Source")
        source_layout = QtWidgets.QGridLayout(source_box)
        source_layout.addWidget(self.source_combo, 0, 0, 1, 2)
        source_layout.addWidget(self.bake_btn, 0, 2)
        source_layout.addWidget(self.new_layer_cb, 1, 0)
        source_layout.addWidget(self.layer_le, 1, 1)
        source_layout.addWidget(self.pre_roll_sb, 1, 2)
        source_layout.setColumnStretch(1, 1)
        main_layout.addWidget(source_box)

        tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(tabs, 1)

        mapping_tab = QtWidgets.QWidget()
        mapping_layout = QtWidgets.QVBoxLayout(mapping_tab)
        body_layout = QtWidgets.QVBoxLayout()
        body_layout.setSpacing(2)
        for row in BODY_LAYOUT:
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setSpacing(2)
            for key, _ in row:
                row_layout.addWidget(self.part_buttons[key])
            body_layout.addLayout(row_layout)
        mapping_layout.addLayout(body_layout)
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(self.mirror_cb)
        filter_layout.addWidget(self.filter_le, 1)
        filter_layout.addWidget(self.mapped_only_cb)
        mapping_layout.addLayout(filter_layout)
        mapping_layout.addWidget(self.mapping_table, 1)
        tabs.addTab(mapping_tab, "Mapping")

        batch_tab = QtWidgets.QWidget()
        batch_layout = QtWidgets.QVBoxLayout(batch_tab)
        files_layout = QtWidgets.QHBoxLayout()
        files_layout.addWidget(self.batch_list, 1)
        files_buttons = QtWidgets.QVBoxLayout()
        for button in (
            self.add_files_btn,
            self.remove_files_btn,
            self.load_list_btn,
            self.save_list_btn,
        ):
            files_buttons.addWidget(button)
        files_buttons.addStretch()
        files_layout.addLayout(files_buttons)
        batch_layout.addLayout(files_layout, 1)
        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(self.batch_mode_combo)
        options_layout.addWidget(self.remove_refs_cb)
        options_layout.addStretch()
        options_layout.addWidget(self.batch_bake_btn)
        batch_layout.addLayout(options_layout)
        batch_layout.addWidget(self.report_tree, 1)
        tabs.addTab(batch_tab, "Batch Bake")

    def create_connections(self):
        self.import_action.triggered.connect(self.import_mapping)
        self.export_action.triggered.connect(self.export_mapping)
        self.refresh_action.triggered.connect(self.refresh)
        self.hik_window_action.triggered.connect(self.open_hik_window)
        self.bake_action.triggered.connect(self.bake)
        self.bake_timeline_action.triggered.connect(self.bake_to_timeline)
        self.initialize_btn.clicked.connect(self.initialize)
        self.source_combo.aboutToShow.connect(self.refresh_sources)
        self.source_combo.activated.connect(self.on_source_activated)
        self.bake_btn.clicked.connect(self.bake)
        self.new_layer_cb.toggled.connect(self.layer_le.setEnabled)
        for key, button in self.part_buttons.items():
            button.clicked.connect(partial(self.open_pairing, key))
        self.filter_le.textChanged.connect(self.apply_filter)
        self.mapped_only_cb.toggled.connect(self.apply_filter)
        self.mapping_table.customContextMenuRequested.connect(self.mapping_menu)
        self.mapping_table.itemDoubleClicked.connect(self.select_row_controls)
        self.add_files_btn.clicked.connect(self.add_files)
        self.remove_files_btn.clicked.connect(self.remove_files)
        self.load_list_btn.clicked.connect(self.load_file_list)
        self.save_list_btn.clicked.connect(self.save_file_list)
        self.batch_bake_btn.clicked.connect(self.batch_bake)
        self.layer_le.setEnabled(self.new_layer_cb.isChecked())

    # -----------------------------------------------------------------
    # Refresh
    # -----------------------------------------------------------------
    def _start_callbacks(self):
        cbm = self.callbacks
        cbm.eventCB("undo", self.scene_refresh, "Undo")
        cbm.eventCB("redo", self.scene_refresh, "Redo")
        cbm.sceneMessageCB("afterNew", self.scene_refresh, om2.MSceneMessage.kAfterNew)
        cbm.sceneMessageCB(
            "afterOpen", self.scene_refresh, om2.MSceneMessage.kAfterOpen
        )

    def _scene_changed(self):
        if not self.closed:
            self.refresh()

    def refresh(self):
        """Read the mapping from the scene and update the window."""
        character = core.get_character()
        self.mapping = core.get_mapping(character) if character else {}
        if character:
            self.character_lb.setText(
                "<b>{}</b>  {} bones mapped".format(character, len(self.mapping))
            )
        else:
            self.character_lb.setText("No HumanIK character")
        self.refresh_sources(character)
        self.refresh_part_buttons()
        self.refresh_table()

    def refresh_sources(self, character=None):
        """List the HumanIK characters that can drive the rig.

        Args:
            character (str, optional): The rig's character, when known.
        """
        character = character or core.get_character()
        sources = core.list_sources(character) if character else []
        current = core.get_source(character) if character else None
        with pyqt.block_signals(self.source_combo):
            self.source_combo.clear()
            self.source_combo.addItem(NONE_SOURCE, "")
            for source in sources:
                self.source_combo.addItem(source, source)
            self.source_combo.setCurrentIndex(
                max(self.source_combo.findData(current or ""), 0)
            )
        self.source_combo.setEnabled(bool(character))
        self.bake_btn.setEnabled(bool(current))

    def refresh_part_buttons(self):
        """Color the body part buttons by mapping status."""
        for key, button in self.part_buttons.items():
            bones = constants.BODY_PART_BONES[key]
            status = core.body_part_status(self.mapping, bones)
            if self.part_status.get(key) != status:
                self.part_status[key] = status
                color = STATUS_COLORS.get(status)
                button.setStyleSheet(
                    "QPushButton {{background-color: {};}}".format(color)
                    if color
                    else ""
                )
            lines = [
                "{}{}: {}".format(
                    bone,
                    "*" if constants.is_required(bone) else "",
                    self.mapping.get(bone, {}).get("target", "-"),
                )
                for bone in bones
            ]
            mapped = len([bone for bone in bones if bone in self.mapping])
            button.setToolTip(
                "{} of {} mapped (* required by HumanIK)\n\n{}".format(
                    mapped, len(bones), "\n".join(lines)
                )
            )

    def _add_table_row(self, bone):
        table = self.mapping_table
        row = table.rowCount()
        table.insertRow(row)
        for column in range(3):
            item = QtWidgets.QTableWidgetItem(bone if column == 0 else "")
            item.setData(QtCore.Qt.UserRole, bone)
            table.setItem(row, column, item)
        self.table_rows[bone] = row

    def refresh_table(self):
        """Show the control and Sub IK controls of every bone."""
        for bone in self.mapping:
            if bone not in self.table_rows:
                self._add_table_row(bone)
        table = self.mapping_table
        grey = QtGui.QColor(UNMAPPED_COLOR)
        table.setUpdatesEnabled(False)
        try:
            for bone, row in self.table_rows.items():
                entry = self.mapping.get(bone)
                table.item(row, 1).setText(entry["target"] if entry else "")
                table.item(row, 2).setText(", ".join(entry["sub_ik"]) if entry else "")
                for column in range(3):
                    table.item(row, column).setData(
                        QtCore.Qt.ForegroundRole, None if entry else grey
                    )
        finally:
            table.setUpdatesEnabled(True)
        self.apply_filter()

    def apply_filter(self, *args):
        """Hide the rows that don't match the filter."""
        text = self.filter_le.text().lower()
        mapped_only = self.mapped_only_cb.isChecked()
        table = self.mapping_table
        for row in range(table.rowCount()):
            bone = table.item(row, 0).text()
            control = table.item(row, 1).text()
            visible = not text or text in bone.lower() or text in control.lower()
            if mapped_only and not control:
                visible = False
            table.setRowHidden(row, not visible)

    # -----------------------------------------------------------------
    # Character and mapping
    # -----------------------------------------------------------------
    def initialize(self):
        """Create the character with the selected control as Reference."""
        selection = cmds.ls(selection=True, transforms=True)
        if not selection:
            cmds.warning("Select the rig's reference control to initialize")
            return
        run_core(self, core.initialize_character, selection[-1])
        self.refresh()

    def open_hik_window(self):
        """Open Maya's HumanIK window."""
        cmds.HIKCharacterControlsTool()

    def open_pairing(self, key):
        """Open the pairing dialog of a body part.

        Args:
            key (str): Body part key.
        """
        if not core.get_character():
            cmds.warning("Initialize the HumanIK character first")
            return
        self.close_pairing()
        self.pairing_dialog = PairingDialog(
            PART_LABELS[key],
            constants.BODY_PART_BONES[key],
            self.mirror_cb.isChecked(),
            parent=self,
        )
        self.pairing_dialog.applied.connect(self.refresh)
        # the dialog deletes itself on close
        self.pairing_dialog.destroyed.connect(
            partial(self._pairing_destroyed, self.pairing_dialog)
        )
        self.pairing_dialog.show()

    def _pairing_destroyed(self, dialog, *args):
        # a replaced dialog is deleted after the new one opens
        if self.pairing_dialog is dialog:
            self.pairing_dialog = None

    def close_pairing(self):
        """Close the open pairing dialog, if any."""
        dialog = self.pairing_dialog
        self.pairing_dialog = None
        if dialog is None:
            return
        try:
            dialog.close()
        except RuntimeError:
            # already deleted by Qt
            pass

    def selected_bones(self):
        """Return the bones of the selected table rows.

        Returns:
            list: HumanIK bone names.
        """
        rows = sorted({index.row() for index in self.mapping_table.selectedIndexes()})
        return [self.mapping_table.item(row, 0).text() for row in rows]

    def mapping_menu(self, position):
        """Show the actions of the clicked mapping rows.

        Args:
            position (QtCore.QPoint): Click position.
        """
        item = self.mapping_table.itemAt(position)
        character = core.get_character()
        if item is None or not character:
            return
        bones = self.selected_bones() or [item.data(QtCore.Qt.UserRole)]
        mapped = [bone for bone in bones if bone in self.mapping]
        single = mapped[0] if len(mapped) == 1 and len(bones) == 1 else None

        menu = QtWidgets.QMenu(self)
        select_action = menu.addAction("Select Controls")
        select_action.setEnabled(bool(mapped))
        map_action = None
        if len(bones) == 1:
            map_action = menu.addAction("Map Selected Control")
        unmap_action = menu.addAction("Unmap")
        unmap_action.setEnabled(bool(mapped))
        menu.addSeparator()
        sub_ik_action = menu.addAction("Set Selection as Sub IK")
        sub_ik_action.setEnabled(bool(single))
        clear_action = menu.addAction("Clear Sub IK")
        clear_action.setEnabled(any(self.mapping[bone]["sub_ik"] for bone in mapped))
        chosen = menu.exec_(self.mapping_table.viewport().mapToGlobal(position))
        if chosen is None:
            return
        if chosen is select_action:
            cmds.select([self.mapping[bone]["target"] for bone in mapped])
        elif chosen is map_action:
            self.map_selected_control(character, bones[0])
        elif chosen is unmap_action:
            core.unmap_bones(character, mapped)
        elif chosen is sub_ik_action:
            self.set_sub_ik(self.mapping[single]["target"])
        elif chosen is clear_action:
            for bone in mapped:
                core.clear_sub_ik(self.mapping[bone]["target"])
        self.refresh()

    def map_selected_control(self, character, bone):
        """Map the selected control to a bone.

        Args:
            character (str): HumanIK character.
            bone (str): HumanIK bone.
        """
        selection = cmds.ls(selection=True, transforms=True)
        if len(selection) != 1:
            cmds.warning("Select one control to map to {}".format(bone))
            return
        run_core(self, core.map_bones, character, [(bone, selection[0])])

    def set_sub_ik(self, target):
        """Link the selected controls as Sub IK of a mapped control.

        Args:
            target (str): Mapped control.
        """
        selection = [
            node for node in cmds.ls(selection=True, transforms=True) if node != target
        ]
        if not selection:
            cmds.warning("Select the Sub IK controls")
            return
        ok, missing = run_core(
            self, core.set_sub_ik, target, selection, mirror=self.mirror_cb.isChecked()
        )
        if ok and missing:
            cmds.warning("No opposite control for: {}".format(", ".join(missing)))

    def select_row_controls(self, item):
        """Select the controls of a double-clicked row.

        Args:
            item (QtWidgets.QTableWidgetItem): Clicked item.
        """
        entry = self.mapping.get(item.data(QtCore.Qt.UserRole))
        if entry:
            cmds.select([entry["target"]] + list(entry["sub_ik"]))

    # -----------------------------------------------------------------
    # Mapping files
    # -----------------------------------------------------------------
    def export_mapping(self):
        """Export the mapping to a ``.hikm`` file."""
        character = core.get_character()
        if not character:
            cmds.warning("No HumanIK character to export")
            return
        paths = _file_dialog("Export Mapping", constants.MAPPING_FILTER, 0)
        if paths:
            core.export_mapping(paths[0], character)

    def import_mapping(self):
        """Import a ``.hikm`` file in the namespace of the selection.

        Without selection, controls are found in any namespace when their
        name is unique.
        """
        paths = _file_dialog("Import Mapping", constants.MAPPING_FILTER, 1)
        if not paths:
            return
        selection = cmds.ls(selection=True)
        namespace = node_remap.common_namespace(selection)[0] if selection else None
        try:
            file_mapping = core.load_mapping_file(paths[0])
        except (IOError, ValueError) as error:
            cmds.warning("Can't read {}: {}".format(paths[0], error))
            return
        mapping, report = core.resolve_mapping(file_mapping, namespace)
        core.warn_report(report)
        if mapping:
            run_core(self, core.apply_mapping, mapping)
            self.refresh()

    # -----------------------------------------------------------------
    # Source and bake
    # -----------------------------------------------------------------
    def on_source_activated(self, index):
        """Drive the character with the chosen source.

        Args:
            index (int): Combo index.
        """
        character = core.get_character()
        if not character:
            return
        source = self.source_combo.itemData(index) or None
        core.set_source(character, source, mapping=self.mapping)
        self.refresh_sources(character)

    def _baked_source(self):
        character = core.get_character()
        source = core.get_source(character) if character else None
        if not source:
            cmds.warning("Choose a source to bake")
        return character, source

    def bake(self):
        """Bake the source over the playback range."""
        character, source = self._baked_source()
        if not source:
            return
        layer = None
        if self.new_layer_cb.isChecked():
            layer = batch.clean_name(
                node_remap.short_name(self.layer_le.text().strip() or source)
            )
        run_core(
            self,
            core.bake,
            character,
            layer=layer,
            pre_roll=self.pre_roll_sb.value(),
            mapping=self.mapping,
        )
        self.refresh_sources(character)

    def bake_to_timeline(self):
        """Bake the source and move the keys into a Time Editor clip."""
        character, source = self._baked_source()
        if not source:
            return
        run_core(
            self,
            batch.bake_to_clip,
            character,
            batch.clean_name(node_remap.short_name(source)),
            pre_roll=self.pre_roll_sb.value(),
            mapping=self.mapping,
        )
        self.refresh_sources(character)

    # -----------------------------------------------------------------
    # Batch bake
    # -----------------------------------------------------------------
    def batch_files(self):
        """Return the files of the batch list.

        Returns:
            list: File paths.
        """
        return [self.batch_list.item(i).text() for i in range(self.batch_list.count())]

    def add_files(self):
        """Add animation files to the batch list."""
        paths = _file_dialog("Add Animation Files", constants.SOURCE_FILTER, 4)
        existing = self.batch_files()
        self.batch_list.addItems([path for path in paths if path not in existing])

    def remove_files(self):
        """Remove the selected files from the batch list."""
        for item in self.batch_list.selectedItems():
            self.batch_list.takeItem(self.batch_list.row(item))

    def load_file_list(self):
        """Replace the batch list with a ``.bkcn`` file."""
        paths = _file_dialog("Load Batch List", constants.BATCH_FILTER, 1)
        if not paths:
            return
        try:
            files = batch.read_file_list(paths[0])
        except (IOError, ValueError) as error:
            cmds.warning("Can't read {}: {}".format(paths[0], error))
            return
        self.batch_list.clear()
        self.batch_list.addItems(files)

    def save_file_list(self):
        """Save the batch list to a ``.bkcn`` file."""
        paths = _file_dialog("Save Batch List", constants.BATCH_FILTER, 0)
        if paths:
            batch.write_file_list(paths[0], self.batch_files())

    def batch_bake(self):
        """Bake every file of the batch list and show the report."""
        files = self.batch_files()
        if not files:
            cmds.warning("Add animation files to bake")
            return
        missing = [path for path in files if not os.path.exists(path)]
        if missing:
            cmds.warning("Missing files: {}".format(", ".join(missing)))
            return
        ok, reports = run_core(
            self,
            batch.batch_bake,
            files,
            mode=self.batch_mode_combo.currentData(),
            remove_references=self.remove_refs_cb.isChecked(),
            pre_roll=self.pre_roll_sb.value(),
        )
        if ok:
            self.show_report(reports)
        self.refresh()

    def show_report(self, reports):
        """List the batch bake result of each file.

        Args:
            reports (list): Reports from :func:`batch.batch_bake`.
        """
        self.report_tree.clear()
        warning = QtGui.QColor(STATUS_COLORS[constants.STATUS_PARTIAL])
        for report in reports:
            detail = report.get("message") or ""
            if report.get("range"):
                detail = "{:g} - {:g}".format(*report["range"])
            item = QtWidgets.QTreeWidgetItem(
                [os.path.basename(report["file"]), report["status"], detail]
            )
            item.setToolTip(0, report["file"])
            if report["status"] != batch.STATUS_BAKED:
                item.setForeground(1, warning)
            self.report_tree.addTopLevelItem(item)
        self.report_tree.resizeColumnToContents(0)

    # -----------------------------------------------------------------
    # Window lifecycle
    # -----------------------------------------------------------------
    def shutdown(self):
        """Remove the callbacks and save the settings (once)."""
        if self.closed:
            return
        self.closed = True
        self.callbacks.removeAllManagedCB()
        self.close_pairing()
        self.save_settings()

    def closeEvent(self, event):
        self.shutdown()
        super(HumanIKMapperUI, self).closeEvent(event)

    def dockCloseEventTriggered(self):
        self.shutdown()


class PairingDialog(QtWidgets.QDialog):
    """Preview the bone and control pairs of a body part, then map them.

    The pairs follow the Maya selection: select the controls in the order
    of the bones.
    """

    applied = QtCore.Signal()

    def __init__(self, label, bones, mirror=False, parent=None):
        """Initialize the dialog.

        Args:
            label (str): Body part label.
            bones (tuple): The body part's HumanIK bones.
            mirror (bool, optional): Initial mirror state.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(PairingDialog, self).__init__(parent)
        self.bones = list(bones)
        self.pairs = []
        self.callbacks = callbackManager.CallbackManager()
        self.selection_update = pyqt.CoalescedCall(self.update_pairs)

        self.setWindowTitle("Map {}".format(label))
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.resize(pyqt.dpi_scale(380), pyqt.dpi_scale(420))

        self.info_lb = QtWidgets.QLabel(
            "Select the controls in the order of the bones. Select fewer "
            "controls to skip the last bones: only the bones in bold are "
            "required by HumanIK."
        )
        self.info_lb.setWordWrap(True)
        self.mirror_cb = QtWidgets.QCheckBox("Mirror")
        self.mirror_cb.setChecked(mirror)
        self.mirror_cb.setEnabled(any(constants.mirror_bone(b) for b in bones))
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Bone", "Control"])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.warning_lb = QtWidgets.QLabel()
        self.warning_lb.setWordWrap(True)
        self.warning_lb.setStyleSheet(
            "color: {};".format(STATUS_COLORS[constants.STATUS_PARTIAL])
        )
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.setDefault(True)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.info_lb)
        layout.addWidget(self.mirror_cb)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.warning_lb)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.apply_btn)
        layout.addLayout(buttons)

        self.mirror_cb.toggled.connect(self.update_pairs)
        self.apply_btn.clicked.connect(self.apply)
        self.cancel_btn.clicked.connect(self.close)
        self.callbacks.selectionChangedCB("hikPairing", self.selection_update)
        self.update_pairs()

    def update_pairs(self, *args):
        """Pair the bones with the selected controls."""
        controls = cmds.ls(selection=True, transforms=True)
        self.pairs, report = core.pair_selection(
            self.bones, controls, self.mirror_cb.isChecked()
        )
        paired = dict(self.pairs)
        bones = list(self.bones) + [
            bone for bone, _ in self.pairs if bone not in self.bones
        ]
        self.table.setRowCount(len(bones))
        grey = QtGui.QColor(UNMAPPED_COLOR)
        for row, bone in enumerate(bones):
            bone_item = QtWidgets.QTableWidgetItem(bone)
            control_item = QtWidgets.QTableWidgetItem(paired.get(bone, ""))
            font = bone_item.font()
            font.setBold(constants.is_required(bone))
            # mirrored pairs
            font.setItalic(bone not in self.bones)
            bone_item.setFont(font)
            control_item.setFont(font)
            if bone not in paired:
                bone_item.setForeground(grey)
            self.table.setItem(row, 0, bone_item)
            self.table.setItem(row, 1, control_item)
        warnings = []
        if report["unused_controls"]:
            warnings.append(
                "More controls than bones, not used: {}".format(
                    ", ".join(report["unused_controls"])
                )
            )
        if report["missing_mirror"]:
            warnings.append(
                "No opposite control for: {}".format(
                    ", ".join(report["missing_mirror"])
                )
            )
        required = [b for b in report["unpaired_bones"] if constants.is_required(b)]
        if self.pairs and required:
            warnings.append("Required bones not paired: {}".format(", ".join(required)))
        self.warning_lb.setText("\n".join(warnings))
        self.apply_btn.setEnabled(bool(self.pairs))

    def apply(self):
        """Map the pairs and close."""
        character = core.get_character()
        if not character:
            cmds.warning("Initialize the HumanIK character first")
            return
        ok, _ = run_core(self, core.map_bones, character, self.pairs)
        if ok:
            self.applied.emit()
            self.close()

    def closeEvent(self, event):
        self.callbacks.removeAllManagedCB()
        super(PairingDialog, self).closeEvent(event)


class LockedCtrlsDialog(QtWidgets.QDialog):
    """Ask to unlock the locked transform channels of controls."""

    def __init__(self, controls, parent=None):
        """Initialize the dialog.

        Args:
            controls (list): Controls with locked channels.
            parent (QtWidgets.QWidget, optional): Parent widget. Default:
                Maya's main window.
        """
        super(LockedCtrlsDialog, self).__init__(parent or pyqt.maya_main_window())
        self.setWindowTitle("Locked channels")
        self.setMinimumSize(QtCore.QSize(320, 240))

        label = QtWidgets.QLabel(
            "These controls have locked or connected transform channels.\n"
            "HumanIK needs to drive them. Unlock them?"
        )
        label.setWordWrap(True)
        controls_list = QtWidgets.QListWidget()
        controls_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        controls_list.addItems(controls)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Unlock")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(controls_list)
        layout.addWidget(buttons)


def show(*args):
    """Show the dockable HumanIK Mapper, replacing an open one.

    Returns:
        HumanIKMapperUI: The window instance.
    """
    core.ensure_hik()
    return pyqt.showDialog(HumanIKMapperUI, dockable=True)
