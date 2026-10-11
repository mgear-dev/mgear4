"""Widgets of the Animbits Hub.

HubRow is the base class of the rows that tools add to the hub.
TweenSlider is the custom-painted tween slider. No widget takes keyboard
focus, so Maya hotkeys keep working while the hub is open.
"""

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
        """Show the name at once in hover mode."""
        if self._show_names == hub_settings.SHOW_NAMES_HOVER:
            pos = self.mapToGlobal(QtCore.QPoint(self.width(), 0))
            QtWidgets.QToolTip.showText(pos, self.name, self)
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

    def _left(self):
        return self.HANDLE_WIDTH * self._unit / 2.0

    def _track_width(self):
        return self.STEP * self._unit * (geometry.STOP_COUNT - 1)

    def _x_at(self, fraction):
        return self._left() + fraction * self._track_width()

    def _handle_rect(self, fraction=None):
        if fraction is None:
            fraction = self._fraction
        w = self.HANDLE_WIDTH * self._unit
        h = self.HANDLE_HEIGHT * self._unit
        return QtCore.QRectF(
            self._x_at(fraction) - w / 2.0, (self.height() - h) / 2.0, w, h
        )

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
            if abs(pos.x() - self._x_at(fraction)) <= radius:
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
            x = self._x_at(fraction)
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
            self._grab_offset = pos.x() - self._x_at(self._fraction)
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
