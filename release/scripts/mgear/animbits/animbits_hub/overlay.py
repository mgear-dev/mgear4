"""Overlay window of the Animbits Hub.

A frameless, translucent window over Maya that never takes keyboard
focus. Each time it shows, it rebuilds its rows from the registered
tools.
"""

import maya.api.OpenMaya as om2

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from mgear.core import callbackManager
from mgear.core import node_remap
from mgear.core import pyqt
from mgear.utilbits.bookmarks import core as bm_core

from . import geometry
from . import modes
from . import registry
from . import settings as hub_settings
from . import tools  # noqa: F401 (registers the built-in tools)
from .widgets import GripHandle
from .widgets import ModeBar
from .widgets import NamespaceLabel
from .widgets import ScaleMenuRow

BASE_UNIT = 10.0

_hub = None


def _rect_tuple(rect):
    return (rect.x(), rect.y(), rect.width(), rect.height())


def _size_tuple(size):
    return (size.width(), size.height())


class HubOverlay(QtWidgets.QWidget):
    """The Animbits Hub window.

    Args:
        parent (QWidget, optional): Parent widget. Defaults to the Maya
            main window.
    """

    def __init__(self, parent=None):
        super(HubOverlay, self).__init__(parent or pyqt.maya_main_window())
        self.setObjectName("animbits_hub")
        self.setWindowFlags(
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.NoDropShadowWindowHint
            | QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self.settings = hub_settings.HubSettings()
        self.namespace = None
        self.namespace_valid = False
        self.rows = []
        self.tool_rows = []
        self._callbacks = callbackManager.CallbackManager()
        self._refresh_later = pyqt.CoalescedCall(self._on_scene_changed)
        self._pos_before_drag = None

        self.grip = GripHandle()
        self.namespace_label = NamespaceLabel()
        self.namespace_label.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed
        )

        self.top_bar = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.grip)
        top_layout.addWidget(self.namespace_label)
        top_layout.addStretch()

        # rows of button tools, e.g. the key tools
        self.tool_area = QtWidgets.QWidget()
        self.tool_layout = QtWidgets.QVBoxLayout(self.tool_area)
        self.tool_layout.setContentsMargins(0, 0, 0, 0)

        self.mode_bar = ModeBar(modes.MODES)

        self.rows_layout = QtWidgets.QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addWidget(self.tool_area)
        self.main_layout.addWidget(self.mode_bar)
        self.main_layout.addLayout(self.rows_layout)

        self.grip.moved.connect(self._on_grip_moved)
        self.namespace_label.clicked.connect(self._show_namespace_menu)
        self.mode_bar.mode_changed.connect(self.set_slider_mode)

    # show / hide ------------------------------------------------------

    def unit(self):
        """Return the size unit: base size x hub scale x Maya DPI scale.

        Returns:
            float: Size unit in pixels.
        """
        return pyqt.dpi_scale(BASE_UNIT) * self.settings.scale

    def show_hub(self):
        """Rebuild the rows, place the hub and show it."""
        self.update_namespace()
        self.refresh()
        self.place()
        self.show()
        self.raise_()
        self._start_callbacks()

    def hide_hub(self):
        """Hide the hub and stop its callbacks."""
        self._callbacks.removeAllManagedCB()
        self.hide()

    def refresh(self):
        """Rebuild the rows and tool widgets from the registered tools."""
        for row in self.rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows = []
        while self.tool_layout.count():
            self.tool_layout.takeAt(0).widget().deleteLater()
        self.tool_rows = []
        context = registry.HubContext(
            self.settings, self.namespace, self.namespace_valid
        )
        for _tool_id, factory in registry.registered_tools(registry.AREA_TOOLS):
            for row in factory(context):
                row.set_namespace(self.namespace, self.namespace_valid)
                self.tool_layout.addWidget(row, 0, QtCore.Qt.AlignLeft)
                self.tool_rows.append(row)
        for _tool_id, factory in registry.registered_tools(registry.AREA_ROWS):
            for row in factory(context):
                row.drag_started.connect(self._on_drag_started)
                row.drag_finished.connect(self._on_drag_finished)
                row.set_namespace(self.namespace, self.namespace_valid)
                self.rows_layout.addWidget(row, 0, QtCore.Qt.AlignLeft)
                self.rows.append(row)
        self._apply_settings()

    def _apply_settings(self):
        """Apply the scale and name display to the hub and its rows."""
        unit = self.unit()
        spacing = int(round(unit * 0.4))
        self.main_layout.setContentsMargins(spacing, spacing, spacing, spacing)
        self.main_layout.setSpacing(spacing)
        self.rows_layout.setSpacing(spacing)
        self.grip.set_unit(unit)
        self.namespace_label.set_unit(unit)
        self.mode_bar.set_unit(unit)
        show_names = self.settings.show_names
        show_tooltips = self.settings.show_tooltips
        mode = modes.get_mode(self.settings.slider_mode)
        self.mode_bar.set_mode(mode.mode_id)
        self.mode_bar.set_show_tooltips(show_tooltips)
        for row in self._all_rows():
            row.set_unit(unit)
            row.set_show_names(show_names)
            row.set_show_tooltips(show_tooltips)
            row.set_mode(mode)
        self.tool_layout.setSpacing(spacing)
        self._update_top_bar()
        self._align_column()

    def _activate_layouts(self):
        """Polish and lay out every widget of the hub, top-down.

        Child layouts are not active until the hub is shown, so positions
        inside rows (e.g. after the buffer gutter) are only right after
        this.
        """
        self.ensurePolished()
        self.main_layout.activate()
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.ensurePolished()
            layout = widget.layout()
            if layout:
                layout.activate()
        self.main_layout.activate()

    def _align_column(self):
        """Start the tool rows and the mode bar at the sliders' 0% square.

        The buffer circles of the slider rows stay in the gutter on the
        left of that edge.
        """
        # the slider rows are not indented, so one pass measures them
        self._activate_layouts()
        indent = self.rows[0].content_left() if self.rows else 0
        for row in self.tool_rows:
            row.set_indent(indent)
        self.mode_bar.set_indent(indent)
        self.main_layout.activate()

    def _all_rows(self):
        """Return the slider rows and the tool rows.

        Returns:
            list: HubRow widgets.
        """
        return self.rows + self.tool_rows

    def _update_top_bar(self):
        fixed = self.settings.placement == hub_settings.PLACEMENT_FIXED
        needs_namespace = any(row.uses_namespace for row in self._all_rows())
        self.grip.setVisible(fixed)
        self.namespace_label.setVisible(needs_namespace)
        self.top_bar.setVisible(fixed or needs_namespace)
        self.tool_area.setVisible(bool(self.tool_rows))
        self.mode_bar.show()

    # placement --------------------------------------------------------

    def place(self):
        """Move the hub to the fixed position, or under the cursor."""
        self._activate_layouts()
        size = _size_tuple(self.size())
        fixed_pos = self.settings.fixed_pos
        if self.settings.placement == hub_settings.PLACEMENT_FIXED and fixed_pos:
            screens = [
                _rect_tuple(screen.availableGeometry())
                for screen in QtWidgets.QApplication.screens()
            ]
            pos = geometry.place_fixed(fixed_pos, size, screens)
        else:
            cursor = QtGui.QCursor.pos()
            screen = QtWidgets.QApplication.screenAt(cursor)
            screen = screen or QtWidgets.QApplication.primaryScreen()
            if self.rows:
                anchor = self.rows[0].mapTo(self, self.rows[0].anchor())
            else:
                anchor = self.rect().center()
            pos = geometry.place_at_cursor(
                (cursor.x(), cursor.y()),
                (anchor.x(), anchor.y()),
                size,
                _rect_tuple(screen.availableGeometry()),
            )
        self.move(int(pos[0]), int(pos[1]))

    def _on_grip_moved(self, pos):
        self.settings.fixed_pos = (pos.x(), pos.y())

    # scale ------------------------------------------------------------

    def set_scale(self, value):
        """Set the hub scale and save it. The top-left corner stays put.

        Args:
            value (float): The scale, clamped to the allowed range.

        Returns:
            float: The clamped scale.
        """
        self.settings.scale = value
        self._apply_settings()
        return self.settings.scale

    # slider mode ------------------------------------------------------

    def set_slider_mode(self, mode_id):
        """Set the slider mode of every row and save it.

        Args:
            mode_id (str): The mode id, see ``modes.MODE_IDS``.
        """
        self.settings.slider_mode = mode_id
        mode = modes.get_mode(mode_id)
        self.mode_bar.set_mode(mode.mode_id)
        for row in self.rows:
            row.set_mode(mode)

    def wheelEvent(self, event):
        """Ctrl+wheel changes the scale."""
        if not event.modifiers() & QtCore.Qt.ControlModifier:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta:
            step = hub_settings.SCALE_STEP if delta > 0 else -hub_settings.SCALE_STEP
            self.set_scale(self.settings.scale + step)
        event.accept()

    # namespace --------------------------------------------------------

    def update_namespace(self):
        """Take the namespace of the selection, or the last stored one."""
        namespace = bm_core.selection_namespace()
        if namespace is None:
            namespace = bm_core.get_last_namespace()
        self.set_namespace(namespace)

    def set_namespace(self, namespace, store=False):
        """Set the namespace of the rows that follow it.

        Args:
            namespace (str): The namespace, or None.
            store (bool, optional): Also store it as the last namespace.
        """
        if store and namespace is not None:
            bm_core.set_last_namespace(namespace)
        self.namespace = namespace
        self.namespace_valid = bm_core.namespace_exists(namespace)
        self.namespace_label.set_namespace(namespace, self.namespace_valid)
        for row in self._all_rows():
            row.set_namespace(namespace, self.namespace_valid)

    def _fill_namespace_menu(self, menu):
        group = QtWidgets.QActionGroup(menu)
        namespaces = node_remap.scene_namespaces()
        if not namespaces:
            menu.addAction("(no namespaces)").setEnabled(False)
        for namespace in namespaces:
            action = menu.addAction(namespace)
            action.setCheckable(True)
            action.setChecked(namespace == self.namespace)
            group.addAction(action)
            action.triggered.connect(
                lambda checked=False, ns=namespace: self.set_namespace(ns, True)
            )

    def _show_namespace_menu(self):
        menu = QtWidgets.QMenu(self)
        self._fill_namespace_menu(menu)
        menu.exec_(QtGui.QCursor.pos())

    # drag -------------------------------------------------------------

    def _on_drag_started(self, active_row):
        """Hide everything but the dragged row, which stays in place."""
        self._pos_before_drag = self.pos()
        row_pos = active_row.mapToGlobal(QtCore.QPoint(0, 0))
        for row in self.rows:
            if row is not active_row:
                row.hide()
        self.top_bar.hide()
        self.tool_area.hide()
        self.mode_bar.hide()
        self.main_layout.activate()
        self.move(self.pos() + row_pos - active_row.mapToGlobal(QtCore.QPoint(0, 0)))

    def _on_drag_finished(self, active_row):
        """Show all rows again, at the position before the drag."""
        for row in self.rows:
            row.show()
        self._update_top_bar()
        self.main_layout.activate()
        if self._pos_before_drag is not None:
            self.move(self._pos_before_drag)
            self._pos_before_drag = None

    # settings menu ----------------------------------------------------

    def contextMenuEvent(self, event):
        """Show the settings menu."""
        menu = QtWidgets.QMenu(self)

        names_menu = menu.addMenu("Show Names")
        self._add_choices(
            names_menu,
            (
                ("Hover", hub_settings.SHOW_NAMES_HOVER),
                ("Always", hub_settings.SHOW_NAMES_ALWAYS),
            ),
            self.settings.show_names,
            self._set_show_names,
        )
        tooltips_action = menu.addAction("Show Tooltips")
        tooltips_action.setCheckable(True)
        tooltips_action.setChecked(self.settings.show_tooltips)
        tooltips_action.triggered.connect(self._set_show_tooltips)
        placement_menu = menu.addMenu("Placement")
        self._add_choices(
            placement_menu,
            (
                ("Under Cursor", hub_settings.PLACEMENT_CURSOR),
                ("Fixed Position", hub_settings.PLACEMENT_FIXED),
            ),
            self.settings.placement,
            self._set_placement,
        )
        menu.addAction("Selection Color...").triggered.connect(
            self._pick_selection_color
        )

        scale_action = QtWidgets.QWidgetAction(menu)
        scale_action.setDefaultWidget(
            ScaleMenuRow(lambda: self.settings.scale, self.set_scale)
        )
        menu.addAction(scale_action)

        menu.addSeparator()
        self._fill_namespace_menu(menu.addMenu("Namespace"))
        menu.addSeparator()
        menu.addAction("Close").triggered.connect(self.hide_hub)
        menu.exec_(event.globalPos())

    @staticmethod
    def _add_choices(menu, choices, current, func):
        group = QtWidgets.QActionGroup(menu)
        for label, value in choices:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == current)
            group.addAction(action)
            action.triggered.connect(lambda checked=False, v=value: func(v))

    def _set_show_names(self, mode):
        self.settings.show_names = mode
        self._apply_settings()

    def _set_show_tooltips(self, show):
        self.settings.show_tooltips = bool(show)
        self._apply_settings()

    def _set_placement(self, placement):
        self.settings.placement = placement
        if placement == hub_settings.PLACEMENT_FIXED:
            # start the fixed position where the hub is now
            self.settings.fixed_pos = (self.x(), self.y())
        self._update_top_bar()
        self.main_layout.activate()

    def _pick_selection_color(self):
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor.fromRgbF(*self.settings.selection_color),
            pyqt.maya_main_window(),
            "Selection Row Color",
        )
        if color.isValid():
            self.settings.selection_color = (
                color.redF(),
                color.greenF(),
                color.blueF(),
            )
            self.refresh()

    # callbacks --------------------------------------------------------

    def _start_callbacks(self):
        cbm = self._callbacks
        cbm.sceneMessageCB("afterNew", self._refresh_later, om2.MSceneMessage.kAfterNew)
        cbm.sceneMessageCB(
            "afterOpen", self._refresh_later, om2.MSceneMessage.kAfterOpen
        )

    def _on_scene_changed(self):
        if self.isVisible():
            self.update_namespace()
            self.refresh()

    def closeEvent(self, event):
        """Stop the callbacks."""
        self._callbacks.removeAllManagedCB()
        super(HubOverlay, self).closeEvent(event)


def get_hub(create=True):
    """Return the hub window, created on first use.

    Args:
        create (bool, optional): Create the hub when it does not exist.

    Returns:
        HubOverlay: The hub, or None when it does not exist and
            ``create`` is False.
    """
    global _hub
    if _hub is not None:
        try:
            _hub.isVisible()
        except RuntimeError:
            # the Qt object was deleted
            _hub = None
    if _hub is None and create:
        _hub = HubOverlay()
    return _hub


def toggle():
    """Show the hub when it is hidden, hide it when it is visible.

    Returns:
        HubOverlay: The hub window.
    """
    hub = get_hub()
    if hub.isVisible():
        hub.hide_hub()
    else:
        hub.show_hub()
    return hub
