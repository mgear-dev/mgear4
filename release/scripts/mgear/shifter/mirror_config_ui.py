"""Mirror Config - Set up the mirror pose flags of the controls of a rig.

Dockable window over :mod:`mgear.core.mirror_config`: analyze the controls,
review and edit the proposed invTx ... invRz flags, apply them, create the
missing inv attributes, verify the mirror and import or export ``.smc``
files.
"""

from functools import partial

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from mgear.core import mirror_config
from mgear.core import pyqt
from mgear.core import utils

from maya import cmds
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

STATUS_MANUAL = "manual"
ALL_STATUSES = mirror_config.STATUSES + (STATUS_MANUAL,)

STATUS_LABELS = {
    mirror_config.STATUS_OK: "OK",
    mirror_config.STATUS_CHANGED: "Changed",
    mirror_config.STATUS_MISSING: "Missing attrs",
    mirror_config.STATUS_NOT_MIRRORABLE: "Not mirrorable",
    mirror_config.STATUS_NO_PAIR: "No pair",
    STATUS_MANUAL: "Manual",
}

STATUS_COLORS = {
    mirror_config.STATUS_OK: "#7cb5a0",
    mirror_config.STATUS_CHANGED: "#e0b050",
    mirror_config.STATUS_MISSING: "#e0b050",
    mirror_config.STATUS_NOT_MIRRORABLE: "#d9655b",
    mirror_config.STATUS_NO_PAIR: "#d9655b",
    STATUS_MANUAL: "#6fa8dc",
}

# filter label, statuses shown (None: all)
FILTERS = (
    ("All", None),
    (
        "Needs attention",
        (
            mirror_config.STATUS_CHANGED,
            mirror_config.STATUS_MISSING,
            mirror_config.STATUS_NOT_MIRRORABLE,
            mirror_config.STATUS_NO_PAIR,
        ),
    ),
) + tuple((STATUS_LABELS[s], (s,)) for s in ALL_STATUSES)

FLAG_LABELS = tuple(a[3:] for a in mirror_config.INV_ATTRS)
COL_NAME = 0
COL_STATUS = 1
COL_ERROR = 2
COL_VERIFY = 3
COL_FLAGS = 4
HEADERS = ("Control", "Status", "Error", "Verify") + FLAG_LABELS

NODE_ROLE = QtCore.Qt.UserRole
CHANGED_BRUSH = QtGui.QBrush(QtGui.QColor(224, 176, 80, 90))


def row_flags(record):
    """Get the flags a table row starts with.

    Args:
        record (dict): Control record of mirror_config.analyze.

    Returns:
        dict: inv attribute name to bool. The proposed flags, or the
            current ones (missing attributes off) without proposal.
    """
    if record["proposed"] is not None:
        return dict(record["proposed"])
    return {a: bool(v) for a, v in record["current"].items()}


def row_status(record):
    """Get the status of a table row.

    Args:
        record (dict): Control record of mirror_config.analyze, with the
            ``flags`` of the row.

    Returns:
        str: STATUS_MANUAL when the row flags differ from the proposal (or
            from the scene, without proposal), else the analysis status
            for the current scene flags.
    """
    proposed = record["proposed"]
    if proposed is None:
        if record["flags"] != row_flags(record):
            return STATUS_MANUAL
        return record["status"]
    if record["flags"] != proposed:
        return STATUS_MANUAL
    return mirror_config.flag_status(proposed, record["current"])


def format_verify(result):
    """Get the text of a verify result.

    Args:
        result (dict): Result of mirror_config.verify for one control.

    Returns:
        str: Rotation and translation errors, i.e. "0.00° / 0.000".
    """
    return "{:.2f}° / {:.3f}".format(
        result["rotation_error"], result["translation_error"]
    )


def is_verify_error(result, tolerance):
    """Tell if a verify result is above the tolerances.

    Args:
        result (dict): Result of mirror_config.verify for one control.
        tolerance (float): Largest rotation error, in degrees.

    Returns:
        bool: True if the control doesn't mirror correctly.
    """
    return (
        result["rotation_error"] > tolerance
        or result["translation_error"] > mirror_config.TRANSLATION_TOLERANCE
    )


class MirrorConfigUI(MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin):
    """Dockable window to set up the mirror pose flags of controls."""

    toolName = "MirrorConfig"

    def __init__(self, parent=None):
        """Initialize the window.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(MirrorConfigUI, self).__init__(parent)
        pyqt.SettingsMixin.__init__(self)

        # control full path to its analysis record, with the row "flags"
        self.records = {}

        self.setObjectName(self.toolName)
        self.setWindowTitle("Mirror Config")
        self.setWindowIcon(QtGui.QIcon(pyqt.get_icon("mgear_mirror_config")))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setMinimumWidth(420)

        if cmds.about(ntOS=True):
            flags = self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
            self.setWindowFlags(flags)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.setup_ui()

        self.user_settings = {
            "mirror_config_mode": (self.mode_combo, 0),
            "mirror_config_tolerance": (
                self.tolerance_spin,
                mirror_config.DEFAULT_TOLERANCE,
            ),
            "mirror_config_filter": (self.filter_combo, 0),
        }
        self.load_settings()
        self.resize(720, 620)

    # =========================================================
    # UI SETUP
    # =========================================================

    def setup_ui(self):
        """Build the window."""
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        """Create the widgets."""
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Rig of selection", "rig")
        self.mode_combo.addItem("Selected controls", "selection")
        self.mode_combo.setToolTip(
            "Rig of selection: every control of the rigs of the selected "
            "nodes.\nSelected controls: only the selected controls."
        )
        self.tolerance_spin = QtWidgets.QDoubleSpinBox()
        self.tolerance_spin.setRange(0.01, 45.0)
        self.tolerance_spin.setDecimals(2)
        self.tolerance_spin.setSuffix("°")
        self.tolerance_spin.setToolTip(
            "Largest error of a control that can be mirrored with channel "
            "flips.\nAbove it the control is Not mirrorable."
        )
        self.analyze_btn = QtWidgets.QPushButton("Analyze")
        self.analyze_btn.setToolTip(
            "Propose the translate and rotate inv flags from the rest "
            "frames of the controls"
        )

        self.filter_combo = QtWidgets.QComboBox()
        for label, _ in FILTERS:
            self.filter_combo.addItem(label)

        self.table = QtWidgets.QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NAME, QtWidgets.QHeaderView.Stretch
        )

        self.apply_all_btn = QtWidgets.QPushButton("Apply All")
        self.apply_sel_btn = QtWidgets.QPushButton("Apply Selected")
        self.create_missing_btn = QtWidgets.QPushButton("Create Missing")
        self.create_missing_btn.setToolTip(
            "Add the inv attributes to the controllers set members that "
            "don't have them"
        )
        self.verify_btn = QtWidgets.QPushButton("Verify")
        self.verify_btn.setToolTip(
            "Mirror a test pose with the current scene flags and measure " "the error"
        )
        self.import_btn = QtWidgets.QPushButton("Import...")
        self.import_btn.setToolTip("Apply a .smc file to the rig of the selection")
        self.export_btn = QtWidgets.QPushButton("Export...")
        self.export_btn.setToolTip("Export the flags of the table to a .smc file")

        self.summary_label = QtWidgets.QLabel("Select a rig and click Analyze")

    def create_layout(self):
        """Arrange the widgets."""
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self.mode_combo, 1)
        top_layout.addWidget(QtWidgets.QLabel("Tolerance"))
        top_layout.addWidget(self.tolerance_spin)
        top_layout.addWidget(self.analyze_btn)

        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Show"))
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        filter_layout.addWidget(self.summary_label)

        apply_layout = QtWidgets.QHBoxLayout()
        apply_layout.addWidget(self.apply_all_btn)
        apply_layout.addWidget(self.apply_sel_btn)
        apply_layout.addWidget(self.create_missing_btn)
        apply_layout.addWidget(self.verify_btn)

        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addStretch()
        file_layout.addWidget(self.import_btn)
        file_layout.addWidget(self.export_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.table)
        main_layout.addLayout(apply_layout)
        main_layout.addLayout(file_layout)

    def create_connections(self):
        """Connect the signals."""
        self.analyze_btn.clicked.connect(self.analyze)
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        self.table.itemChanged.connect(self._item_changed)
        self.table.itemSelectionChanged.connect(self.select_controls)
        self.apply_all_btn.clicked.connect(partial(self.apply, False))
        self.apply_sel_btn.clicked.connect(partial(self.apply, True))
        self.create_missing_btn.clicked.connect(self.create_missing)
        self.verify_btn.clicked.connect(self.verify)
        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)

    # =========================================================
    # TABLE
    # =========================================================

    def _scene_nodes(self):
        """Get the nodes to work on: the selection, or the analyzed rig."""
        nodes = cmds.ls(selection=True, long=True) or list(self.records)
        if not nodes:
            self.summary_label.setText("Select a rig control first")
        return nodes

    def _row_node(self, row):
        """Get the control full path of a row."""
        return self.table.item(row, COL_NAME).data(NODE_ROLE)

    def analyze(self):
        """Analyze the controls and fill the table."""
        nodes = self._scene_nodes()
        if nodes:
            self.analyze_nodes(nodes, self.mode_combo.currentData())

    def analyze_nodes(self, nodes, mode):
        """Analyze controls and fill the table.

        Args:
            nodes (list): Nodes, see mirror_config.get_controls.
            mode (str): "rig" or "selection".
        """
        analysis = mirror_config.analyze(
            nodes, mode=mode, tolerance=self.tolerance_spin.value()
        )
        self.records = {}
        for record in analysis["controls"]:
            record["flags"] = row_flags(record)
            self.records[record["node"]] = record
        self.populate()

    def populate(self):
        """Fill the table with the records."""
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records.values()):
            name_item = QtWidgets.QTableWidgetItem(record["name"])
            name_item.setData(NODE_ROLE, record["node"])
            target = record["target"]
            name_item.setToolTip(
                "Mirror: {}".format(mirror_config.short_name(target))
                if target
                else "No mirror control"
            )
            self.table.setItem(row, COL_NAME, name_item)
            error = record["error"]
            error_item = QtWidgets.QTableWidgetItem(
                "" if error is None else "{:.2f}°".format(error)
            )
            error_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, COL_ERROR, error_item)
            self.table.setItem(row, COL_VERIFY, QtWidgets.QTableWidgetItem(""))
            self.table.setItem(row, COL_STATUS, QtWidgets.QTableWidgetItem(""))
            for col, attr in enumerate(mirror_config.INV_ATTRS, COL_FLAGS):
                item = QtWidgets.QTableWidgetItem()
                item_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                if attr not in mirror_config.SCALE_ATTRS:
                    item_flags |= QtCore.Qt.ItemIsUserCheckable
                item.setFlags(item_flags)
                self.table.setItem(row, col, item)
            self._update_row(row)
        self.table.resizeColumnsToContents()
        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)
        self.apply_filter()

    def _update_row(self, row):
        """Show the status and flags of a row. Call with signals blocked."""
        record = self.records[self._row_node(row)]
        status = row_status(record)
        status_item = self.table.item(row, COL_STATUS)
        status_item.setText(STATUS_LABELS[status])
        status_item.setForeground(QtGui.QBrush(QtGui.QColor(STATUS_COLORS[status])))
        for col, attr in enumerate(mirror_config.INV_ATTRS, COL_FLAGS):
            item = self.table.item(row, col)
            checked = record["flags"][attr]
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            current = record["current"][attr]
            differs = current is None or current != checked
            item.setBackground(CHANGED_BRUSH if differs else QtGui.QBrush())
            item.setToolTip(
                "{}: current {}".format(
                    attr, "missing" if current is None else ("on" if current else "off")
                )
            )

    def _refresh_rows(self):
        """Read the scene flags of the rows again and update them."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            record = self.records[self._row_node(row)]
            if cmds.objExists(record["node"]):
                record["current"] = mirror_config.current_flags(record["node"])
            self._update_row(row)
        self.table.blockSignals(False)
        self.apply_filter()

    def _item_changed(self, item):
        """Store a flag edited in the table."""
        if item.column() < COL_FLAGS:
            return
        record = self.records[self._row_node(item.row())]
        attr = mirror_config.INV_ATTRS[item.column() - COL_FLAGS]
        record["flags"][attr] = item.checkState() == QtCore.Qt.Checked
        self.table.blockSignals(True)
        self._update_row(item.row())
        self.table.blockSignals(False)
        self.apply_filter()

    def apply_filter(self):
        """Show only the rows of the statuses of the filter."""
        statuses = FILTERS[self.filter_combo.currentIndex()][1]
        counts = {}
        for row in range(self.table.rowCount()):
            status = row_status(self.records[self._row_node(row)])
            counts[status] = counts.get(status, 0) + 1
            self.table.setRowHidden(
                row, statuses is not None and status not in statuses
            )
        self.summary_label.setText(
            ", ".join(
                "{} {}".format(counts[s], STATUS_LABELS[s].lower())
                for s in ALL_STATUSES
                if counts.get(s)
            )
            or "No controls"
        )

    def selected_nodes(self):
        """Get the controls of the selected rows.

        Returns:
            list: Control full paths.
        """
        rows = sorted({i.row() for i in self.table.selectedItems()})
        return [self._row_node(r) for r in rows]

    def select_controls(self):
        """Select in Maya the controls of the selected rows."""
        nodes = [n for n in self.selected_nodes() if cmds.objExists(n)]
        if nodes:
            cmds.select(nodes, replace=True)

    # =========================================================
    # ACTIONS
    # =========================================================

    def apply(self, selected_only=False):
        """Apply the flags of the table to the scene.

        Args:
            selected_only (bool, optional): Only the selected rows.
        """
        nodes = self.selected_nodes() if selected_only else list(self.records)
        nodes = [n for n in nodes if cmds.objExists(n)]
        if not nodes:
            return
        result = mirror_config.apply_flags({n: self.records[n]["flags"] for n in nodes})
        self._refresh_rows()
        self.summary_label.setText(
            "Apply: {}".format(mirror_config.format_apply_result(result))
        )

    def create_missing(self):
        """Add the missing inv attributes to the controllers set members."""
        nodes = self._scene_nodes()
        if not nodes:
            return
        missing = mirror_config.find_missing(nodes)
        missing += [
            n
            for n, r in self.records.items()
            if None in r["current"].values() and n not in missing
        ]
        created = mirror_config.create_missing(missing)
        self._refresh_rows()
        self.summary_label.setText(
            "Created inv attributes on {} controls".format(len(created))
        )

    def verify(self):
        """Verify the current scene flags and show the errors."""
        if self.records:
            results = mirror_config.verify(list(self.records), mode="selection")
        else:
            nodes = self._scene_nodes()
            if not nodes:
                return
            results = mirror_config.verify(nodes, mode=self.mode_combo.currentData())
        by_node = dict(results)
        for result in results.values():
            by_node.setdefault(result["target"], result)
        tolerance = self.tolerance_spin.value()
        bad_brush = QtGui.QBrush(
            QtGui.QColor(STATUS_COLORS[mirror_config.STATUS_NOT_MIRRORABLE])
        )
        for row in range(self.table.rowCount()):
            result = by_node.get(self._row_node(row))
            item = QtWidgets.QTableWidgetItem(format_verify(result) if result else "")
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            if result and is_verify_error(result, tolerance):
                item.setForeground(bad_brush)
            self.table.setItem(row, COL_VERIFY, item)
        bad = sum(1 for r in results.values() if is_verify_error(r, tolerance))
        self.summary_label.setText(
            "Verified {} controls, {} with errors".format(len(results), bad)
        )

    def import_config(self):
        """Apply a .smc file to the rig of the selection."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Mirror Config", self._start_dir(), mirror_config.FILE_FILTER
        )
        if not path:
            return
        nodes = self._scene_nodes()
        if not nodes:
            return
        try:
            result = mirror_config.import_config(path, nodes=nodes)
        except ValueError as err:
            self.summary_label.setText(str(err))
            return
        # show the imported flags in the table
        for node in result["applied"] + result["skipped"]:
            record = self.records.get(node)
            if record:
                record["current"] = mirror_config.current_flags(node)
                record["flags"] = {a: bool(v) for a, v in record["current"].items()}
        self._refresh_rows()
        self.summary_label.setText(
            "Import: {}".format(mirror_config.format_apply_result(result))
        )

    def export_config(self):
        """Export the flags of the table to a .smc file."""
        if not self.records:
            self.summary_label.setText("Nothing to export, Analyze first")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Mirror Config", self._start_dir(), mirror_config.FILE_FILTER
        )
        if not path:
            return
        config = mirror_config.build_config(
            {n: r["flags"] for n, r in self.records.items()}
        )
        path = mirror_config.export_config(path, config)
        self.summary_label.setText("Exported {}".format(path))

    def _start_dir(self):
        """Get the starting folder of the file dialogs."""
        return utils.get_workspace_folder("scenes")

    # =========================================================
    # MAYA INTEGRATION
    # =========================================================

    def closeEvent(self, event):
        """Save the settings when closing.

        Args:
            event (QtGui.QCloseEvent): Close event.
        """
        self.save_settings()
        super(MirrorConfigUI, self).closeEvent(event)

    def dockCloseEventTriggered(self):
        """Save the settings when the docked window is closed."""
        self.save_settings()


def show(*args):
    """Show the Mirror Config window.

    Returns:
        MirrorConfigUI: The window.
    """
    return pyqt.showDialog(MirrorConfigUI, dockable=True)
