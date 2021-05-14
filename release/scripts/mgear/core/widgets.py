"""mGear Qt custom widgets"""

from mgear.vendor.Qt import QtCore, QtWidgets, QtGui
import maya.OpenMaya as api


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
            rows_to_move = [[QtWidgets.QTableWidgetItem(
                self.item(row_index, column_index))
                for column_index in range(self.columnCount())]
                for row_index in rows]

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
                    self.item(drop_row + row_index,
                              column_index).setSelected(True)

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()

        return index.row() + 1 if self.is_below(event.pos(),
                                                index) else index.row()

    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        return rect.contains(pos, True) \
            and not (int(self.model().flags(index))
                     & QtCore.Qt.ItemIsDropEnabled) \
            and pos.y() >= rect.center().y()

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

        if (event.source() == self
            and event.possibleActions() & QtCore.Qt.MoveAction
                and dropAction == QtCore.Qt.MoveAction):
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
            if (not index.isValid()
                    or not self.visualRect(index).contains(event.pos())):
                index = self.rootIndex()

        if self.model().supportedDropActions() & event.dropAction():
            if index != self.rootIndex():
                dropIndicatorPosition = self.position(event.pos(),
                                                      self.visualRect(index),
                                                      index)
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

        if (r == QtWidgets.QAbstractItemView.OnItem
                and not (self.model().flags(index)
                         & QtCore.Qt.ItemIsDropEnabled)):
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
            x, y, x_rect, y_rect, api.MGlobal.kReplaceList)
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
        mimeData.setText('%d,%d' % (event.x(), event.y()))

        drag = QtGui.QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos())
        dropAction = drag.start(QtCore.Qt.MoveAction)
        if not dropAction == QtCore.Qt.MoveAction:
            pos = QtGui.QCursor.pos()
            widget = QtWidgets.QApplication.widgetAt(pos)
            if self.ignore_self and (
                    widget is self
                    or widget.objectName() == "qt_scrollarea_viewport"):
                return
            relpos = widget.mapFromGlobal(pos)
            # need to invert Y axis
            invY = widget.frameSize().height() - relpos.y()
            sel = selectFromScreenApi(relpos.x() - self.exp,
                                      invY - self.exp,
                                      relpos.x() + self.exp,
                                      invY + self.exp)

            self.doAction(sel)

    def setAction(self, action):
        self.theAction = action

    def doAction(self, sel):
        self.theAction(sel)
