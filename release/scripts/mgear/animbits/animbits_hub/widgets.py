"""Widgets of the Animbits Hub.

HubRow is the base class of the rows that tools add to the hub.
TweenSlider is the custom-painted tween slider. No widget takes keyboard
focus, so Maya hotkeys keep working while the hub is open.
"""

from functools import partial

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from mgear.core import pyqt

from . import geometry
from . import settings as hub_settings

# Alpha of the "empty" areas: invisible, but still catching the mouse, so
# clicks between the stops don't go through to the viewport
HIT_ALPHA = 1

DISABLED_ALPHA = 0.35


def _qcolor(color, alpha=1.0):
    """Return a QColor from an RGB 0-1 tuple."""
    return QtGui.QColor.fromRgbF(color[0], color[1], color[2], alpha)


def mode_tooltip(mode, title=None):
    """Return the rich tooltip of a slider mode.

    Args:
        mode (SliderMode): The mode.
        title (str, optional): Title. Defaults to the mode title.

    Returns:
        str: The tooltip HTML.
    """
    return pyqt.rich_tooltip(title or mode.title, mode.text, mode.bullets, mode.color)


_icon_cache = {}


def _icon(name, size, tint=None):
    """Return an icon pixmap, tinted, rendered once per name, size and tint."""
    key = (name, size, tint)
    if key not in _icon_cache:
        pixmap = pyqt.get_icon(name, size)
        if tint:
            pixmap = pyqt.tint_pixmap(pixmap, _qcolor(tint))
        _icon_cache[key] = pixmap
    return _icon_cache[key]


def _no_focus(widget):
    """Keep a widget from taking keyboard focus."""
    widget.setFocusPolicy(QtCore.Qt.NoFocus)


#############################################
# HUB ROW
#############################################


class HubRow(QtWidgets.QWidget):
    """Base class of the rows shown in the hub.

    A row holds a content widget and its name. The hub hides the other
    rows while one emits ``drag_started``, until it emits
    ``drag_finished``.

    Args:
        name (str): Name of the row, shown on hover or next to it.
        color (tuple): RGB 0-1 color of the row.
        parent (QWidget, optional): Parent widget.

    Attributes:
        uses_namespace (bool): True when the row depends on the hub
            namespace. Such rows are disabled while the namespace is
            missing from the scene.
    """

    drag_started = QtCore.Signal(object)
    drag_finished = QtCore.Signal(object)

    def __init__(self, name, color, parent=None):
        super(HubRow, self).__init__(parent)
        _no_focus(self)
        self.name = name
        self.color = tuple(color)
        self.uses_namespace = False
        self.namespace = None
        self._show_names = hub_settings.SHOW_NAMES_HOVER
        self._show_tooltips = True
        self._content = None

        self._name_label = QtWidgets.QLabel(name)
        self._name_label.setStyleSheet("color: {};".format(_qcolor(self.color).name()))
        self._name_label.hide()

        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._name_label)

    def set_content(self, widget):
        """Set the main widget of the row.

        Args:
            widget (QWidget): The widget, e.g. a TweenSlider.
        """
        self._content = widget
        self._layout.insertWidget(0, widget)

    def add_leading(self, widget):
        """Add a widget on the left of the row content.

        Args:
            widget (QWidget): The widget, e.g. a BufferButton.
        """
        self._layout.insertWidget(0, widget)

    def content_left(self):
        """Return where the row content starts, for column alignment.

        Returns:
            int: X position in row coordinates. Rows with a leading gutter
                (e.g. the buffer circle) return the start after it.
        """
        return 0

    def set_indent(self, indent):
        """Indent the row content, to align it with other rows.

        Args:
            indent (int): Left margin in pixels.
        """
        self._layout.setContentsMargins(indent, 0, 0, 0)

    def anchor(self):
        """Return the point to put under the cursor when the hub opens.

        Returns:
            QPoint: The point, in row coordinates.
        """
        if self._content and hasattr(self._content, "anchor"):
            return self._content.mapTo(self, self._content.anchor())
        return self.rect().center()

    def set_unit(self, unit):
        """Scale the row.

        Args:
            unit (float): Size unit in pixels.
        """
        if self._content and hasattr(self._content, "set_unit"):
            self._content.set_unit(unit)
        font = self._name_label.font()
        font.setPixelSize(max(1, int(round(unit * 1.1))))
        font.setBold(True)
        self._name_label.setFont(font)
        self._layout.setSpacing(int(round(unit * 0.6)))

    def set_show_names(self, mode):
        """Show the name next to the row, or only on hover.

        Args:
            mode (str): ``"hover"`` or ``"always"``.
        """
        self._show_names = mode
        self._name_label.setVisible(mode == hub_settings.SHOW_NAMES_ALWAYS)

    def set_show_tooltips(self, show):
        """Show rich help tooltips, or only the row name.

        Args:
            show (bool): True for rich tooltips.
        """
        self._show_tooltips = show

    def set_mode(self, mode):
        """Set the slider mode. Rows without modes ignore it.

        Args:
            mode (SliderMode): The mode.
        """

    def hover_tooltip(self):
        """Return the text shown when the pointer enters the row.

        The base row shows its name in "hover" name display. Subclasses
        add their help when rich tooltips are on.

        Returns:
            str: Plain or rich text, None for no tooltip.
        """
        if self._show_names == hub_settings.SHOW_NAMES_HOVER:
            return self.name
        return None

    def set_namespace(self, namespace, valid):
        """Set the hub namespace. Rows using it are disabled when invalid.

        Args:
            namespace (str): The namespace, or None.
            valid (bool): True when it exists in the scene.
        """
        if not self.uses_namespace:
            return
        self.namespace = namespace
        self.setEnabled(valid)

    def enterEvent(self, event):
        """Show the hover tooltip at once."""
        text = self.hover_tooltip()
        if text:
            pos = self.mapToGlobal(QtCore.QPoint(self.width(), 0))
            QtWidgets.QToolTip.showText(pos, text, self)
        super(HubRow, self).enterEvent(event)

    def leaveEvent(self, event):
        """Hide the hover name."""
        QtWidgets.QToolTip.hideText()
        super(HubRow, self).leaveEvent(event)


#############################################
# TWEEN SLIDER
#############################################


class TweenSlider(QtWidgets.QWidget):
    """Slider with a ``TW`` handle that springs back to the center.

    11 stops in 10% steps: squares at 0% and 100%, dots between. Only
    the stops and the handle are opaque. Dragging the handle emits the
    fraction under it; clicking a stop emits the stop's fraction.

    Args:
        color (tuple): RGB 0-1 color of the stops and the handle.
        label (str, optional): Handle text.
        unit (float, optional): Size unit in pixels.
        parent (QWidget, optional): Parent widget.
    """

    pressed = QtCore.Signal()
    drag_started = QtCore.Signal()
    fraction_changed = QtCore.Signal(float)
    drag_finished = QtCore.Signal()
    stop_clicked = QtCore.Signal(float)

    # sizes in units
    HANDLE_WIDTH = 2.8
    HANDLE_HEIGHT = 1.8
    STEP = 2.0
    SQUARE = 0.8
    DOT = 0.5

    def __init__(self, color, label="TW", unit=10.0, parent=None):
        super(TweenSlider, self).__init__(parent)
        _no_focus(self)
        self._color = tuple(color)
        self._text_color = pyqt.text_color_for_background(self._color)
        self._label = label
        self._unit = unit
        self._fraction = 0.5
        self._press_x = None
        self._grab_offset = 0.0
        self._dragging = False
        self._pressed_stop = None
        self.set_unit(unit)

    # geometry ---------------------------------------------------------

    def set_unit(self, unit):
        """Scale the slider.

        Args:
            unit (float): Size unit in pixels.
        """
        self._unit = float(unit)
        width = self._track_width() + self.HANDLE_WIDTH * self._unit
        height = (self.HANDLE_HEIGHT + 0.4) * self._unit
        self.setFixedSize(int(round(width)), int(round(height)))
        self.update()

    @property
    def unit(self):
        """float: Size unit in pixels."""
        return self._unit

    def _left(self):
        return self.HANDLE_WIDTH * self._unit / 2.0

    def _track_width(self):
        return self.STEP * self._unit * (geometry.STOP_COUNT - 1)

    def x_at(self, fraction):
        """Return the x position of a fraction on the slider.

        Args:
            fraction (float): 0 at the left square, 1 at the right one.

        Returns:
            float: X position in slider coordinates.
        """
        return self._left() + fraction * self._track_width()

    def _handle_rect(self, fraction=None):
        if fraction is None:
            fraction = self._fraction
        w = self.HANDLE_WIDTH * self._unit
        h = self.HANDLE_HEIGHT * self._unit
        return QtCore.QRectF(
            self.x_at(fraction) - w / 2.0, (self.height() - h) / 2.0, w, h
        )

    def set_label(self, label):
        """Set the handle text.

        Args:
            label (str): Short text, e.g. the mode label ``"BM"``.
        """
        self._label = label
        self.update()

    def anchor(self):
        """Return the center of the idle handle.

        Returns:
            QPoint: The point, in slider coordinates.
        """
        return self._handle_rect(0.5).center().toPoint()

    def _stop_at(self, pos):
        """Return the index of the stop under a point, or None."""
        radius = self.STEP * self._unit / 2.0
        for index, fraction in enumerate(geometry.stop_fractions()):
            if abs(pos.x() - self.x_at(fraction)) <= radius:
                return index
        return None

    # painting ---------------------------------------------------------

    def paintEvent(self, event):
        """Paint the stops and the handle on a transparent background."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, HIT_ALPHA))
        alpha = 1.0 if self.isEnabled() else DISABLED_ALPHA
        color = _qcolor(self._color, alpha)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color)

        cy = self.height() / 2.0
        last = geometry.STOP_COUNT - 1
        center = last // 2
        for index, fraction in enumerate(geometry.stop_fractions()):
            # the idle handle covers the 50% stop
            if index == center and self._fraction == 0.5:
                continue
            x = self.x_at(fraction)
            if index in (0, last):
                size = self.SQUARE * self._unit
                painter.drawRect(
                    QtCore.QRectF(x - size / 2.0, cy - size / 2.0, size, size)
                )
            else:
                radius = self.DOT * self._unit / 2.0
                painter.drawEllipse(QtCore.QPointF(x, cy), radius, radius)

        rect = self._handle_rect()
        corner = 0.3 * self._unit
        painter.drawRoundedRect(rect, corner, corner)
        font = painter.font()
        font.setPixelSize(max(1, int(round(self._unit))))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_qcolor(self._text_color, alpha))
        painter.drawText(rect, QtCore.Qt.AlignCenter, self._label)
        painter.end()

    # mouse ------------------------------------------------------------

    def mousePressEvent(self, event):
        """Grab the handle, or show the handle on the pressed stop."""
        if event.button() != QtCore.Qt.LeftButton:
            event.ignore()
            return
        pos = event.pos()
        if self._handle_rect().contains(QtCore.QPointF(pos)):
            self._press_x = pos.x()
            self._grab_offset = pos.x() - self.x_at(self._fraction)
            self.pressed.emit()
        else:
            self._pressed_stop = self._stop_at(pos)
            if self._pressed_stop is not None:
                self._fraction = geometry.stop_fractions()[self._pressed_stop]
                self.update()

    def mouseMoveEvent(self, event):
        """Drag the handle once past the drag distance."""
        if self._press_x is None:
            return
        x = event.pos().x()
        if not self._dragging:
            if abs(x - self._press_x) < QtWidgets.QApplication.startDragDistance():
                return
            self._dragging = True
            self.drag_started.emit()
        self._fraction = geometry.fraction_from_x(
            x - self._grab_offset, self._left(), self._track_width()
        )
        self.update()
        self.fraction_changed.emit(self._fraction)

    def mouseReleaseEvent(self, event):
        """Spring the handle back, or emit the clicked stop."""
        if event.button() != QtCore.Qt.LeftButton:
            event.ignore()
            return
        if self._dragging:
            self._finish_drag()
        elif self._pressed_stop is not None:
            if self._stop_at(event.pos()) == self._pressed_stop:
                fraction = geometry.stop_fractions()[self._pressed_stop]
                self.stop_clicked.emit(fraction)
            self._fraction = 0.5
            self.update()
        self._press_x = None
        self._pressed_stop = None

    def hideEvent(self, event):
        """End a running drag, e.g. when the hub hides in the middle."""
        if self._dragging:
            self._finish_drag()
        self._press_x = None
        self._pressed_stop = None
        self._fraction = 0.5
        super(TweenSlider, self).hideEvent(event)

    def _finish_drag(self):
        self._dragging = False
        self._fraction = 0.5
        self.update()
        self.drag_finished.emit()

    def wheelEvent(self, event):
        """Let the hub handle the wheel."""
        event.ignore()


#############################################
# HUB CHROME
#############################################


class NamespaceLabel(QtWidgets.QLabel):
    """Label showing the hub namespace. Clicking it emits ``clicked``.

    Args:
        parent (QWidget, optional): Parent widget.
    """

    clicked = QtCore.Signal()

    WARNING_COLOR = "#e8a050"

    def __init__(self, parent=None):
        super(NamespaceLabel, self).__init__(parent)
        _no_focus(self)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_namespace(None, False)

    def set_namespace(self, namespace, valid):
        """Show a namespace, marked when missing from the scene.

        Args:
            namespace (str): The namespace, or None.
            valid (bool): True when it exists in the scene.
        """
        if namespace is None:
            text = "ns: (none) ▾"
        else:
            text = "ns: {}{} ▾".format(namespace or ":", "" if valid else " (missing)")
        color = "#dddddd" if valid else self.WARNING_COLOR
        self.setText(text)
        self.setStyleSheet(
            "QLabel {{ color: {}; background: rgba(30, 30, 30, 160);"
            " border-radius: 3px; padding: 1px 5px; }}".format(color)
        )

    def set_unit(self, unit):
        """Scale the text.

        Args:
            unit (float): Size unit in pixels.
        """
        font = self.font()
        font.setPixelSize(max(1, int(round(unit * 1.0))))
        self.setFont(font)

    def mousePressEvent(self, event):
        """Emit ``clicked`` on a left click."""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        else:
            event.ignore()


class GripHandle(QtWidgets.QWidget):
    """Handle that moves its window. Emits ``moved`` with the new position.

    Args:
        parent (QWidget, optional): Parent widget.
    """

    moved = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent=None):
        super(GripHandle, self).__init__(parent)
        _no_focus(self)
        self.setCursor(QtCore.Qt.SizeAllCursor)
        self.setToolTip("Move the hub")
        self._offset = None
        self.set_unit(10.0)

    def set_unit(self, unit):
        """Scale the handle.

        Args:
            unit (float): Size unit in pixels.
        """
        self.setFixedSize(int(round(unit * 1.6)), int(round(unit * 1.6)))

    def paintEvent(self, event):
        """Paint a 2x3 dot grip."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(30, 30, 30, 160))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(220, 220, 220))
        radius = self.width() / 14.0
        for column in (1, 2):
            for row in (1, 2, 3):
                painter.drawEllipse(
                    QtCore.QPointF(
                        self.width() * column / 3.0, self.height() * row / 4.0
                    ),
                    radius,
                    radius,
                )
        painter.end()

    def mousePressEvent(self, event):
        """Start moving the window."""
        if event.button() == QtCore.Qt.LeftButton:
            window = self.window()
            self._offset = QtGui.QCursor.pos() - window.pos()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """Move the window with the cursor."""
        if self._offset is not None:
            self.window().move(QtGui.QCursor.pos() - self._offset)

    def mouseReleaseEvent(self, event):
        """Emit the final window position."""
        if self._offset is not None:
            self._offset = None
            self.moved.emit(self.window().pos())


class ModeButton(QtWidgets.QAbstractButton):
    """Checkable mode button, painted with the mode label.

    Args:
        mode (SliderMode): The mode.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, mode, parent=None):
        super(ModeButton, self).__init__(parent)
        _no_focus(self)
        self.mode = mode
        self._unit = 10.0
        self.setCheckable(True)
        self.set_unit(10.0)

    def set_unit(self, unit):
        """Scale the button.

        Args:
            unit (float): Size unit in pixels.
        """
        self._unit = float(unit)
        self.setFixedSize(int(round(unit * 2.6)), int(round(unit * 1.6)))
        self.update()

    def paintEvent(self, event):
        """Paint the label, filled with the mode color when checked."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, HIT_ALPHA))
        rect = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        corner = 0.3 * self._unit
        color = QtGui.QColor(self.mode.color)
        painter.setPen(QtCore.Qt.NoPen)
        if self.isChecked():
            painter.setBrush(color)
            text_color = QtGui.QColor(25, 25, 25)
        else:
            painter.setBrush(QtGui.QColor(30, 30, 30, 160))
            text_color = color
        painter.drawRoundedRect(rect, corner, corner)
        font = painter.font()
        font.setPixelSize(max(1, int(round(self._unit * 0.95))))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(rect, QtCore.Qt.AlignCenter, self.mode.label)
        painter.end()


class ModeBar(QtWidgets.QWidget):
    """Row of exclusive mode buttons. Emits ``mode_changed`` with the id.

    Args:
        modes (tuple): SliderMode objects, in display order.
        parent (QWidget, optional): Parent widget.
    """

    mode_changed = QtCore.Signal(str)

    def __init__(self, modes, parent=None):
        super(ModeBar, self).__init__(parent)
        _no_focus(self)
        self.buttons = {}
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        for mode in modes:
            button = ModeButton(mode)
            self._group.addButton(button)
            self._layout.addWidget(button)
            self.buttons[mode.mode_id] = button
            button.clicked.connect(partial(self._on_clicked, mode.mode_id))
        self._layout.addStretch()

    def _on_clicked(self, mode_id, *args):
        self.mode_changed.emit(mode_id)

    def set_mode(self, mode_id):
        """Check the button of a mode, without emitting ``mode_changed``.

        Args:
            mode_id (str): The mode id.
        """
        button = self.buttons.get(mode_id)
        if button:
            button.setChecked(True)

    def set_unit(self, unit):
        """Scale the buttons.

        Args:
            unit (float): Size unit in pixels.
        """
        for button in self.buttons.values():
            button.set_unit(unit)
        self._layout.setSpacing(int(round(unit * 0.3)))

    def set_indent(self, indent):
        """Indent the buttons, to align them with the rows.

        Args:
            indent (int): Left margin in pixels.
        """
        self._layout.setContentsMargins(indent, 0, 0, 0)

    def set_show_tooltips(self, show):
        """Use rich tooltips, or the mode titles only.

        Args:
            show (bool): True for rich tooltips.
        """
        for button in self.buttons.values():
            mode = button.mode
            button.setToolTip(mode_tooltip(mode) if show else mode.title)


class BufferButton(QtWidgets.QWidget):
    """Circle on the left of a row: hollow when empty, filled when stored.

    It only reacts and paints while active (the buffer mode), but always
    keeps its size so the rows don't move between modes. Click emits
    ``store_requested``, Ctrl+click ``clear_requested``.

    Args:
        color (tuple): RGB 0-1 color of the row.
        parent (QWidget, optional): Parent widget.

    Attributes:
        active (bool): True in the buffer mode, see :meth:`set_active`.
    """

    store_requested = QtCore.Signal()
    clear_requested = QtCore.Signal()

    def __init__(self, color, parent=None):
        super(BufferButton, self).__init__(parent)
        _no_focus(self)
        self._color = tuple(color)
        self._filled = False
        self.active = False
        self._unit = 10.0
        self.set_unit(10.0)

    def set_unit(self, unit):
        """Scale the button.

        Args:
            unit (float): Size unit in pixels.
        """
        self._unit = float(unit)
        size = int(round(unit * 1.6))
        self.setFixedSize(size, size)
        self.update()

    def set_active(self, active):
        """Show and enable the button, or keep only its space.

        Args:
            active (bool): True in the buffer mode.
        """
        self.active = active
        cursor = QtCore.Qt.PointingHandCursor if active else QtCore.Qt.ArrowCursor
        self.setCursor(cursor)
        self.update()

    def set_filled(self, filled):
        """Draw the circle filled (a buffer is stored) or hollow.

        Args:
            filled (bool): True when the row has a buffer.
        """
        self._filled = filled
        self.update()

    def paintEvent(self, event):
        """Paint the circle while active."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, HIT_ALPHA))
        if self.active:
            alpha = 1.0 if self.isEnabled() else DISABLED_ALPHA
            color = _qcolor(self._color, alpha)
            pen = QtGui.QPen(color)
            pen.setWidthF(max(1.0, self._unit * 0.18))
            painter.setPen(pen)
            painter.setBrush(color if self._filled else QtCore.Qt.NoBrush)
            radius = self._unit * 0.5
            painter.drawEllipse(QtCore.QRectF(self.rect()).center(), radius, radius)
        painter.end()

    def mousePressEvent(self, event):
        """Store, or clear with Ctrl."""
        if not self.active or event.button() != QtCore.Qt.LeftButton:
            event.ignore()
            return
        if event.modifiers() & QtCore.Qt.ControlModifier:
            self.clear_requested.emit()
        else:
            self.store_requested.emit()


#############################################
# TOOL AREA
#############################################


class HubToolWidget(QtWidgets.QWidget):
    """Base class of the widgets that tools add to the hub tool area.

    The hub calls :meth:`set_unit` and :meth:`set_show_tooltips` like it
    does for the rows.

    Args:
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, parent=None):
        super(HubToolWidget, self).__init__(parent)
        _no_focus(self)
        self._unit = 10.0
        self._show_tooltips = True
        self._row_name = None

    def set_unit(self, unit):
        """Scale the widget.

        Args:
            unit (float): Size unit in pixels.
        """
        self._unit = float(unit)
        self.update()

    def set_row_name(self, name):
        """Name the row in the tooltip titles, e.g. ``Nudge forward · Arms``.

        Args:
            name (str): Row name, None to leave it out.
        """
        self._row_name = name
        self.update_tooltip()

    def update_tooltip(self):
        """Rebuild the tooltips. Subclasses with tooltips implement it."""

    def build_tooltip(self, title, text, bullets=None, color=None, state=None):
        """Return a rich or short tooltip, per the tooltip setting.

        Args:
            title (str): Tool title; the row name is added when set.
            text (str): What the tool does.
            bullets (tuple, optional): Usage notes.
            color (str, optional): Rich tooltip title color.
            state (str, optional): State line, always shown.

        Returns:
            str: The tooltip.
        """
        title = self.tooltip_title(title)
        if self._show_tooltips:
            text = "{} {}".format(state, text) if state else text
            return pyqt.rich_tooltip(title, text, bullets, color)
        return "{}: {}".format(title, state) if state else title

    def tooltip_title(self, title):
        """Return a tooltip title with the row name, when it is set.

        Args:
            title (str): Tool title.

        Returns:
            str: ``"<title> · <row name>"`` or the title.
        """
        if self._row_name:
            return "{} · {}".format(title, self._row_name)
        return title

    def set_show_tooltips(self, show):
        """Use rich help tooltips, or short ones.

        Args:
            show (bool): True for rich tooltips.
        """
        self._show_tooltips = show
        self.update_tooltip()


class HubToolButton(HubToolWidget):
    """Square button with an icon, for the hub tool area.

    Args:
        icon (str): mGear icon name, e.g. ``"mgear_copy"``.
        title (str): Tool name, the short tooltip.
        text (str): What the tool does, for the rich tooltip.
        bullets (tuple, optional): Usage notes for the rich tooltip.
        color (str, optional): Rich tooltip title color.
        state (callable, optional): Returns a state line always shown in
            the tooltip, e.g. what a buffer holds.
        tint (tuple, optional): RGB 0-1 color to draw the icon in, e.g.
            the row color.
        parent (QWidget, optional): Parent widget.
    """

    clicked = QtCore.Signal()

    def __init__(
        self,
        icon,
        title,
        text,
        bullets=None,
        color=None,
        state=None,
        tint=None,
        parent=None,
    ):
        super(HubToolButton, self).__init__(parent)
        self.icon = icon
        self.title = title
        self.text = text
        self.bullets = bullets
        self.color = color
        self.state = state
        self.tint = tint
        self.dim = False
        self.highlight = False
        self._pixmap = None
        self.set_unit(10.0)

    def set_unit(self, unit):
        """Scale the button.

        Args:
            unit (float): Size unit in pixels.
        """
        super(HubToolButton, self).set_unit(unit)
        size = int(round(unit * 2.2))
        self.setFixedSize(size, size)
        self._pixmap = _icon(self.icon, int(round(unit * 1.5)), self.tint)

    def set_icon(self, icon):
        """Change the icon, e.g. for another state of the tool.

        Args:
            icon (str): mGear icon name.
        """
        self.icon = icon
        self._pixmap = _icon(icon, int(round(self._unit * 1.5)), self.tint)
        self.update()

    def set_highlight(self, highlight):
        """Draw a frame in the tint color, e.g. while a tool waits for a click.

        Args:
            highlight (bool): True to draw the frame.
        """
        self.highlight = highlight
        self.update()

    def set_dim(self, dim):
        """Draw the button dim, e.g. while there is nothing to paste.

        Args:
            dim (bool): True to draw it dim.
        """
        self.dim = dim
        self.update()

    def update_tooltip(self):
        """Rebuild the tooltip, e.g. after the state changed."""
        state = self.state() if self.state else None
        self.setToolTip(
            self.build_tooltip(self.title, self.text, self.bullets, self.color, state)
        )

    def paintEvent(self, event):
        """Paint the background, lighter on hover, and the icon."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        alpha = 220 if self.underMouse() else 160
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(30, 30, 30, alpha))
        corner = 0.3 * self._unit
        painter.drawRoundedRect(rect, corner, corner)
        if self.highlight:
            pen = QtGui.QPen(_qcolor(self.tint or (1.0, 1.0, 1.0)))
            pen.setWidthF(max(1.0, self._unit * 0.15))
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), corner, corner)
        if self._pixmap:
            painter.setOpacity(DISABLED_ALPHA if self.dim else 1.0)
            x = (self.width() - self._pixmap.width()) / 2.0
            y = (self.height() - self._pixmap.height()) / 2.0
            painter.drawPixmap(QtCore.QPointF(x, y), self._pixmap)
        painter.end()

    def enterEvent(self, event):
        """Repaint for the hover highlight."""
        self.update()
        super(HubToolButton, self).enterEvent(event)

    def leaveEvent(self, event):
        """Repaint without the hover highlight."""
        self.update()
        super(HubToolButton, self).leaveEvent(event)

    def mousePressEvent(self, event):
        """Emit ``clicked`` on a left click."""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        else:
            event.ignore()


class NudgeWidget(HubToolWidget):
    """Nudge Keys controls: ``[<] amount [>] ripple``.

    The mouse wheel over the amount changes it by one; clicking it opens a
    popup to type a value. Popups can take the keyboard focus, the hub
    can't.

    Args:
        amount (int): The nudge amount.
        ripple (bool): The ripple state.
        tint (tuple, optional): RGB 0-1 color of the icons and the amount.
        parent (QWidget, optional): Parent widget.
    """

    nudge_requested = QtCore.Signal(int)
    amount_changed = QtCore.Signal(int)
    ripple_changed = QtCore.Signal(bool)

    TITLE = "Nudge Keys"
    TEXT = (
        "Shift keys earlier or later by the number of frames in the field. "
        "The current time moves with them."
    )
    BULLETS = (
        "Moves the selected keys (Graph Editor, Dope Sheet) first.",
        "Else the keys in the timeline range selection (Shift+drag).",
        "Else the keys on the current frame (Channel Box attributes only "
        "when some are selected).",
        "Wheel over the number to change it, click it to type a value.",
        "Ripple also moves all the later keys.",
        "Blocked when keys would overlap other keys.",
    )
    COLOR = "#8a9bd9"

    def __init__(self, amount, ripple, tint=None, parent=None):
        super(NudgeWidget, self).__init__(parent)
        self.amount = amount
        self.ripple = ripple
        self.tint = tint
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._layout = layout
        self.left_button = HubToolButton(
            "mgear_chevron-left",
            "Nudge back",
            self.TEXT,
            self.BULLETS,
            self.COLOR,
            tint=tint,
        )
        self.right_button = HubToolButton(
            "mgear_chevron-right",
            "Nudge forward",
            self.TEXT,
            self.BULLETS,
            self.COLOR,
            tint=tint,
        )
        self.amount_label = QtWidgets.QLabel()
        self.amount_label.setAlignment(QtCore.Qt.AlignCenter)
        self.amount_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.ripple_button = HubToolButton(
            "mgear_chevrons-right",
            "Ripple",
            "Also move all the keys after the nudged keys.",
            color=self.COLOR,
            tint=tint,
        )
        for widget in (
            self.left_button,
            self.amount_label,
            self.right_button,
            self.ripple_button,
        ):
            _no_focus(widget)
            layout.addWidget(widget)
        self.left_button.clicked.connect(
            lambda: self.nudge_requested.emit(-self.amount)
        )
        self.right_button.clicked.connect(
            lambda: self.nudge_requested.emit(self.amount)
        )
        self.ripple_button.clicked.connect(self._toggle_ripple)
        self.amount_label.installEventFilter(self)
        color = _qcolor(self.tint).name() if self.tint else "#dddddd"
        self.amount_label.setStyleSheet(
            "QLabel {{ color: {}; background: rgba(30, 30, 30, 160);"
            " border-radius: 3px; }}".format(color)
        )
        self._update_amount()
        self._update_ripple()
        self.set_unit(10.0)

    def set_unit(self, unit):
        """Scale the controls.

        Args:
            unit (float): Size unit in pixels.
        """
        super(NudgeWidget, self).set_unit(unit)
        for button in (self.left_button, self.right_button, self.ripple_button):
            button.set_unit(unit)
        font = self.amount_label.font()
        font.setPixelSize(max(1, int(round(unit * 1.2))))
        font.setBold(True)
        self.amount_label.setFont(font)
        self.amount_label.setFixedSize(int(round(unit * 3.0)), int(round(unit * 2.2)))
        self._layout.setSpacing(int(round(unit * 0.3)))

    def set_show_tooltips(self, show):
        """Use rich help tooltips, or short ones.

        Args:
            show (bool): True for rich tooltips.
        """
        for button in (self.left_button, self.right_button, self.ripple_button):
            button.set_show_tooltips(show)
        super(NudgeWidget, self).set_show_tooltips(show)

    def set_row_name(self, name):
        """Name the row in the tooltip titles.

        Args:
            name (str): Row name, None to leave it out.
        """
        for button in (self.left_button, self.right_button, self.ripple_button):
            button.set_row_name(name)
        super(NudgeWidget, self).set_row_name(name)

    def update_tooltip(self):
        """Rebuild the tooltip of the amount."""
        self.amount_label.setToolTip(
            self.build_tooltip(self.TITLE, self.TEXT, self.BULLETS, self.COLOR)
        )

    def set_amount(self, amount):
        """Set the nudge amount, clamped to 1-100, and emit the change.

        Args:
            amount (int): Frames.
        """
        amount = hub_settings.clamp_nudge(amount)
        if amount == self.amount:
            return
        self.amount = amount
        self._update_amount()
        self.amount_changed.emit(amount)

    def _update_amount(self):
        self.amount_label.setText(str(self.amount))

    def _toggle_ripple(self):
        self.ripple = not self.ripple
        self._update_ripple()
        self.ripple_changed.emit(self.ripple)

    def _update_ripple(self):
        self.ripple_button.set_dim(not self.ripple)

    def _edit_amount(self):
        menu = QtWidgets.QMenu(self)
        spin = QtWidgets.QSpinBox()
        spin.setRange(hub_settings.NUDGE_MIN, hub_settings.NUDGE_MAX)
        spin.setValue(self.amount)
        action = QtWidgets.QWidgetAction(menu)
        action.setDefaultWidget(spin)
        menu.addAction(action)
        spin.editingFinished.connect(menu.close)
        menu.aboutToShow.connect(spin.setFocus)
        menu.exec_(QtGui.QCursor.pos())
        self.set_amount(spin.value())

    def eventFilter(self, watched, event):
        """Wheel and click on the amount."""
        if watched is self.amount_label:
            if event.type() == QtCore.QEvent.Wheel:
                step = 1 if event.angleDelta().y() > 0 else -1
                self.set_amount(self.amount + step)
                return True
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton:
                    self._edit_amount()
                    return True
        return super(NudgeWidget, self).eventFilter(watched, event)


class HubToolRow(HubRow):
    """Row of tool widgets for the hub tool area, e.g. the key tools.

    Args:
        name (str): Row name, e.g. the bookmark name.
        color (tuple): RGB 0-1 row color.
        widgets (list): HubToolWidget widgets, left to right.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, name, color, widgets, parent=None):
        super(HubToolRow, self).__init__(name, color, parent)
        self.widgets = list(widgets)
        content = QtWidgets.QWidget()
        _no_focus(content)
        self._content_layout = QtWidgets.QHBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        for widget in self.widgets:
            self._content_layout.addWidget(widget)
        self.set_content(content)

    def set_unit(self, unit):
        """Scale the row and its widgets.

        Args:
            unit (float): Size unit in pixels.
        """
        super(HubToolRow, self).set_unit(unit)
        for widget in self.widgets:
            widget.set_unit(unit)
        self._content_layout.setSpacing(int(round(unit * 0.3)))

    def set_show_tooltips(self, show):
        """Use rich help tooltips on the widgets, or short ones.

        Args:
            show (bool): True for rich tooltips.
        """
        super(HubToolRow, self).set_show_tooltips(show)
        for widget in self.widgets:
            widget.set_show_tooltips(show)

    def set_show_names(self, mode):
        """Show the name next to the row, or in the tooltip titles.

        Args:
            mode (str): ``"hover"`` or ``"always"``.
        """
        super(HubToolRow, self).set_show_names(mode)
        name = self.name if mode == hub_settings.SHOW_NAMES_HOVER else None
        for widget in self.widgets:
            widget.set_row_name(name)

    def hover_tooltip(self):
        """Return None: the tool widgets name the row in their tooltips.

        Returns:
            None: No row tooltip.
        """
        return None


class ScaleMenuRow(QtWidgets.QWidget):
    """Menu row ``Scale [-] 100% [+]``. Its buttons don't close the menu.

    Args:
        get_scale (callable): Returns the current scale.
        set_scale (callable): Sets a scale, returns the clamped scale.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, get_scale, set_scale, parent=None):
        super(ScaleMenuRow, self).__init__(parent)
        self._set_scale = set_scale
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(24, 2, 8, 2)
        layout.addWidget(QtWidgets.QLabel("Scale"))
        layout.addStretch()
        self.minus_button = QtWidgets.QToolButton()
        self.minus_button.setText("−")
        self.value_label = QtWidgets.QLabel()
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setMinimumWidth(40)
        self.plus_button = QtWidgets.QToolButton()
        self.plus_button.setText("+")
        for widget in (self.minus_button, self.value_label, self.plus_button):
            layout.addWidget(widget)
        self.minus_button.clicked.connect(lambda: self._step(-hub_settings.SCALE_STEP))
        self.plus_button.clicked.connect(lambda: self._step(hub_settings.SCALE_STEP))
        self._scale = get_scale()
        self._update_label()

    def _step(self, delta):
        self._scale = self._set_scale(self._scale + delta)
        self._update_label()

    def _update_label(self):
        self.value_label.setText("{:d}%".format(int(round(self._scale * 100))))
