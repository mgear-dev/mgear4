"""Bookmarks widgets.

ChipButton for bookmark chips. FlowLayout is re-exported from
mgear.core.widgets.
"""

from functools import partial

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from mgear.core.pyqt import dpi_scale
from mgear.core.pyqt import get_icon

# moved to mgear.core.widgets, kept here for backward compatibility
from mgear.core.widgets import FlowLayout  # noqa: F401

from . import core


#############################################
# CHIP BUTTON
#############################################


class ChipButton(QtWidgets.QPushButton):
    """Chip button representing a single bookmark.

    Left-click recalls the bookmark. Shift+click adds to selection,
    Ctrl+click deselects. Middle-click keys the members of a selection
    bookmark. Right-click opens context menu.

    Args:
        bookmark (dict): Bookmark data dictionary.
        parent (QWidget, optional): Parent widget.
    """

    chip_clicked = QtCore.Signal(object)
    secondary_action_requested = QtCore.Signal(object)
    rename_requested = QtCore.Signal(object)
    color_change_requested = QtCore.Signal(object)
    add_items_requested = QtCore.Signal(object)
    remove_items_requested = QtCore.Signal(object)
    add_to_shelf_requested = QtCore.Signal(object)
    delete_requested = QtCore.Signal(object)
    toggle_menu_requested = QtCore.Signal()
    toggle_namespace_mode_requested = QtCore.Signal(object)
    tool_toggled = QtCore.Signal(object, str, bool)
    key_members_requested = QtCore.Signal(object)
    drag_reorder = QtCore.Signal(object, object)

    def __init__(self, bookmark, parent=None):
        super(ChipButton, self).__init__(parent)
        self.bookmark = bookmark
        self._drag_start_pos = None
        self._update_display()

    def update_bookmark(self, bookmark):
        """Update the bookmark reference and refresh display.

        Args:
            bookmark (dict): Updated bookmark data.
        """
        self.bookmark = bookmark
        self._update_display()

    def _update_display(self):
        """Refresh text, tooltip, and stylesheet."""
        if self.bookmark["type"] == core.BOOKMARK_ISOLATE:
            self.setText("  " + self.bookmark["name"])
            icon_size = int(dpi_scale(14))
            pixmap = get_icon("mgear_eye", icon_size)
            self.setIcon(QtGui.QIcon(pixmap))
            self.setIconSize(QtCore.QSize(icon_size, icon_size))
        else:
            self.setText(self.bookmark["name"])
            self.setIcon(QtGui.QIcon())
        self._update_style()
        self._update_tooltip()

    def _update_style(self):
        """Apply stylesheet based on bookmark color."""
        r, g, b = self.bookmark["color"]
        r_int = int(r * 255)
        g_int = int(g * 255)
        b_int = int(b * 255)
        tr, tg, tb = core.text_color_for_background((r, g, b))
        text_color = "rgb({}, {}, {})".format(
            int(tr * 255), int(tg * 255), int(tb * 255)
        )

        radius = int(dpi_scale(4))
        h_pad = int(dpi_scale(8))
        v_pad = int(dpi_scale(3))
        font_size = int(dpi_scale(11))

        hover_r = max(0, r_int - 20)
        hover_g = max(0, g_int - 20)
        hover_b = max(0, b_int - 20)
        press_r = max(0, r_int - 40)
        press_g = max(0, g_int - 40)
        press_b = max(0, b_int - 40)

        self.setStyleSheet(
            "QPushButton {{"
            "    background-color: rgb({r}, {g}, {b});"
            "    color: {text};"
            "    border: none;"
            "    border-radius: {radius}px;"
            "    padding: {vpad}px {hpad}px;"
            "    font-size: {font}px;"
            "    font-weight: bold;"
            "}}"
            "QPushButton:hover {{"
            "    background-color: rgb({hr}, {hg}, {hb});"
            "}}"
            "QPushButton:pressed {{"
            "    background-color: rgb({pr}, {pg}, {pb});"
            "}}".format(
                r=r_int,
                g=g_int,
                b=b_int,
                text=text_color,
                radius=radius,
                vpad=v_pad,
                hpad=h_pad,
                font=font_size,
                hr=hover_r,
                hg=hover_g,
                hb=hover_b,
                pr=press_r,
                pg=press_g,
                pb=press_b,
            )
        )

    def _update_tooltip(self):
        """Set tooltip with bookmark details."""
        self.setToolTip(core.build_tooltip(self.bookmark))

    def mousePressEvent(self, event):
        """Record drag start position.

        Args:
            event (QMouseEvent): The mouse event.
        """
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super(ChipButton, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Start drag if moved past threshold.

        Args:
            event (QMouseEvent): The mouse event.
        """
        if not self._drag_start_pos:
            return
        if not (event.buttons() & QtCore.Qt.LeftButton):
            return
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < QtWidgets.QApplication.startDragDistance():
            return

        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setText("chip_drag")
        drag.setMimeData(mime)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        drag.exec_(QtCore.Qt.MoveAction)
        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        """Handle mouse release with modifier detection.

        Args:
            event (QMouseEvent): The mouse event.
        """
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start_pos = None
            self.chip_clicked.emit(self.bookmark)
        elif event.button() == QtCore.Qt.MiddleButton:
            if self.bookmark["type"] == core.BOOKMARK_SELECTION:
                self.key_members_requested.emit(self.bookmark)
        super(ChipButton, self).mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """Show right-click context menu.

        Args:
            event (QContextMenuEvent): The context menu event.
        """
        menu = QtWidgets.QMenu(self)

        # Secondary action: the other type's action on this bookmark's items.
        if self.bookmark["type"] == core.BOOKMARK_ISOLATE:
            secondary_action = menu.addAction("Select Items")
        else:
            secondary_action = menu.addAction("Isolate Selection")
        menu.addSeparator()

        rename_action = menu.addAction("Rename")
        color_action = menu.addAction("Change Color")
        menu.addSeparator()
        add_action = menu.addAction("Add Selected Items")
        remove_action = menu.addAction("Remove Selected Items")
        menu.addSeparator()
        ns_action = menu.addAction("Use Selected Object's Namespace")
        ns_action.setCheckable(True)
        ns_action.setChecked(
            bool(self.bookmark.get("use_selected_namespace", False))
        )
        if self.bookmark["type"] == core.BOOKMARK_SELECTION:
            tools_menu = menu.addMenu("Show In Tools")
            tools = core.registered_bookmark_tools()
            for tool_id, label in tools:
                tool_action = tools_menu.addAction(label)
                tool_action.setCheckable(True)
                tool_action.setChecked(
                    core.is_tool_enabled(self.bookmark, tool_id)
                )
                tool_action.triggered.connect(
                    partial(self._on_tool_triggered, tool_id, tool_action)
                )
            tools_menu.setEnabled(bool(tools))
        menu.addSeparator()
        shelf_action = menu.addAction("Add to Shelf")
        menu.addSeparator()
        toggle_menu_action = menu.addAction("Toggle Menu Bar")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Bookmark")

        action = menu.exec_(event.globalPos())

        if action == secondary_action:
            self.secondary_action_requested.emit(self.bookmark)
        elif action == rename_action:
            self.rename_requested.emit(self.bookmark)
        elif action == color_action:
            self.color_change_requested.emit(self.bookmark)
        elif action == add_action:
            self.add_items_requested.emit(self.bookmark)
        elif action == remove_action:
            self.remove_items_requested.emit(self.bookmark)
        elif action == ns_action:
            self.toggle_namespace_mode_requested.emit(self.bookmark)
        elif action == shelf_action:
            self.add_to_shelf_requested.emit(self.bookmark)
        elif action == toggle_menu_action:
            self.toggle_menu_requested.emit()
        elif action == delete_action:
            self.delete_requested.emit(self.bookmark)

    def _on_tool_triggered(self, tool_id, action, *args):
        """Emit tool_toggled for a "Show In Tools" action.

        The state is read from the action: PySide does not pass the
        ``checked`` argument of ``triggered`` to a ``partial`` slot.

        Args:
            tool_id (str): The tool id.
            action (QAction): The triggered action.
            *args: Signal arguments, ignored.
        """
        self.tool_toggled.emit(self.bookmark, tool_id, action.isChecked())
