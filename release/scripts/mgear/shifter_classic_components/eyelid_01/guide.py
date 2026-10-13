"""Guide Eyelid 01 module"""

import os
from functools import partial

from maya import cmds

import mgear
from mgear.shifter.component import guide
from mgear.core import config_io
from mgear.core import meshNavigation
from mgear.core import pyqt
from mgear.core import settings_form
from mgear.core import settings_schema
from mgear.core import transform
from mgear.core.facial import eyelid_schema
from mgear.core.facial import eyelid_solver

from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

# guide info
AUTHOR = "Miquel Campos"
URL = "www.mcsgear.com"
EMAIL = ""
VERSION = [1, 0, 0]
TYPE = "eyelid_01"
NAME = "eyelid"
DESCRIPTION = (
    "Eyelid rig from an eyelid loop (Eye Rigger 3.0). The root is the eye "
    "center, root to aim is the eye direction and the aim depth in front of "
    "the eyelid is the control offset."
)

# settings the guide locators or the connector decide
GUIDE_DECIDED = ("trackingSource", "offset", "sideRange")

# settings holding mesh component indices, mirrored with the guide
INDEX_KEYS = ("edgeLoop", "vertexLoop", "intCorner", "extCorner")


def eyelid_settings(values, follow_eye=False):
    """Get complete eyelid settings from the guide values.

    Args:
        values (dict): Guide settings.
        follow_eye (bool, optional): The eyelids follow a parent eye
            component instead of their own aim control.

    Returns:
        dict: Coerced eyelid settings.
    """
    settings = settings_schema.defaults(eyelid_schema.SCHEMA)
    for key in settings:
        if key in values:
            settings[key] = values[key]
    settings["trackingSource"] = eyelid_schema.TRACKING_SOURCES.index(
        "external" if follow_eye else "own"
    )
    return settings_schema.coerce(settings, eyelid_schema.SCHEMA)


def solve(values, positions, side, follow_eye=False):
    """Solve the eyelid geometry of a guide.

    Args:
        values (dict): Guide settings.
        positions (dict): Guide locator positions, with "root" and "aim".
        side (str): Component side.
        follow_eye (bool, optional): See :func:`eyelid_settings`.

    Returns:
        tuple: (eyelid settings, EyelidGeometry)

    Raises:
        ValueError: If the guide doesn't describe a valid eyelid.
    """
    settings = eyelid_settings(values, follow_eye)
    geometry = eyelid_solver.solve(
        settings,
        eye_center=tuple(positions["root"]),
        aim=tuple(positions["aim"]),
        side=side,
    )
    return settings, geometry


def guide_schema():
    """Get the eyelid settings stored on the guide.

    Returns:
        list: Shared eyelid schema params the locators don't decide.
    """
    return [
        param
        for param in eyelid_schema.SCHEMA
        if param.scope == "shared" and param.key not in GUIDE_DECIDED
    ]


##########################################################
# CLASS
##########################################################


class Guide(guide.ComponentGuide):
    """Component Guide Class"""

    compType = TYPE
    compName = NAME
    description = DESCRIPTION

    author = AUTHOR
    url = URL
    email = EMAIL
    version = VERSION

    # named after the eye components: drawn under one, it is picked
    connectors = ["eye_01", "MCS_eye_01"]

    def postInit(self):
        """Initialize the position for the guide"""
        self.save_transform = ["root", "aim"]
        # eyelid geometry solved by validate, reused by the build
        self.geometry = None

    def addObjects(self):
        """Add the Guide Root and the aim locator"""
        self.root = self.addRoot()
        position = transform.getOffsetPosition(self.root, [0, 0, 1])
        self.aim = self.addLoc("aim", self.root, position)
        self.dispcrv = self.addDispCurve("crv", [self.root, self.aim])

    def addParameters(self):
        """Add the configurations settings"""
        for param in guide_schema():
            if param.value_type == "enum":
                self.addEnumParam(param.key, list(param.choices), param.default)
            else:
                self.addParam(
                    param.key,
                    param.value_type,
                    param.default,
                    param.minimum,
                    param.maximum,
                )
        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None
        )

    def validate(self):
        """Check the eyelid can be solved from the mesh and the guide.

        Returns:
            list: Problem messages, empty when the eyelid can build.
        """
        try:
            self.geometry = solve(self.values, self.pos, self.values["comp_side"])[1]
        except ValueError as error:
            self.geometry = None
            return ["{}. Check the {} component settings".format(error, TYPE)]
        return []

    def symmetrize(self):
        """Mirror the guide, and the eyelid loop and corners on the mesh.

        Returns:
            bool: False for a center guide.
        """
        if not super(Guide, self).symmetrize():
            return False
        for key in INDEX_KEYS:
            value = self.values[key]
            if not value:
                continue
            mesh = meshNavigation.parse_component_string(value)[0]
            if not cmds.objExists(mesh):
                mgear.log(
                    "{}: can't mirror {}, the mesh {} doesn't exist".format(
                        self.fullName, key, mesh
                    ),
                    mgear.sev_warning,
                )
                continue
            mirrored, missing = meshNavigation.mirror_component_string(value)
            if missing:
                mgear.log(
                    "{}: {} has no mirror for indices {}, kept as it is".format(
                        self.fullName, key, missing
                    ),
                    mgear.sev_warning,
                )
                continue
            self.setParamDefValue(key, mirrored)
        return True


##########################################################
# Setting Page
##########################################################


class settingsTab(QtWidgets.QWidget):
    """The eyelid settings, generated from the eyelid schema."""

    def __init__(self, parent=None):
        super(settingsTab, self).__init__(parent)
        keys = set(param.key for param in guide_schema())
        groups = []
        for title, group_keys in eyelid_schema.FORM_GROUPS:
            group_keys = [key for key in group_keys if key in keys]
            if group_keys:
                groups.append((title, group_keys))
        self.form = settings_form.SettingsForm(guide_schema(), groups)
        self.form.set_visibility_rule(
            eyelid_schema.row_visibility, eyelid_schema.ROW_KEYS
        )
        self.snap_button = QtWidgets.QPushButton("Snap Root to Eyeball")
        self.import_button = QtWidgets.QPushButton("Import Config")
        self.export_button = QtWidgets.QPushButton("Export Config")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.export_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.snap_button)
        layout.addWidget(scroll)
        layout.addLayout(buttons)


class componentSettings(MayaQWidgetDockableMixin, guide.componentMainSettings):
    """Create the component setting window"""

    def __init__(self, parent=None):
        self.toolName = TYPE
        # Delete old instances of the componet settings window.
        pyqt.deleteInstances(self, MayaQDockWidget)

        super(componentSettings, self).__init__(parent=parent)
        self.settingsTab = settingsTab()
        self.last_path = ""

        self.setup_componentSettingWindow()
        self.create_componentControls()
        self.populate_componentControls()
        self.create_componentLayout()
        self.create_componentConnections()

    def setup_componentSettingWindow(self):
        self.mayaMainWindow = pyqt.maya_main_window()

        self.setObjectName(self.toolName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle(TYPE)
        self.resize(380, 700)

    def create_componentControls(self):
        return

    def populate_componentControls(self):
        """Populate the controls from the guide attributes."""
        self.tabs.insertTab(1, self.settingsTab, "Component Settings")
        self.settingsTab.form.set_settings(self.guide_settings())

        # populate connections in main settings
        cBox = self.mainSettingsTab.connector_comboBox
        for cnx in Guide.connectors:
            cBox.addItem(cnx)
        self.connector_items = [cBox.itemText(i) for i in range(cBox.count())]
        currentConnector = self.root.attr("connector").get()
        if currentConnector not in self.connector_items:
            cBox.addItem(currentConnector)
            self.connector_items.append(currentConnector)
        cBox.setCurrentIndex(self.connector_items.index(currentConnector))

    def create_componentLayout(self):
        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)
        self.setLayout(self.settings_layout)

    def create_componentConnections(self):
        tab = self.settingsTab
        self.mainSettingsTab.connector_comboBox.currentIndexChanged.connect(
            partial(
                self.updateConnector,
                self.mainSettingsTab.connector_comboBox,
                self.connector_items,
            )
        )
        tab.form.valueChanged.connect(self.set_guide_value)
        tab.snap_button.clicked.connect(self.snap_root_to_eyeball)
        tab.import_button.clicked.connect(partial(self.import_settings, None))
        tab.export_button.clicked.connect(partial(self.export_settings, None))

    def guide_settings(self):
        """Get the eyelid settings stored on the guide.

        Returns:
            dict: {key: value}
        """
        return {param.key: self.root.attr(param.key).get() for param in guide_schema()}

    def set_guide_value(self, key, value):
        """Store a setting on the guide.

        Args:
            key (str): Setting key.
            value (object): Setting value.
        """
        self.root.attr(key).set(value)

    def snap_root_to_eyeball(self):
        """Move the guide root to the eyeball center."""
        eye_mesh = self.root.attr("eyeMesh").get()
        if not eye_mesh or not cmds.objExists(eye_mesh):
            selection = cmds.ls(selection=True, objectsOnly=True)
            eye_mesh = selection[0] if selection else ""
        if not eye_mesh:
            cmds.warning("Set the eyeball mesh or select it")
            return
        bbox = cmds.exactWorldBoundingBox(eye_mesh)
        center = [(bbox[i] + bbox[i + 3]) * 0.5 for i in range(3)]
        cmds.xform(self.root.name(), worldSpace=True, translation=center)

    def _start_dir(self):
        if self.last_path:
            return os.path.dirname(self.last_path)
        return cmds.workspace(query=True, rootDirectory=True)

    def import_settings(self, path=None):
        """Load the guide settings from a ``.eyes`` file (3.0 or 2.1).

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Import Eye Rigger Configuration",
                self._start_dir(),
                eyelid_schema.FILE_FILTER,
            )
        if not path:
            return
        try:
            settings, warnings = eyelid_schema.load_settings(path)
        except ValueError as error:
            cmds.warning(str(error))
            return
        for warning in warnings:
            cmds.warning("Eye Rigger: {}".format(warning))
        self.last_path = path
        settings = settings_schema.filter_scope(settings, guide_schema(), "shared")
        for key, value in settings.items():
            self.root.attr(key).set(value)
        self.settingsTab.form.set_settings(settings)

    def export_settings(self, path=None):
        """Save the guide settings to a ``.eyes`` file.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export Eye Rigger Configuration",
                self._start_dir(),
                eyelid_schema.FILE_FILTER,
            )
        if not path:
            return
        path = config_io.file_path(path, eyelid_schema.FILE_EXT)
        settings = settings_schema.defaults(eyelid_schema.SCHEMA)
        settings.update(self.guide_settings())
        eyelid_schema.save_settings(path, settings)
        self.last_path = path

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
