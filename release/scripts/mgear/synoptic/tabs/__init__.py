# python
import traceback

# dcc
import pymel.core as pm

# mgear
import mgear
from mgear.vendor.Qt import QtCore, QtWidgets, QtGui
from mgear.core import callbackManager

from .. import widgets, utils


##################################################
# SYNOPTIC TAB WIDGET
##################################################


class MainSynopticTab(QtWidgets.QDialog):
    """
    Base class of synoptic tab widget

    """

    description = "base calss of synoptic tab"
    name = ""
    bgPath = None

    buttons = []
    default_buttons = [
        {"name": "selAll", "mouseTracking": True},
        {"name": "keyAll"},
        {"name": "keySel"},
        {"name": "resetAll"},
        {"name": "resetSel"}
    ]

    # ============================================
    # INIT
    def __init__(self, klass, parent=None):
        # type: (MainSynopticTab, QtWidgets.QWidget) -> None

        print("Loading synoptic tab of {0}".format(self.name))

        super(MainSynopticTab, self).__init__(parent)

        klass.setupUi(self)
        klass.setBackground()
        klass.connectSignals()
        klass.connectMaya()
        self._buttonGeometry = {}  # for cachinig

        # This is necessary for not to be zombie job on close.
        # Qt does not actually destroy the object by just pressing
        # close button by default.
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

    def setBackground(self):
        # type: () -> None

        # Retarget background Image to absolute path
        if self.bgPath is not None:
            self.img_background.setPixmap(QtGui.QPixmap(self.bgPath))

    def connectSignals(self):
        # type: () -> None

        def _conn(entry):
            name = entry.get("name")
            buttonName = "b_{0}".format(name)
            button = getattr(self, buttonName, None)

            clickEventName = "{0}_clicked".format(name)
            clickEvent = getattr(self, clickEventName, None)

            if not button or not clickEvent:
                return  # TODO

            button.clicked.connect(clickEvent)
            if entry.get("mouseTracking", False):
                button.setMouseTracking(True)

        # this is equivalent to below code commented out
        for entry in self.default_buttons + self.buttons:
            _conn(entry)

    def connectMaya(self):
        # type: () -> None
        # script job callback
        # ptr = long(QtCompat.getCppPointer(self)[0])
        # ptr = long(QtCompat.getCppPointer(self))
        # ptr = QtCompat.getCppPointer(self)

        self.cbManager = callbackManager.CallbackManager()

    def selectChanged(self, *args):
        # wrap to catch exception guaranteeing core does not stop at this
        try:
            self.__selectChanged(*args)

        except Exception as e:
            mes = traceback.format_exc()
            mes = "error has occur in scriptJob " \
                  "SelectionChanged\n{0}".format(mes)

            mes = "{0}\n{1}".format(mes, e)
            mgear.log(mes, mgear.sev_error)
            self.cbManager.removeAllManagedCB()
            try:
                self.close()
            except RuntimeError:
                pass

    def __selectChanged(self, *args):

        sels = []
        [sels.append(x.name()) for x in pm.ls(sl=True)]

        oModel = utils.getModel(self)
        if not oModel:
            mes = "model not found for synoptic {}".format(self.name)
            mgear.log(mes, mgear.sev_info)

            # self.close()

            syn_widget = utils.getSynopticWidget(self)
            syn_widget.updateModelList()

            return

        nameSpace = utils.getNamespace(oModel.name())

        selButtons = self.findChildren(widgets.SelectButton)
        selButtonsStyled = self.findChildren(widgets.SelectButtonStyleSheet)

        buttons = []
        buttons.extend(selButtons)
        buttons.extend(selButtonsStyled)

        for selB in buttons:
            obj = str(selB.property("object")).split(",")
            if len(obj) == 1:
                if nameSpace:
                    checkName = ":".join([nameSpace, obj[0]])
                else:
                    checkName = obj[0]

                if checkName in sels:
                    selB.paintSelected(True)
                else:
                    selB.paintSelected(False)

    def _getButtonAbsoluteGeometry(self, button):
        # type: (widgets.SelectButton) -> QtCore.QSize

        if button in self._buttonGeometry.keys():
            return self._buttonGeometry[button]

        geo = button.geometry()
        point = button.mapTo(self, geo.topLeft())
        point -= geo.topLeft()
        geo = QtCore.QRect(point, geo.size())

        self._buttonGeometry[button] = geo

        return geo

    def mousePressEvent_(self, event):
        # type: (QtGui.QMouseEvent) -> None

        self.origin = event.pos()
        QtWidgets.QWidget.mousePressEvent(self, event)

    def mouseMoveEvent_(self, event):
        # type: (QtGui.QMouseEvent) -> None

        QtWidgets.QWidget.mouseMoveEvent(self, event)

    def mouseReleaseEvent_(self, event):
        # type: (QtGui.QMouseEvent) -> None

        if not self.origin:
            self.origin = event.pos()

        selected = []
        rect = QtCore.QRect(self.origin, event.pos()).normalized()

        selButtons = self.findChildren(widgets.SelectButton)
        selButtonsStyled = self.findChildren(widgets.SelectButtonStyleSheet)

        buttons = []
        buttons.extend(selButtons)
        buttons.extend(selButtonsStyled)

        for child in buttons:
            # if rect.intersects(child.geometry()):
            if rect.intersects(self._getButtonAbsoluteGeometry(child)):
                selected.append(child)

        if selected:
            firstLoop = True
            with pm.UndoChunk():
                for wi in selected:
                    wi.rectangleSelection(event, firstLoop)
                    firstLoop = False

        else:
            if event.modifiers() == QtCore.Qt.NoModifier:
                pm.select(cl=True)
                pm.displayInfo("Clear selection")

        self.origin = None
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    # ============================================
    # BUTTONS
    def selAll_clicked(self):
        # type: () -> None
        model = utils.getModel(self)
        utils.selAll(model)

    def resetAll_clicked(self):
        # type: () -> None
        print "resetAll"

    def resetSel_clicked(self):
        # type: () -> None
        print "resetSel"

    def keyAll_clicked(self):
        # type: () -> None
        model = utils.getModel(self)
        utils.keyAll(model)

    def keySel_clicked(self):
        # type: () -> None
        utils.keySel()
