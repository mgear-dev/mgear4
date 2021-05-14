
from functools import partial

import maya.cmds as mc

import mgear.core.pyqt as gqt
from mgear.synoptic import utils
QtGui, QtCore, QtWidgets, wrapInstance = gqt.qt_import()

# ==============================================================================
# Constants
# ==============================================================================
GEO_RENDER_NODE = "render_geoRoot"
COLOR_GREEN = "rgb(23, 158, 131)"
COLOR_RED = "rgb(155, 45, 34)"


# ==============================================================================
# Functions
# ==============================================================================
def safeSetAttr(node, attr="v", value=None):
    try:
        mc.setAttr("{}.{}".format(node, attr), value)
    except Exception:
        pass


def getHidden(nodes):
    """Oh the list of nodes provided, return non visible ones

    Args:
        nodes (list): list of nodes to query, strings

    Returns:
        list: of nodes that are hidden
    """
    hiddenNodes = []
    for node in nodes:
        if not mc.getAttr("{0}.v".format(node)):
            hiddenNodes.append(node)
    return hiddenNodes


def getVisible(nodes):
    """Oh the list of nodes provided, return visible ones

    Args:
        nodes (list): list of nodes to query, strings

    Returns:
        list: of nodes that are visible
    """
    visibleNodes = []
    for node in nodes:
        if mc.getAttr("{0}.v".format(node)):
            visibleNodes.append(node)
    return visibleNodes


def getMeshesFromHierarchy(node):
    """Get transforms with shapes, meshes

    Args:
        node (TYPE): Description

    Returns:
        TYPE: Description
    """
    meshNodes = []
    allChildren = mc.listRelatives(node, ad=True, type="transform")
    for mesh in allChildren:
        if mc.listRelatives(mesh, s=True):
            meshNodes.append(mesh)
    return meshNodes


def getBaseNames(nodes):
    """strip the nameSpace off of the list of provided nodes

    Args:
        nodes (list): of nodes with a namespace

    Returns:
        list: of nodes without namespaces
    """
    baseNodeNames = [utils.stripNamespace(x) for x in nodes]
    return baseNodeNames


def getMatching(token, toQuery):
    """use the token to search a list of strings, return all matching token

    Args:
        token (string): "l0"
        toQuery (list): of strings to check

    Returns:
        list: of matchings strings
    """
    matching = [q for q in toQuery
                if token.lower() in q.lower()]
    return matching


def getTokens(userInput):
    """splits up the userInput via commas, strips spaces

    Args:
        userInput (string): comma seperated search tokens, filters

    Returns:
        list: of all tokens that were seperated via comma
    """
    allTokens = userInput.replace(" ", "").split(',')
    return allTokens


class ToggleGeoVisibility(QtWidgets.QWidget):
    """widget for listing all controls under a namespace"""
    visibleColor = QtGui.QBrush()
    # green
    visibleColor.setColor('#179e83')
    hiddenColor = QtGui.QBrush()
    # red color
    hiddenColor.setColor('#9b2d22')
    connectedColor = QtGui.QBrush()
    # gray color
    connectedColor.setColor('#696969')

    def __init__(self, parent=None):
        super(ToggleGeoVisibility, self).__init__(parent)
        self.parent = parent
        self.model = None
        self.nameSpace = None
        self.modelControls = []
        self.gui()
        self.connectSignals()

    def showEvent(self, event):
        self.refresh()

    def colorItemBasedOnAttr(self, item):
        """Color the widgetitem based on the state of the visibility control

        Args:
            item (TYPE): qtlistwidgetitem
        """
        meshName = self.getNodeWithNameSpace(item.text())
        meshAttr = "{0}.v".format(meshName)
        if mc.listConnections(meshAttr):
            brush = self.connectedColor
            itemFont = item.font()
            itemFont.setItalic(True)
            item.setFont(itemFont)
        else:
            if mc.getAttr("{0}.v".format(meshName)):
                brush = self.visibleColor
            else:
                brush = self.hiddenColor
        item.setForeground(brush)

    def upateAllResultColors(self):
        """Queary every item, its respective mesh node and color
        """
        for row in range(self.resultWidget.count()):
            item = self.resultWidget.item(row)
            self.colorItemBasedOnAttr(item)

    def setInfomation(self):
        """set the model on the widget and refresh/update info

        Args:
            model (string): name of the model
        """
        # self.model = model
        self.model = utils.getModel(self).name()
        self.nameSpace = utils.getNamespace(utils.getModel(self))
        # self.refresh()

    def connectSignals(self):
        """connect widgets/signals to the functions
        """
        self.searchLineEdit.textChanged.connect(self.queryNames)
        visibleCmd = partial(self.toggleResultsDisplay, "visible")
        self.showVisibleButton.toggled.connect(visibleCmd)
        hiddenCmd = partial(self.toggleResultsDisplay, "hidden")
        self.showHiddenButton.toggled.connect(hiddenCmd)
        self.hideSelectedButton.clicked.connect(self.hideSelected)
        self.unHideSelectedButton.clicked.connect(self.unHideSelected)
        self.unHideAllButton.clicked.connect(self.unHideAll)
        self.selectButton.clicked.connect(self.specificSelection)

    def displayResults(self, resultsToDisplay):
        """clear and display the provided list

        Args:
            resultsToDisplay (list): of results to display
        """
        self.resultWidget.clear()
        self.resultWidget.addItems(sorted(set(resultsToDisplay)))

    def hideResults(self, resultsToDisplay):
        """clear and display the provided list

        Args:
            resultsToDisplay (list): of results to display
        """
        for row in range(self.resultWidget.count()):
            item = self.resultWidget.item(row)
            if item.text() in resultsToDisplay:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def getNodeWithNameSpace(self, node):
        """In the future this will need to change to allow for set name prefix

        Args:
            node (string): name of the node

        Returns:
            string: name of node with namespace
        """
        if self.nameSpace is not None and self.nameSpace.endswith(":"):
            ns = ""
        else:
            ns = "{0}:".format(self.nameSpace)
        return "{0}{1}".format(ns, node)

    def queryNames(self, userInput):
        """Take the userInput and query against all controls
        remove duplicates and sort

        Args:
            userInput (string): from UI
        """
        searchResults = []
        allTokens = getTokens(userInput)
        [searchResults.extend(getMatching(token, self.modelControls))
         for token in allTokens]
        self.hideResults(searchResults)

    def setNodeInfoForQuery(self, nodesToGet="all"):
        """Query the controls set in the scene from the scene.
        TODO: Open this up to select multiple areas for query
        """
        rootNode = str(self.property("geo_root"))
        meshNodes = []
        node = self.getNodeWithNameSpace(rootNode)
        if mc.objExists(node):
            meshNodes = getMeshesFromHierarchy(node)
        if nodesToGet == "all":
            pass
        elif nodesToGet == "hidden":
            meshNodes = getHidden(meshNodes)
        elif nodesToGet == "visible":
            meshNodes = getVisible(meshNodes)
        baseNodeNames = set(getBaseNames(meshNodes))
        self.modelControls = list(baseNodeNames)

    def selectAllResults(self):
        """Select all items in results widget
        """
        self.resultWidget.clearSelection()
        self.resultWidget.selectAll()

    def hideSelected(self, *args):
        """When something is selected on the results widget, select it in core

        Args:
            *args: unised signal information
        """
        itemsToColor = []
        for item in self.resultWidget.selectedItems():
            mesh = self.getNodeWithNameSpace(item.text())
            safeSetAttr(mesh, attr="v", value=False)
            itemsToColor.append(item)
        [self.colorItemBasedOnAttr(item) for item in itemsToColor]

    def unHideSelected(self, *args):
        """When something is selected on the results widget, select it in core

        Args:
            *args: unised signal information
        """
        itemsToColor = []
        for item in self.resultWidget.selectedItems():
            mesh = self.getNodeWithNameSpace(item.text())
            safeSetAttr(mesh, attr="v", value=True)
            itemsToColor.append(item)
        [self.colorItemBasedOnAttr(item) for item in itemsToColor]

    def unHideAll(self, *args):
        """When something is selected on the results widget, select it in core

        Args:
            *args: unised signal information
        """
        itemsToColor = []
        for row in range(self.resultWidget.count()):
            item = self.resultWidget.item(row)
            mesh = self.getNodeWithNameSpace(item.text())
            safeSetAttr(mesh, attr="v", value=True)
            itemsToColor.append(item)

        [self.colorItemBasedOnAttr(x) for x in itemsToColor]

    def specificSelection(self, *args):
        """When something is selected on the results widget, select it in core

        Args:
            *args: unised signal information
        """
        selectionList = []
        for item in self.resultWidget.selectedItems():
            selectionList.append(self.getNodeWithNameSpace(item.text()))
        mc.select(selectionList)

    def refresh(self):
        """refresh the ui
        """
        self.setInfomation()
        self.showVisibleButton.setChecked(False)
        self.showHiddenButton.setChecked(False)
        self.searchLineEdit.clear()
        self.resultWidget.clear()
        self.setNodeInfoForQuery()
        self.displayResults(self.modelControls)
        self.upateAllResultColors()

    def filterByVisibility(self, nodesToGet):
        """A refresh function specifically for changing what types of nodes
        to display, hidden or visible

        Args:
            nodesToGet (TYPE): Description
        """
        self.searchLineEdit.clear()
        self.resultWidget.clear()
        self.setNodeInfoForQuery(nodesToGet=nodesToGet)
        self.displayResults(self.modelControls)
        self.upateAllResultColors()

    def toggleResultsDisplay(self, nodesToGet, toggled):
        """Mutually exclusive checked buttons

        Args:
            nodesToGet (TYPE): Description
            toggled (TYPE): Description
        """
        if nodesToGet == "visible" and toggled:
            self.showHiddenButton.setChecked(False)
        elif nodesToGet == "hidden" and toggled:
            self.showVisibleButton.setChecked(False)
        elif not self.showHiddenButton.isChecked() and \
                not self.showVisibleButton.isChecked():
            nodesToGet = "all"
        self.filterByVisibility(nodesToGet)

    def gui(self):
        """set the widget layout and content
        """
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.setLayout(self.mainLayout)
        #  -------------------------------------------------------------------
        self.searchLineEdit = QtWidgets.QLineEdit()
        self.searchLineEdit.setPlaceholderText("Filter via ',' seperated...")
        self.mainLayout.addWidget(self.searchLineEdit)
        #  -------------------------------------------------------------------
        bodyLayout = QtWidgets.QHBoxLayout()
        self.resultWidget = QtWidgets.QListWidget()
        self.resultWidget.setSpacing(4)
        self.resultWidget.setAlternatingRowColors(True)
        selMode = QtWidgets.QAbstractItemView.ExtendedSelection
        self.resultWidget.setSelectionMode(selMode)

        optionsLayout = QtWidgets.QVBoxLayout()
        filterLayout = QtWidgets.QHBoxLayout()
        self.showVisibleButton = QtWidgets.QPushButton("Visible")
        self.showHiddenButton = QtWidgets.QPushButton("hidden")
        self.showHiddenButton.setCheckable(True)
        self.showVisibleButton.setCheckable(True)
        filterLayout.addWidget(self.showVisibleButton)
        filterLayout.addWidget(self.showHiddenButton)
        filterLayout.setSpacing(0)
        self.hideSelectedButton = QtWidgets.QPushButton('Hide selected')
        redColor = "background-color: {}".format(COLOR_RED)
        self.hideSelectedButton.setStyleSheet(redColor)
        self.unHideSelectedButton = QtWidgets.QPushButton('Unhide selected')
        greenColor = "background-color: {}".format(COLOR_GREEN)
        self.unHideSelectedButton.setStyleSheet(greenColor)
        self.unHideAllButton = QtWidgets.QPushButton('Unhide ALL')
        self.selectButton = QtWidgets.QPushButton('Select highlighted')
        #  -------------------------------------------------------------------
        optionsLayout.addLayout(filterLayout)
        optionsLayout.addWidget(self.hideSelectedButton)
        optionsLayout.addWidget(self.unHideSelectedButton)
        optionsLayout.addWidget(self.unHideAllButton)
        optionsLayout.addWidget(self.selectButton)
        bodyLayout.addWidget(self.resultWidget)
        bodyLayout.addLayout(optionsLayout)
        self.mainLayout.addLayout(bodyLayout)
