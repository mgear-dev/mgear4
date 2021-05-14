import os

import pymel.core as pm

from maya.app.general.mayaMixin import MayaQDockWidget
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

import mgear
from mgear.core import pyqt
from mgear.vendor.Qt import QtGui, QtCore, QtWidgets
import mgear.core.utils


SYNOPTIC_WIDGET_NAME = "synoptic_view"
SYNOPTIC_ENV_KEY = "MGEAR_SYNOPTIC_PATH"

SYNOPTIC_DIRECTORIES = mgear.core.utils.gatherCustomModuleDirectories(
    SYNOPTIC_ENV_KEY,
    os.path.join(os.path.dirname(__file__), "tabs"))


##################################################
# OPEN
##################################################
def open(*args):
    # open the synoptic dialog, without clean old instances
    pyqt.showDialog(Synoptic, False)


def importTab(tabName):
    """Import Synoptic Tab

    Args:
        tabName (Str): Synoptic tab name

    Returns:
        module: Synoptic tab module
    """
    import mgear.synoptic as syn
    dirs = syn.SYNOPTIC_DIRECTORIES
    defFmt = "mgear.synoptic.tabs.{}"
    customFmt = "{0}"

    module = mgear.core.utils.importFromStandardOrCustomDirectories(
        dirs, defFmt, customFmt, tabName)
    return module


##################################################
# SYNOPTIC
##################################################
class Synoptic(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    """Synoptic Main class"""

    default_height = 790
    default_width = 325
    margin = 15 * 2

    def __init__(self, parent=None):
        self.toolName = SYNOPTIC_WIDGET_NAME
        # Delete old instances of the componet settings window.
        pyqt.deleteInstances(self, MayaQDockWidget)
        super(Synoptic, self).__init__(parent)
        self.create_widgets()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

    def closeEvent(self, evnt):
        """oon close, kill all callbacks

        Args:
            evnt (Qt.QEvent): Close event called
        """

        # self.cbManager.removeAllManagedCB()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, SynopticTabWrapper):
                synTab, resultBool = tab.searchMainSynopticTab()
                if resultBool and hasattr(synTab, "cbManager"):
                    synTab.cbManager.removeAllManagedCB()
            tab.close()
        self.tabs.clear()
        super(Synoptic, self).closeEvent(evnt)

    def create_widgets(self):
        self.setupUi()

        # Connect Signal
        self.refresh_button.clicked.connect(self.updateModelList)
        self.model_list.currentIndexChanged.connect(self.updateTabs)

        # Initialise
        self.updateModelList()

    def setupUi(self):
        # Widgets
        self.setObjectName(SYNOPTIC_WIDGET_NAME)
        self.resize(560, 775)

        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setMinimumSize(QtCore.QSize(0, 0))

        self.gridLayout_2 = QtWidgets.QGridLayout(self)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_2.setObjectName("gridLayout_2")

        self.mainContainer = QtWidgets.QGroupBox(self)

        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)

        sizePolicy.setHeightForWidth(
            self.mainContainer.sizePolicy().hasHeightForWidth())

        self.mainContainer.setSizePolicy(sizePolicy)
        self.mainContainer.setMinimumSize(QtCore.QSize(0, 0))
        self.mainContainer.setObjectName("mainContainer")

        self.gridLayout_3 = QtWidgets.QGridLayout(self.mainContainer)
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_3.setObjectName("gridLayout_3")

        # header boxies
        self.hbox = QtWidgets.QHBoxLayout()
        self.hbox.setContentsMargins(5, 5, 5, 5)
        self.hbox.setObjectName("hbox")

        self.model_list = QtWidgets.QComboBox(self.mainContainer)
        self.model_list.setObjectName("model_list")
        self.model_list.setMinimumSize(QtCore.QSize(0, 23))

        self.refresh_button = QtWidgets.QPushButton(self.mainContainer)
        self.refresh_button.setObjectName("refresh_button")
        self.refresh_button.setText("Refresh")

        self.hbox.addWidget(self.model_list)
        self.hbox.addWidget(self.refresh_button)
        self.gridLayout_3.addLayout(self.hbox, 0, 0, 1, 1)

        # synoptic main area
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.scrollArea = QtWidgets.QScrollArea(self.mainContainer)

        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(
            self.scrollArea.sizePolicy().hasHeightForWidth())

        self.scrollArea.setSizePolicy(sizePolicy)
        self.scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.scrollArea.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)

        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setAlignment(QtCore.Qt.AlignCenter)
        self.scrollArea.setObjectName("scrollArea")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setSizePolicy(sizePolicy)
        self.tabs.setObjectName("tabs")

        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(
            self.tabs.sizePolicy().hasHeightForWidth())

        self.tabs.setSizePolicy(sizePolicy)
        self.tabs.setObjectName("synoptic_tab")
        self.scrollArea.setWidget(self.tabs)

        self.gridLayout.addWidget(self.scrollArea, 0, 0, 1, 1)
        self.gridLayout_3.addLayout(self.gridLayout, 2, 0, 1, 1)
        self.gridLayout_2.addWidget(self.mainContainer, 0, 0, 1, 1)

    # Singal Methods =============================
    def updateModelList(self):
        # avoiding unnecessary firing currentIndexChanged event before
        # finish to model_list
        try:
            self.model_list.currentIndexChanged.disconnect()
        except RuntimeError:
            pass

        rig_models = [item for item in pm.ls(transforms=True)
                      if item.hasAttr("is_rig")]

        self.model_list.clear()
        for item in rig_models:
            self.model_list.addItem(item.name(), item.name())

        # restore event and update tabs for reflecting self.model_list
        self.model_list.currentIndexChanged.connect(self.updateTabs)
        self.updateTabs()

    def updateTabs(self):

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, SynopticTabWrapper):
                synTab, resultBool = tab.searchMainSynopticTab()
                if resultBool and hasattr(synTab, "cbManager"):
                    synTab.cbManager.removeAllManagedCB()
            tab.close()
        self.tabs.clear()

        currentModelName = self.model_list.currentText()
        currentModels = pm.ls(currentModelName)
        if not currentModels:
            return

        tab_names = currentModels[0].getAttr("synoptic").split(",")

        max_h = 0
        max_w = 0
        for i, tab_name in enumerate(tab_names):
            try:
                if tab_name:
                    # instantiate SynopticTab widget
                    module = importTab(tab_name)
                    synoptic_tab = getattr(module, "SynopticTab")()

                    # set minimum size for auto fit (stretch) scroll area
                    if synoptic_tab.minimumHeight() == 0:
                        synoptic_tab.setMinimumHeight(synoptic_tab.height())
                    if synoptic_tab.minimumWidth() == 0:
                        synoptic_tab.setMinimumWidth(synoptic_tab.width())

                    # store tab size for set container size later
                    h = synoptic_tab.minimumHeight()
                    w = synoptic_tab.minimumWidth()

                    max_h = h if max_h < h else max_h
                    max_w = w if max_w < w else max_w

                    tab = self.wrapTabContents(synoptic_tab)
                    self.tabs.insertTab(i, tab, tab_name)

                else:
                    mes = "No synoptic tabs for %s" % \
                          self.model_list.currentText()

                    pm.displayWarning(mes)

            except Exception as e:
                import traceback
                traceback.print_exc()

                mes = "Synoptic tab: %s Loading fail {0}\n{1}".format(
                    tab_name, e)

                pm.displayError(mes)

        max_h = self.default_height if max_h == 0 else max_h
        max_w = self.default_width if max_w == 0 else max_w
        header_space = 45
        self.resize(max_w + self.margin, max_h + self.margin + header_space)

    def wrapTabContents(self, synoptic_tab):
        # type: (SynopticTab) -> QtWidgets.QWidget

        # horizontal layout:
        #     spacer >>  SynopticTab << spacer

        wrapperWidget = SynopticTabWrapper()
        wrapperWidget.setGeometry(QtCore.QRect(0, 0, 10, 10))
        wrapperWidget.setObjectName("wrapperWidget")

        horizontalLayout = QtWidgets.QHBoxLayout(wrapperWidget)
        horizontalLayout.setContentsMargins(0, 0, 0, 0)
        horizontalLayout.setObjectName("horizontalLayout")

        spacer_left = QtWidgets.QSpacerItem(0,
                                            0,
                                            QtWidgets.QSizePolicy.Expanding,
                                            QtWidgets.QSizePolicy.Minimum)

        spacer_right = QtWidgets.QSpacerItem(0,
                                             0,
                                             QtWidgets.QSizePolicy.Expanding,
                                             QtWidgets.QSizePolicy.Minimum)

        wrapperWidget.setSpacerLeft(spacer_left)

        horizontalLayout.addItem(spacer_left)
        horizontalLayout.addWidget(synoptic_tab)
        horizontalLayout.addItem(spacer_right)

        horizontalLayout.setStretch(0, 1)
        horizontalLayout.setStretch(1, 0)
        horizontalLayout.setStretch(2, 1)

        return wrapperWidget


class SynopticTabWrapper(QtWidgets.QWidget):
    """Class for handling mouse rubberband Selection

    Class for handling mouse rubberband within spacer and synoptic tab that
    is children of.
    """

    def __init__(self, *args, **kwargs):
        # type: () -> None

        super(SynopticTabWrapper, self).__init__(*args, **kwargs)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.rubberband = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Rectangle, self)

        self.offset = QtCore.QPoint()

    def setSpacerLeft(self, spacer):
        # type: (QtWidgets.QSpacerItem) -> None

        # QSpacerItem can't be traversed from its parent widget
        self.spacer = spacer

    # ------------------------------------------------------------------------
    # utility for mouse event
    # ------------------------------------------------------------------------
    def searchMainSynopticTab(self):
        # type: () -> (MainSynopticTab, bool)

        # avoiding cyclic import, declaration here not top of code
        from mgear.synoptic.tabs import MainSynopticTab
        for kid in self.children():
            if isinstance(kid, MainSynopticTab):
                return kid, True

            if "SynopticTab" in str(type(kid)):
                return kid, False

        else:
            mes = "synoptic tab not found"
            mgear.log(mes, mgear.sev_warning)
            return None, False

    def calculateOffset(self):
        # type: () -> QtCore.QPoint

        w = self.spacer.geometry().width()
        return QtCore.QPoint(w * -1, 0)

    def offsetEvent(self, event):
        # type: (QtGui.QMouseEvent) -> QtGui.QMouseEvent

        offsetev = QtGui.QMouseEvent(
            event.type(),
            event.pos() + self.offset,
            event.globalPos(),
            event.button(),
            event.buttons(),
            event.modifiers()
        )

        return offsetev

    # ------------------------------------------------------------------------
    # mouse events
    # ------------------------------------------------------------------------
    def mousePressEvent(self, event):
        # type: (QtGui.QMouseEvent) -> None

        self.syn_w, self.syn_wid_is_mainsyntab = self.searchMainSynopticTab()
        self.offset = self.calculateOffset()
        self.origin = event.pos()

        self.rubberband.setGeometry(QtCore.QRect(self.origin, QtCore.QSize()))
        self.rubberband.show()

        if self.syn_wid_is_mainsyntab:
            self.syn_w.mousePressEvent_(self.offsetEvent(event))
        else:
            self.syn_w.mousePressEvent(self.offsetEvent(event))

    def mouseMoveEvent(self, event):
        # type: (QtGui.QMouseEvent) -> None
        self.syn_w, self.syn_wid_is_mainsyntab = self.searchMainSynopticTab()

        if self.rubberband.isVisible():

            self.rubberband.setGeometry(
                QtCore.QRect(self.origin, event.pos()).normalized())

        if self.syn_wid_is_mainsyntab:
            self.syn_w.mouseMoveEvent_(self.offsetEvent(event))
        else:
            self.syn_w.mouseMoveEvent(self.offsetEvent(event))

    def mouseReleaseEvent(self, event):
        # type: (QtGui.QMouseEvent) -> None

        if self.rubberband.isVisible():
            self.rubberband.hide()

            if self.syn_wid_is_mainsyntab:
                self.syn_w.mouseReleaseEvent_(self.offsetEvent(event))
            else:
                self.syn_w.mouseReleaseEvent(self.offsetEvent(event))
