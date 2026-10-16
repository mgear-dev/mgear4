"""mGear Qt custom widgets"""

import json
import os
from functools import partial

from mgear.vendor.Qt import QtCore, QtWidgets, QtGui
from maya import cmds
import maya.OpenMaya as api
from mgear.core import pyqt
from mgear.core import ui_style


#################################################
# CUSTOM WIDGETS
#################################################


class TableWidgetDragRows(QtWidgets.QTableWidget):
    """qTableWidget with drag and drop functionality"""

    def __init__(self, *args, **kwargs):
        super(TableWidgetDragRows, self).__init__(*args, **kwargs)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)

    def dropEvent(self, event):
        if not event.isAccepted() and event.source() == self:
            drop_row = self.drop_on(event)

            rows = sorted(set(item.row() for item in self.selectedItems()))
            rows_to_move = [
                [
                    QtWidgets.QTableWidgetItem(
                        self.item(row_index, column_index)
                    )
                    for column_index in range(self.columnCount())
                ]
                for row_index in rows
            ]

            for row_index in reversed(rows):
                self.removeRow(row_index)
                if row_index < drop_row:
                    drop_row -= 1

            for row_index, data in enumerate(rows_to_move):
                row_index += drop_row
                self.insertRow(row_index)
                for column_index, column_data in enumerate(data):
                    self.setItem(row_index, column_index, column_data)
            event.accept()
            for row_index in range(len(rows_to_move)):
                for column_index in range(self.columnCount()):
                    self.item(drop_row + row_index, column_index).setSelected(
                        True
                    )

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()

        return (
            index.row() + 1
            if self.is_below(event.pos(), index)
            else index.row()
        )

    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        return (
            rect.contains(pos, True)
            and not (
                int(self.model().flags(index)) & QtCore.Qt.ItemIsDropEnabled
            )
            and pos.y() >= rect.center().y()
        )

    def getSelectedRowsFast(self):
        selRows = []
        for item in self.selectedItems():
            if item.row() not in selRows:
                selRows.append(item.row())
        return selRows

    def droppingOnItself(self, event, index):
        dropAction = event.dropAction()

        if self.dragDropMode() == QtWidgets.QAbstractItemView.InternalMove:
            dropAction = QtCore.Qt.MoveAction

        if (
            event.source() == self
            and event.possibleActions() & QtCore.Qt.MoveAction
            and dropAction == QtCore.Qt.MoveAction
        ):
            selectedIndexes = self.selectedIndexes()
            child = index
            while child.isValid() and child != self.rootIndex():
                if child in selectedIndexes:
                    return True
                child = child.parent()

        return False

    def dropOn(self, event):
        if event.isAccepted():
            return False, None, None, None

        index = QtWidgets.QModelIndex()
        row = -1
        col = -1

        if self.viewport().rect().contains(event.pos()):
            index = self.indexAt(event.pos())
            if not index.isValid() or not self.visualRect(index).contains(
                event.pos()
            ):
                index = self.rootIndex()

        if self.model().supportedDropActions() & event.dropAction():
            if index != self.rootIndex():
                dropIndicatorPosition = self.position(
                    event.pos(), self.visualRect(index), index
                )
                qabw = QtWidgets.QAbstractItemView
                if dropIndicatorPosition == qabw.AboveItem:
                    row = index.row()
                    col = index.column()
                elif dropIndicatorPosition == qabw.BelowItem:
                    row = index.row() + 1
                    col = index.column()
                else:
                    row = index.row()
                    col = index.column()

            if not self.droppingOnItself(event, index):
                return True, row, col, index

        return False, None, None, None

    def position(self, pos, rect, index):
        r = QtWidgets.QAbstractItemView.OnViewport
        margin = 5
        if pos.y() - rect.top() < margin:
            r = QtWidgets.QAbstractItemView.AboveItem
        elif rect.bottom() - pos.y() < margin:
            r = QtWidgets.QAbstractItemView.BelowItem
        elif rect.contains(pos, True):
            r = QtWidgets.QAbstractItemView.OnItem

        if r == QtWidgets.QAbstractItemView.OnItem and not (
            self.model().flags(index) & QtCore.Qt.ItemIsDropEnabled
        ):
            if pos.y() < rect.center().y():
                r = QtWidgets.QAbstractItemView.AboveItem
            else:
                r = QtWidgets.QAbstractItemView.BelowItem

        return r


######################################
# drag and drop QListView to Maya view
######################################


def selectFromScreenApi(x, y, x_rect=None, y_rect=None):
    """Find the object under the cursor on Maya view


    found here: http://nathanhorne.com/maya-python-selectfromscreen/
    Thanks Nathan!
    Args:
        x (int): rectable selection start x
        y (int): rectagle selection start y
        x_rect (int, optional): rectable selection end x
        y_rect (int, optional): rectagle selection end y

    Returns:
        list of str: Name of the objects under the cursor
    """
    # get current selection
    sel = api.MSelectionList()
    api.MGlobal.getActiveSelectionList(sel)

    # select from screen
    if x_rect is not None and y_rect is not None:
        api.MGlobal.selectFromScreen(
            x, y, x_rect, y_rect, api.MGlobal.kReplaceList
        )
    else:
        api.MGlobal.selectFromScreen(x, y, api.MGlobal.kReplaceList)
    objects = api.MSelectionList()
    api.MGlobal.getActiveSelectionList(objects)

    # restore selection
    api.MGlobal.setActiveSelectionList(sel, api.MGlobal.kReplaceList)

    # return the objects as strings
    fromScreen = []
    objects.getSelectionStrings(fromScreen)
    return fromScreen


class DragQListView(QtWidgets.QListView):
    """QListView with basic drop functionality

    Attributes:
        exp (int): Extend the mouse position to a rectable
        theAction (func): function triggered when drop
    """

    def __init__(self, parent):
        super(DragQListView, self).__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setDefaultDropAction(QtCore.Qt.CopyAction)
        self.exp = 3
        self.ignore_self = True

    def mouseMoveEvent(self, event):
        mimeData = QtCore.QMimeData()
        mimeData.setText("%d,%d" % (event.x(), event.y()))

        drag = QtGui.QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos())
        try:
            dropAction = drag.start(QtCore.Qt.MoveAction)  # PySide2
        except AttributeError:
            dropAction = drag.exec(QtCore.Qt.MoveAction)  # PySide6
        if not dropAction == QtCore.Qt.MoveAction:
            pos = QtGui.QCursor.pos()
            widget = QtWidgets.QApplication.widgetAt(pos)
            if self.ignore_self and (
                widget is self
                or widget.objectName() == "qt_scrollarea_viewport"
            ):
                return
            relpos = widget.mapFromGlobal(pos)
            # need to invert Y axis
            invY = widget.frameSize().height() - relpos.y()
            sel = selectFromScreenApi(
                relpos.x() - self.exp,
                invY - self.exp,
                relpos.x() + self.exp,
                invY + self.exp,
            )

            self.doAction(sel)

    def setAction(self, action):
        self.theAction = action

    def doAction(self, sel):
        self.theAction(sel)


######################################
# collapsible widget
######################################


class CollapsibleHeader(QtWidgets.QWidget):
    COLLAPSED_PIXMAP = QtGui.QPixmap(":teRightArrow.png")
    EXPANDED_PIXMAP = QtGui.QPixmap(":teDownArrow.png")

    clicked = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(CollapsibleHeader, self).__init__(parent)

        self.setAutoFillBackground(True)
        self.set_background_color(None)

        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedWidth(self.COLLAPSED_PIXMAP.width())

        self.text_label = QtWidgets.QLabel()
        self.text_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.text_label)

        self.set_text(text)
        self.set_expanded(True)

    def set_text(self, text):
        self.text_label.setText("<b>{0}</b>".format(text))

    def set_background_color(self, color):
        if not color:
            color = (
                QtWidgets.QPushButton().palette().color(QtGui.QPalette.Button)
            )

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)

    def is_expanded(self):
        return self._expanded

    def set_expanded(self, expanded):
        self._expanded = expanded

        if self._expanded:
            self.icon_label.setPixmap(self.EXPANDED_PIXMAP)
        else:
            self.icon_label.setPixmap(self.COLLAPSED_PIXMAP)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()


class CollapsibleWidget(QtWidgets.QWidget):
    # emitted with the new state when the widget is expanded or collapsed
    expandedChanged = QtCore.Signal(bool)

    def __init__(self, text, expanded=True, expandable=True, parent=None):
        """Create a collapsible widget with header and body.

        Args:
            text: Header text
            expanded: Initial expanded state
            expandable: If True, widget expands to fill available space when
                       expanded. If False, widget stays fixed size.
            parent: Parent widget
        """
        super(CollapsibleWidget, self).__init__(parent)

        self._expandable = expandable
        self.header_wgt = CollapsibleHeader(text)
        self.header_wgt.clicked.connect(self.on_header_clicked)
        self.body_wgt = QtWidgets.QWidget()

        self.body_layout = QtWidgets.QVBoxLayout(self.body_wgt)
        self.body_layout.setContentsMargins(4, 2, 4, 2)
        self.body_layout.setSpacing(3)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.header_wgt)
        self.main_layout.addWidget(self.body_wgt)

        self.set_expanded(expanded)

    def addWidget(self, widget):
        self.body_layout.addWidget(widget)

    def addLayout(self, layout):
        self.body_layout.addLayout(layout)

    def is_expanded(self):
        """Return True when the body is shown.

        Returns:
            bool: The expanded state.
        """
        return self.header_wgt.is_expanded()

    def is_expandable(self):
        """Return True when the widget grows to fill space once expanded.

        Returns:
            bool: The expandable setting.
        """
        return self._expandable

    def set_expanded(self, expanded):
        changed = expanded != self.header_wgt.is_expanded()
        self.header_wgt.set_expanded(expanded)
        self.body_wgt.setVisible(expanded)
        # Update size policy based on expanded state and expandable setting
        if expanded and self._expandable:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred,
                QtWidgets.QSizePolicy.Expanding
            )
        else:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred,
                QtWidgets.QSizePolicy.Fixed
            )
        if changed:
            self.expandedChanged.emit(expanded)

    def set_header_background_color(self, color):
        self.header_wgt.set_background_color(color)

    def on_header_clicked(self):
        self.set_expanded(not self.header_wgt.is_expanded())


class ColorSwatchButton(QtWidgets.QPushButton):
    """Button that shows an RGB color and edits it with a color picker.

    Colors are 0-1 RGB tuples. ``colorChanged`` is emitted when the color
    changes, either from the picker or from :meth:`set_color`.
    """

    colorChanged = QtCore.Signal(tuple)

    def __init__(self, color=(1.0, 1.0, 1.0), width=60, parent=None):
        """Initialize the swatch.

        Args:
            color (tuple, optional): Initial RGB color, 0-1 range.
            width (int, optional): Fixed button width in pixels.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(ColorSwatchButton, self).__init__(parent)
        self._color = tuple(color)
        self.setFixedWidth(width)
        self.clicked.connect(self._pick_color)
        self._update_swatch()

    def color(self):
        """Return the current color.

        Returns:
            tuple: RGB color, 0-1 range.
        """
        return self._color

    def set_color(self, color):
        """Set the current color.

        Args:
            color (tuple): RGB color, 0-1 range.
        """
        color = tuple(float(c) for c in color[:3])
        if color == self._color:
            return
        self._color = color
        self._update_swatch()
        self.colorChanged.emit(color)

    def settings_value(self):
        """Return the color for pyqt.SettingsMixin.

        Returns:
            list: RGB values, 0-1 range.
        """
        return list(self._color)

    def set_settings_value(self, value):
        """Set the color from a stored value (pyqt.SettingsMixin).

        Invalid values are ignored.

        Args:
            value (object): RGB list / tuple, or a comma-separated string.
        """
        if isinstance(value, str):
            value = value.split(",")
        try:
            rgb = [float(c) for c in value]
        except (TypeError, ValueError):
            return
        if len(rgb) >= 3:
            self.set_color(rgb)

    def settings_signal(self):
        """Return the signal emitted when the color changes.

        Returns:
            QtCore.Signal: ``colorChanged``.
        """
        return self.colorChanged

    def _pick_color(self):
        """Open the color picker and apply the chosen color."""
        chosen = QtWidgets.QColorDialog.getColor(
            QtGui.QColor.fromRgbF(*self._color), self
        )
        if chosen.isValid():
            self.set_color((chosen.redF(), chosen.greenF(), chosen.blueF()))

    def _update_swatch(self):
        """Paint the button with the current color."""
        r, g, b = (int(round(c * 255)) for c in self._color)
        self.setStyleSheet("background-color: rgb({}, {}, {});".format(r, g, b))


class HeightGrip(QtWidgets.QFrame):
    """Drag handle that sets the height of the widget above it.

    Put it under the target widget in a layout. Dragging it up or down
    gives the target a fixed height, clamped to ``minimum`` and
    ``maximum``. Implements the settings protocol of
    :class:`pyqt.SettingsMixin`, so the height can be remembered.
    """

    # emitted while dragging; heightCommitted once when the drag ends
    heightChanged = QtCore.Signal(int)
    heightCommitted = QtCore.Signal(int)

    def __init__(self, target, minimum=40, maximum=2000, parent=None):
        """Initialize the grip.

        Args:
            target (QtWidgets.QWidget): Widget whose height is set.
            minimum (int, optional): Smallest height, in pixels.
            maximum (int, optional): Largest height, in pixels.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(HeightGrip, self).__init__(parent)
        self._target = target
        self._minimum = minimum
        self._maximum = maximum
        self._press_y = None
        self._press_height = None
        self.setFixedHeight(pyqt.dpi_scale(6))
        self.setCursor(QtCore.Qt.SizeVerCursor)
        self.setToolTip("Drag to resize")
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)

    def set_target_height(self, height):
        """Set the target height, clamped to the range.

        Args:
            height (int): Height in pixels.
        """
        height = int(max(self._minimum, min(self._maximum, height)))
        target = self._target
        if target.minimumHeight() != height or target.maximumHeight() != height:
            target.setFixedHeight(height)
            self.heightChanged.emit(height)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press_y = event.globalPos().y()
            self._press_height = self._target.height()
        super(HeightGrip, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_y is not None:
            delta = event.globalPos().y() - self._press_y
            self.set_target_height(self._press_height + delta)
        super(HeightGrip, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._press_y is not None:
            self._press_y = None
            self.heightCommitted.emit(self._target.maximumHeight())
        super(HeightGrip, self).mouseReleaseEvent(event)

    def settings_value(self):
        """Return the target height for pyqt.SettingsMixin.

        Returns:
            int: Height in pixels.
        """
        return self._target.maximumHeight()

    def set_settings_value(self, value):
        """Set the target height from a stored setting.

        Args:
            value (object): Stored height, ignored when not a number.
        """
        try:
            self.set_target_height(int(float(value)))
        except (TypeError, ValueError):
            pass

    def settings_signal(self):
        """Return the signal emitted when a drag ends.

        Returns:
            QtCore.Signal: ``heightCommitted``.
        """
        return self.heightCommitted


class VectorSpinBox(QtWidgets.QWidget):
    """Row of labelled float spin boxes editing a vector value.

    Same interface as :class:`FloatSliderSpinBox`: ``value``,
    ``setValue``, ``isMixed``, ``setMixed``, ``valueChanged`` and
    ``valueCommitted``. Mixed components show "—"; when one component is
    edited, components still mixed are reported as None, so callers can
    leave them unchanged.
    """

    valueChanged = QtCore.Signal(object)
    valueCommitted = QtCore.Signal(object)

    MIXED_TEXT = "—"

    def __init__(
        self,
        labels="XYZ",
        minimum=-1.0e6,
        maximum=1.0e6,
        default=(0.0, 0.0, 0.0),
        decimals=3,
        parent=None,
    ):
        """Initialize the widget.

        Args:
            labels (str or list, optional): One label per component.
            minimum (float, optional): Minimum of every component.
            maximum (float, optional): Maximum of every component.
            default (tuple, optional): Initial value.
            decimals (int, optional): Spin box decimals.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(VectorSpinBox, self).__init__(parent)
        self._minimum = float(minimum)
        self._step = 10.0**-decimals
        self._mixed = [False] * len(labels)
        self.spin_boxes = []
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for index, label in enumerate(labels):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(decimals)
            spin.setRange(minimum, maximum)
            spin.setKeyboardTracking(False)
            spin.setPrefix("{} ".format(label))
            spin.valueChanged.connect(partial(self._on_changed, index))
            layout.addWidget(spin, 1)
            self.spin_boxes.append(spin)
        self.setValue(default)

    def value(self):
        """Return the value. Mixed components are None.

        Returns:
            tuple: The components.
        """
        return tuple(
            None if mixed else spin.value()
            for spin, mixed in zip(self.spin_boxes, self._mixed)
        )

    def setValue(self, value):
        """Set the value without emitting signals. Clears the mixed state.

        Args:
            value (tuple): The components.
        """
        self.setMixed(False)
        for spin, component in zip(self.spin_boxes, value):
            with pyqt.block_signals(spin):
                spin.setValue(component)

    def isMixed(self):
        """Return True when any component shows the mixed state.

        Returns:
            bool: The mixed state.
        """
        return any(self._mixed)

    def setMixed(self, mixed):
        """Show or clear the mixed state, without emitting signals.

        Args:
            mixed (bool or list): One flag for every component, or a list
                with one flag per component.
        """
        if isinstance(mixed, bool):
            mixed = [mixed] * len(self.spin_boxes)
        for index, (spin, flag) in enumerate(zip(self.spin_boxes, mixed)):
            if flag == self._mixed[index]:
                continue
            self._mixed[index] = flag
            with pyqt.block_signals(spin):
                if flag:
                    spin.setSpecialValueText(spin.prefix() + self.MIXED_TEXT)
                    spin.setMinimum(self._minimum - self._step)
                    spin.setValue(spin.minimum())
                else:
                    spin.setSpecialValueText("")
                    spin.setMinimum(self._minimum)

    def _on_changed(self, index, value):
        if self._mixed[index]:
            if value < self._minimum:
                return
            self._mixed[index] = False
            spin = self.spin_boxes[index]
            with pyqt.block_signals(spin):
                spin.setSpecialValueText("")
                spin.setMinimum(self._minimum)
                spin.setValue(value)
        self.valueChanged.emit(self.value())
        self.valueCommitted.emit(self.value())


class TriStateCheckBox(QtWidgets.QCheckBox):
    """Check box with a mixed state, for multi-selection editing.

    Same interface as :class:`FloatSliderSpinBox`: ``value``,
    ``setValue``, ``isMixed``, ``setMixed``, ``valueChanged`` and
    ``valueCommitted``. The mixed state shows as partially checked and a
    click always sets a plain checked or unchecked value.
    """

    valueChanged = QtCore.Signal(object)
    valueCommitted = QtCore.Signal(object)

    def __init__(self, text="", parent=None):
        """Initialize the check box.

        Args:
            text (str, optional): Label.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(TriStateCheckBox, self).__init__(text, parent)
        self.clicked.connect(self._on_clicked)

    def value(self):
        """Return the checked state.

        Returns:
            bool: The value.
        """
        return self.isChecked()

    def setValue(self, value):
        """Set the state without emitting signals. Clears the mixed state.

        Args:
            value (bool): The value.
        """
        with pyqt.block_signals(self):
            self.setTristate(False)
            self.setChecked(bool(value))

    def isMixed(self):
        """Return True when showing the mixed state.

        Returns:
            bool: The mixed state.
        """
        return self.checkState() == QtCore.Qt.PartiallyChecked

    def setMixed(self, mixed):
        """Show or clear the mixed state, without emitting signals.

        Args:
            mixed (bool): True to show the partially checked state.
        """
        if mixed:
            with pyqt.block_signals(self):
                self.setTristate(True)
                self.setCheckState(QtCore.Qt.PartiallyChecked)
        elif self.isMixed():
            self.setValue(True)

    def _on_clicked(self, *args):
        self.setTristate(False)
        self.valueChanged.emit(self.isChecked())
        self.valueCommitted.emit(self.isChecked())


class ThumbnailEditor(QtWidgets.QWidget):
    """Square thumbnail preview with viewport, region and clear buttons.

    The viewport button captures the active Maya viewport, the region
    button lets the user drag a rectangle anywhere on the screen
    (:mod:`mgear.core.screen_capture`). Images are cropped to a square.
    ``imageChanged`` is emitted with the new image, or None when cleared.
    """

    imageChanged = QtCore.Signal(object)

    def __init__(self, image=None, size=128, image_size=256, parent=None):
        """Initialize the editor.

        Args:
            image (QtGui.QImage, optional): Initial image.
            size (int, optional): Preview size, in pixels.
            image_size (int, optional): Size of the stored square image.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(ThumbnailEditor, self).__init__(parent)
        self._image = None
        self._size = size
        self._image_size = image_size
        self.preview = QtWidgets.QLabel()
        self.preview.setFixedSize(size, size)
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setStyleSheet(
            "background-color: rgb(40, 40, 40); color: rgb(150, 150, 150);"
        )
        self.viewport_btn = QtWidgets.QPushButton("Viewport")
        self.viewport_btn.setToolTip("Capture the active viewport")
        self.region_btn = QtWidgets.QPushButton("Capture Region...")
        self.region_btn.setToolTip("Drag a rectangle anywhere on the screen")
        self.clear_btn = QtWidgets.QPushButton("Clear")

        buttons = QtWidgets.QVBoxLayout()
        buttons.addWidget(self.viewport_btn)
        buttons.addWidget(self.region_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview)
        layout.addLayout(buttons)

        self.viewport_btn.clicked.connect(self.capture_viewport)
        self.region_btn.clicked.connect(self.capture_region)
        self.clear_btn.clicked.connect(self.clear)
        self.set_image(image)

    def image(self):
        """Return the image.

        Returns:
            QtGui.QImage: The square image, or None.
        """
        return self._image

    def set_image(self, image):
        """Set the image, cropped to a square.

        Args:
            image (QtGui.QImage): The image, or None to clear.
        """
        self._image = pyqt.square_crop_image(image, self._image_size)
        if self._image is None:
            self.preview.setPixmap(QtGui.QPixmap())
            self.preview.setText("No image")
        else:
            self.preview.setPixmap(
                QtGui.QPixmap.fromImage(self._image).scaled(
                    self._size,
                    self._size,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        self.imageChanged.emit(self._image)

    def clear(self):
        """Remove the image."""
        self.set_image(None)

    def capture_viewport(self):
        """Use the active viewport as image."""
        image = pyqt.capture_active_view_image()
        if image is None:
            cmds.warning("No active viewport to capture")
            return
        self.set_image(image)

    def capture_region(self):
        """Use a screen region as image."""
        from mgear.core import screen_capture

        image = screen_capture.capture_screen_region(hide_widgets=[self.window()])
        if image is not None:
            self.set_image(image)


class FloatSliderSpinBox(QtWidgets.QWidget):
    """Float spin box and slider kept in sync, with a mixed-value state.

    ``valueChanged`` is emitted while the value changes (including during
    a slider drag). ``valueCommitted`` is emitted once when an edit is
    finished: slider released, slider track clicked or spin box value
    entered. Use it to record a single undo step per edit.

    The slider covers ``minimum`` to ``soft_maximum``. Typing a larger
    value (up to ``maximum``) extends the slider range.

    The mixed state shows "—" in the spin box, for multi-selection
    editing when the edited objects have different values. Any edit
    clears it.
    """

    valueChanged = QtCore.Signal(float)
    valueCommitted = QtCore.Signal(float)
    sliderPressed = QtCore.Signal()

    SLIDER_STEPS = 1000
    MIXED_TEXT = "—"

    def __init__(
        self,
        label="",
        minimum=0.0,
        maximum=1.0,
        default=0.0,
        decimals=3,
        soft_maximum=None,
        parent=None,
    ):
        """Initialize the widget.

        Args:
            label (str, optional): Label shown on the left. No label when
                empty.
            minimum (float, optional): Minimum value.
            maximum (float, optional): Maximum value.
            default (float, optional): Initial value.
            decimals (int, optional): Spin box decimals.
            soft_maximum (float, optional): Initial slider maximum.
                Defaults to ``maximum``.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(FloatSliderSpinBox, self).__init__(parent)
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        soft_maximum = float(
            maximum if soft_maximum is None else min(soft_maximum, maximum)
        )
        self._slider_maximum = soft_maximum
        self._mixed = False
        self._step = 10.0**-decimals

        self.label = QtWidgets.QLabel(label)
        self.label.setVisible(bool(label))

        self.spin_box = QtWidgets.QDoubleSpinBox()
        self.spin_box.setDecimals(decimals)
        self.spin_box.setRange(self._minimum, self._maximum)
        self.spin_box.setSingleStep(
            max(self._step, (soft_maximum - self._minimum) / 100.0)
        )
        self.spin_box.setKeyboardTracking(False)
        self.spin_box.setMinimumWidth(pyqt.dpi_scale(60))

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, self.SLIDER_STEPS)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        layout.addWidget(self.spin_box)
        layout.addWidget(self.slider, 1)

        self._set_widgets(float(default))

        self.spin_box.valueChanged.connect(self._on_spin_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.sliderPressed.connect(self.sliderPressed.emit)
        self.slider.sliderReleased.connect(self._on_slider_released)

    # public -----------------------------------------------------------

    def value(self):
        """Return the current value.

        Returns:
            float: The value. Meaningless while the widget is mixed.
        """
        return self.spin_box.value()

    def setValue(self, value):
        """Set the value without emitting signals. Clears the mixed state.

        Args:
            value (float): New value, clamped to the range.
        """
        self.setMixed(False)
        self._set_widgets(float(value))

    def isMixed(self):
        """Return True while the widget shows the mixed state.

        Returns:
            bool: The mixed state.
        """
        return self._mixed

    def setMixed(self, mixed):
        """Show or clear the mixed-value state. Does not emit signals.

        Args:
            mixed (bool): True to show "—" in the spin box.
        """
        if mixed == self._mixed:
            return
        self._mixed = mixed
        with pyqt.block_signals(self.spin_box):
            if mixed:
                # the special value text is shown when value == minimum
                self.spin_box.setSpecialValueText(self.MIXED_TEXT)
                self.spin_box.setMinimum(self._minimum - self._step)
                self.spin_box.setValue(self.spin_box.minimum())
            else:
                self.spin_box.setSpecialValueText("")
                self.spin_box.setMinimum(self._minimum)

    def settings_value(self):
        """Return the value for pyqt.SettingsMixin.

        Returns:
            float: The value.
        """
        return self.value()

    def set_settings_value(self, value):
        """Set the value from a stored setting (pyqt.SettingsMixin).

        Args:
            value (object): Stored value, ignored when not a number.
        """
        try:
            self.setValue(float(value))
        except (TypeError, ValueError):
            pass

    def settings_signal(self):
        """Return the signal emitted when an edit is finished.

        Returns:
            QtCore.Signal: ``valueCommitted``.
        """
        return self.valueCommitted

    # internal ---------------------------------------------------------

    def _set_widgets(self, value):
        value = max(self._minimum, min(self._maximum, value))
        if value > self._slider_maximum:
            self._slider_maximum = value
        with pyqt.block_signals(self.spin_box):
            self.spin_box.setValue(value)
        with pyqt.block_signals(self.slider):
            self.slider.setValue(self._to_slider(value))

    def _to_slider(self, value):
        span = self._slider_maximum - self._minimum
        if span <= 0:
            return 0
        ratio = (value - self._minimum) / span
        return int(round(max(0.0, min(1.0, ratio)) * self.SLIDER_STEPS))

    def _from_slider(self, position):
        span = self._slider_maximum - self._minimum
        return self._minimum + span * position / float(self.SLIDER_STEPS)

    def _on_spin_changed(self, value):
        if self._mixed:
            if value < self._minimum:
                # still showing the mixed text
                return
            self.setMixed(False)
        self._set_widgets(value)
        self.valueChanged.emit(self.value())
        self.valueCommitted.emit(self.value())

    def _on_slider_changed(self, position):
        self.setMixed(False)
        value = round(self._from_slider(position), self.spin_box.decimals())
        with pyqt.block_signals(self.spin_box):
            self.spin_box.setValue(value)
        self.valueChanged.emit(self.value())
        if not self.slider.isSliderDown():
            # track click or keyboard: the edit is already finished
            self.valueCommitted.emit(self.value())

    def _on_slider_released(self):
        self.valueCommitted.emit(self.value())


class NodeListWidget(QtWidgets.QWidget):
    """List of Maya nodes with "Add Selected" and "Remove" buttons.

    Rows show short names (the full path is in the tooltip) while
    :meth:`nodes` returns full DAG paths, so nodes with the same short name
    under different parents stay distinct. ``nodesChanged`` is emitted
    when rows are added or removed.
    """

    nodesChanged = QtCore.Signal()

    def __init__(self, parent=None):
        """Initialize the widget.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(NodeListWidget, self).__init__(parent)
        self.list_widget = QtWidgets.QListWidget()
        self.add_button = QtWidgets.QPushButton("Add Selected")
        self.remove_button = QtWidgets.QPushButton("Remove")

        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setMinimumHeight(90)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list_widget)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self.add_selected)
        self.remove_button.clicked.connect(self.remove_selected)

    def nodes(self):
        """Return the listed nodes.

        Returns:
            list: Full DAG paths (or plain names for non-DAG nodes).
        """
        return [
            self.list_widget.item(i).data(QtCore.Qt.UserRole)
            for i in range(self.list_widget.count())
        ]

    def set_nodes(self, nodes):
        """Replace the list contents.

        Args:
            nodes (list): Node names or full DAG paths.
        """
        self.list_widget.clear()
        self._add(nodes or [])
        self.nodesChanged.emit()

    def settings_value(self):
        """Return the nodes for pyqt.SettingsMixin.

        Returns:
            list: Full DAG paths.
        """
        return self.nodes()

    def set_settings_value(self, value):
        """Set the nodes from a stored value (pyqt.SettingsMixin).

        Args:
            value (object): List of names, or a single name (QSettings
                returns a one-item list as a plain string).
        """
        if not value:
            value = []
        elif isinstance(value, str):
            value = [value]
        self.set_nodes([str(n) for n in value if n])

    def settings_signal(self):
        """Return the signal emitted when the nodes change.

        Returns:
            QtCore.Signal: ``nodesChanged``.
        """
        return self.nodesChanged

    def add_selected(self):
        """Add the selected Maya nodes, skipping ones already listed."""
        added = self._add(cmds.ls(selection=True, long=True) or [])
        if added:
            self.nodesChanged.emit()

    def remove_selected(self):
        """Remove the selected rows."""
        items = self.list_widget.selectedItems()
        for item in items:
            self.list_widget.takeItem(self.list_widget.row(item))
        if items:
            self.nodesChanged.emit()

    def _add(self, nodes):
        """Append nodes that are not listed yet.

        Args:
            nodes (list): Node names or full DAG paths.

        Returns:
            int: Number of rows added.
        """
        existing = set(self.nodes())
        added = 0
        for node in nodes:
            if node in existing:
                continue
            item = QtWidgets.QListWidgetItem(node.split("|")[-1])
            item.setData(QtCore.Qt.UserRole, node)
            item.setToolTip(node)
            self.list_widget.addItem(item)
            existing.add(node)
            added += 1
        return added


#############################################
# Recent files menu
#############################################


class RecentFilesMenu(QtWidgets.QMenu):
    """Menu listing recently used files, persisted in mGear user settings.

    Entries are most recent first, without duplicates, and capped at
    ``max_entries``. Picking an entry emits ``fileTriggered(path)``.

    Example:
        >>> menu = RecentFilesMenu("myTool_recent", parent=file_menu)
        >>> menu.fileTriggered.connect(self.load_file)
        >>> file_menu.addMenu(menu)
        >>> menu.add_file(path)  # after a successful load or save
    """

    fileTriggered = QtCore.Signal(str)

    def __init__(
        self,
        settings_key,
        title="Recent Files",
        max_entries=10,
        settings=None,
        parent=None,
    ):
        """Initialize the menu.

        Args:
            settings_key (str): Key used to store the list in the mGear
                user settings. Must be unique per tool.
            title (str, optional): Menu title.
            max_entries (int, optional): Maximum number of files kept.
            settings (QtCore.QSettings, optional): Settings object to use,
                e.g. a tool's ``SettingsMixin.settings``. Defaults to
                ``pyqt.get_user_settings()``.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(RecentFilesMenu, self).__init__(title, parent)
        self.settings_key = settings_key
        self.max_entries = max_entries
        self.settings = settings or pyqt.get_user_settings()
        self.rebuild()

    def files(self):
        """Return the stored recent files.

        Returns:
            list: File paths, most recent first.
        """
        raw = self.settings.value(self.settings_key, "")
        if not raw:
            return []
        try:
            paths = raw if isinstance(raw, list) else json.loads(raw)
        except (TypeError, ValueError):
            return []
        return [p for p in paths if p]

    def add_file(self, path):
        """Move or add a file to the top of the list.

        Args:
            path (str): File path.
        """
        path = os.path.abspath(path)
        paths = [p for p in self.files() if p != path]
        paths.insert(0, path)
        self._store(paths[: self.max_entries])

    def clear_files(self):
        """Remove every entry without asking."""
        self._store([])

    def rebuild(self):
        """Repopulate the menu from the stored list."""
        self.clear()
        paths = self.files()
        if not paths:
            empty = self.addAction("(empty)")
            empty.setEnabled(False)
        for path in paths:
            action = self.addAction(path)
            action.triggered.connect(
                lambda checked=False, p=path: self.fileTriggered.emit(p)
            )
        self.addSeparator()
        clear_action = self.addAction("Clear Recent")
        clear_action.setEnabled(bool(paths))
        clear_action.triggered.connect(self._confirm_clear)

    def _store(self, paths):
        """Persist the list and refresh the menu.

        Args:
            paths (list): File paths, most recent first.
        """
        self.settings.setValue(self.settings_key, json.dumps(paths))
        self.settings.sync()
        self.rebuild()

    def _confirm_clear(self):
        """Ask before clearing the list."""
        answer = QtWidgets.QMessageBox.question(
            self.parentWidget(),
            "Clear Recent",
            "Clear the list of recent files?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.clear_files()


##################
# Helper functions
##################


def create_button(
    size=17,
    text=None,
    icon=None,
    toggle_icon=None,
    icon_size=None,
    toolTip=None,
    width=None,
    setMax=True,
):
    """Create and configure a QPushButton

    Args:
        size (int, optional): Size of the button
        text (str, optional): Text of the button
        icon (str, optional): Icon name
        toggle_icon (str, optional): Toggle icon name. If exist will make
                                     the button checkable
        icon_size (int, optional): Icon size
        toolTip (str, optional): Buttom tool tip

    Returns:
        QPushButton: The reated button
    """
    button = QtWidgets.QPushButton()
    if not width:
        width = size
    button.setMinimumHeight(size)
    button.setMinimumWidth(width)
    if setMax:
        button.setMaximumHeight(size)
        button.setMaximumWidth(width)

    if toolTip:
        button.setToolTip(toolTip)

    if text:
        button.setText(text)

    if icon:
        if not icon_size:
            icon_size = size - 3
        button.setIcon(pyqt.get_icon(icon, icon_size))
        # button.setIconSize(QtCore.QSize(icon_size, icon_size))

    if toggle_icon:
        button.setCheckable(True)

        def changeIcon(
            button=button, icon=icon, toggle_icon=toggle_icon, size=icon_size
        ):
            if button.isChecked():
                button.setIcon(pyqt.get_icon(toggle_icon, size))
            else:
                button.setIcon(pyqt.get_icon(icon, size))
            # button.setIconSize(QtCore.QSize(icon_size, icon_size))

        button.clicked.connect(changeIcon)

    return button


def action_button(text, role="primary", tooltip=None, parent=None):
    """Create a main action button styled with a UI role.

    Args:
        text (str): Button text, Title Case verb + noun ("Build Rig").
        role (str, optional): ``"primary"``, ``"secondary"``, ``"danger"``,
            or None for a plain button of the same height.
        tooltip (str, optional): Button tooltip.
        parent (QtWidgets.QWidget, optional): Parent widget.

    Returns:
        QtWidgets.QPushButton: The button.
    """
    button = QtWidgets.QPushButton(text, parent)
    button.setAutoDefault(False)
    button.setMinimumHeight(ui_style.scaled(ui_style.BUTTON_HEIGHT_PRIMARY)[0])
    if role:
        ui_style.set_role(button, role)
    if tooltip:
        button.setToolTip(tooltip)
    return button


class ActionBar(QtWidgets.QWidget):
    """Row of main action buttons at the bottom of a tool window.

    Buttons share the width in the order added; add the primary action last
    so it sits on the right.

    Example:
        >>> bar = ActionBar()
        >>> bar.add_button("Cancel", role=None)
        >>> build_button = bar.add_button("Build", role="primary")
    """

    def __init__(self, parent=None):
        """Initialize the action bar.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(ActionBar, self).__init__(parent)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(*ui_style.scaled(*ui_style.SECTION_MARGINS))
        self.main_layout.setSpacing(ui_style.scaled(ui_style.S)[0])

    def add_button(self, text, role="primary", tooltip=None):
        """Add a button to the right end of the bar.

        Args:
            text (str): Button text.
            role (str, optional): Button role, or None for a plain button.
            tooltip (str, optional): Button tooltip.

        Returns:
            QtWidgets.QPushButton: The button.
        """
        button = action_button(text, role, tooltip, self)
        self.add_widget(button)
        return button

    def add_widget(self, widget):
        """Add any widget to the right end of the bar.

        Args:
            widget (QtWidgets.QWidget): The widget.
        """
        self.main_layout.addWidget(widget)


class StatusLine(QtWidgets.QLabel):
    """One-line status message at the bottom of a tool window.

    Example:
        >>> status = StatusLine()
        >>> status.set_message("Built 12 joints", "text_success")
    """

    def __init__(self, parent=None):
        """Initialize the status line.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(StatusLine, self).__init__(parent)
        self.setWordWrap(True)
        self.setContentsMargins(*ui_style.scaled(*ui_style.SECTION_MARGINS))
        ui_style.set_role(self, "text_hint")

    def set_message(self, text, role="text_hint"):
        """Show a message.

        Args:
            text (str): The message.
            role (str, optional): ``"text_hint"``, ``"text_success"``,
                ``"text_warning"`` or ``"text_error"``.
        """
        ui_style.set_role(self, role)
        self.setText(text)

    def clear(self):
        """Remove the message and go back to the hint role."""
        ui_style.set_role(self, "text_hint")
        super(StatusLine, self).clear()


#########################
# Widget Settings Manager
#########################


class WidgetSettingsManager(QtCore.QSettings):
    widget_map = {
        "QCheckBox": ("isChecked", "setChecked", bool, False),
        "QComboBox": ("currentIndex", "setCurrentIndex", int, 0),
        "QLineEdit": ("text", "setText", str, ""),
        "QListWidget": (None, None, str, ""),
    }

    def __init__(self, ui_name, parent=None):
        super(WidgetSettingsManager, self).__init__(parent)
        self.settings = QtCore.QSettings(
            QtCore.QSettings.IniFormat,
            QtCore.QSettings.UserScope,
            "mcsGear",
            ui_name,
        )

    def _get_listwidget_item_names(self, listwidget):
        items = [listwidget.item(i).text() for i in range(listwidget.count())]
        item_string = ",".join(items)
        return item_string

    def _add_listwidget_items(self, name, listwidget):
        value = self.settings.value(name, type=str)
        if not value or value == "0":
            return
        items = value.split(",")
        current_items = self._get_listwidget_item_names(listwidget)
        for item in items:
            if item not in current_items:
                listwidget.addItem(item)

    def save_ui_state(self, widget_dict):
        for name, widget in widget_dict.items():
            class_name = widget.__class__.__name__
            if class_name not in self.widget_map:
                continue
            if class_name == "QListWidget":
                value = self._get_listwidget_item_names(widget)
                self.settings.setValue(name, value)
                continue
            getter, _, _, _ = self.widget_map.get(class_name)
            if not getter:
                return
            get_function = getattr(widget, getter)
            value = get_function()
            if value is not None:
                self.settings.setValue(name, value)

    def load_ui_state(self, widget_dict, reset=False):
        for name, widget in widget_dict.items():
            class_name = widget.__class__.__name__
            if class_name not in self.widget_map:
                continue
            if class_name == "QListWidget":
                self._add_listwidget_items(name, widget)
                continue
            _, setter, dtype, default_value = self.widget_map.get(class_name)
            if not setter:
                return
            value = self.settings.value(name, type=dtype)
            if reset:
                value = default_value
            if value is not None:
                set_function = getattr(widget, setter)
                try:
                    set_function(value)
                except Exception as e:
                    print(e)


class FlowLayout(QtWidgets.QLayout):
    """Layout that arranges items left-to-right, wrapping to next row.

    Args:
        parent (QWidget, optional): Parent widget.
        margin (int, optional): Layout margin in pixels.
        spacing (int, optional): Spacing between items in pixels.
    """

    def __init__(self, parent=None, margin=-1, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        self._item_list = []
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)
        if spacing >= 0:
            self._spacing = spacing
        else:
            self._spacing = -1

    def __del__(self):
        while self._item_list:
            self.takeAt(0)

    def addItem(self, item):
        """Add item to layout."""
        self._item_list.append(item)

    def count(self):
        """Return item count."""
        return len(self._item_list)

    def itemAt(self, index):
        """Return item at index."""
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        """Remove and return item at index."""
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        """Return expanding directions."""
        return QtCore.Qt.Orientations()

    def hasHeightForWidth(self):
        """Layout height depends on width."""
        return True

    def heightForWidth(self, width):
        """Calculate height for given width."""
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        """Set layout geometry."""
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        """Return preferred size."""
        return self.minimumSize()

    def minimumSize(self):
        """Return minimum size."""
        size = QtCore.QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _do_layout(self, rect, test_only):
        """Arrange items, wrapping to new rows as needed.

        Args:
            rect (QRect): Available rectangle.
            test_only (bool): If True, only calculate height.

        Returns:
            int: Total height used.
        """
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(),
            -margins.right(), -margins.bottom(),
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing() if self._spacing < 0 else self._spacing

        for item in self._item_list:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + spacing
                next_x = x + item_size.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(
                    QtCore.QRect(QtCore.QPoint(x, y), item_size)
                )
            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + margins.bottom()
