"""Guide Lips 01 module"""

import math

from maya import cmds

from mgear.shifter.component import guide
from mgear.shifter.component import facial_guide
from mgear.core import transform
from mgear.core.facial import lips_schema
from mgear.core.facial import lips_solver
from mgear.core.settings_schema import Param

from mgear.vendor.Qt import QtWidgets

# guide info
AUTHOR = "Miquel Campos"
URL = "www.mcsgear.com"
EMAIL = ""
VERSION = [1, 0, 0]
TYPE = "lips_01"
NAME = "lips"
DESCRIPTION = (
    "Lips rig from the loop between the lips (Lips Rigger 3.0). The root is "
    "the mouth center, root to aim is the mouth front direction, the aim "
    "depth in front of the lips is the control offset and the root to lip "
    "distance is the lips thickness."
)

# settings holding mesh component indices, mirrored with the guide
INDEX_KEYS = ("edgeLoop", "vertexLoop")

# settings the guide locators decide
GUIDE_DECIDED = ("thickness",)

# guide defaults replacing the tool ones
GUIDE_DEFAULTS = {"doSkin": False}

# the component's own setting, only for the standard connector
JAW_REF = Param(
    "jawRef",
    "string",
    "",
    label="Jaw Reference",
    kind="node",
    tooltip="Standard connector only: guide element the lower lip follows, "
    "e.g. the jaw control guide. The guide parent when empty. With a mouth "
    "component parent, use its connector: the lips follow the mouth "
    "automatically.",
)


def lips_settings(values):
    """Get complete lips settings from the guide values.

    Args:
        values (dict): Guide settings.

    Returns:
        dict: Coerced lips settings.
    """
    return facial_guide.rig_settings(lips_schema.SCHEMA, values)


def solve(values, positions):
    """Solve the lips geometry of a guide.

    Args:
        values (dict): Guide settings.
        positions (dict): Guide locator positions, with "root", "aim" and
            "lip". The root to lip distance is the lips thickness.

    Returns:
        tuple: (lips settings, LipsGeometry)

    Raises:
        ValueError: If the guide doesn't describe valid lips.
    """
    settings = lips_settings(values)
    settings["thickness"] = math.dist(positions["root"], positions["lip"])
    geometry = lips_solver.solve(
        settings, center=tuple(positions["root"]), aim=tuple(positions["aim"])
    )
    return settings, geometry


def guide_schema():
    """Get the lips settings stored on the guide.

    Returns:
        list: Shared lips schema params the locators don't decide.
    """
    return facial_guide.shared_params(lips_schema.SCHEMA, GUIDE_DECIDED)


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

    # named after the mouth components: drawn under one, it is picked
    connectors = ["mouth_01", "mouth_02", "MCS_mouth_01", "MCS_mouth_03"]

    def postInit(self):
        """Initialize the position for the guide"""
        self.save_transform = ["root", "aim", "lip"]
        # lips geometry solved by validate, reused by the build
        self.geometry = None

    def addObjects(self):
        """Add the Guide Root, the aim and the lip thickness locators"""
        self.root = self.addRoot()
        position = transform.getOffsetPosition(self.root, [0, 0, 1])
        self.aim = self.addLoc("aim", self.root, position)
        position = transform.getOffsetPosition(self.root, [0, 0.1, 0])
        self.lip = self.addLoc("lip", self.root, position)
        self.dispcrv = self.addDispCurve("crv", [self.root, self.aim])
        self.lipcrv = self.addDispCurve("lipCrv", [self.root, self.lip])

    def addParameters(self):
        """Add the configurations settings"""
        facial_guide.add_params(self, guide_schema() + [JAW_REF], GUIDE_DEFAULTS)
        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None
        )

    def validate(self):
        """Check the lips can be solved from the mesh and the guide.

        Returns:
            list: Problem messages, empty when the lips can build.
        """
        try:
            self.geometry = solve(self.values, self.pos)[1]
        except ValueError as error:
            self.geometry = None
            return ["{}. Check the {} component settings".format(error, TYPE)]
        return []

    def symmetrize(self):
        """Mirror a side guide, and its lips loop on the mesh.

        A center lips guide keeps its loop.

        Returns:
            bool: False for a center guide.
        """
        if not super(Guide, self).symmetrize():
            return False
        facial_guide.mirror_index_params(self, INDEX_KEYS)
        return True


##########################################################
# Setting Page
##########################################################


class componentSettings(facial_guide.FacialComponentSettings):
    """Create the component setting window"""

    toolName = TYPE
    connectors = Guide.connectors
    schema = lips_schema
    params = guide_schema() + [JAW_REF]
    extra_groups = (("Standard Connector", ["jawRef"]),)
    title = "Lips Rigger"

    def populate_componentControls(self):
        """Populate the controls, showing jawRef with the standard connector."""
        super(componentSettings, self).populate_componentControls()
        self.update_connector_rows()

    def create_componentConnections(self):
        """Connect the controls."""
        super(componentSettings, self).create_componentConnections()
        self.mainSettingsTab.connector_comboBox.currentIndexChanged.connect(
            self.update_connector_rows
        )

    def update_connector_rows(self, *args):
        """Show the settings of the selected connector only."""
        connector = self.mainSettingsTab.connector_comboBox.currentText()
        self.settingsTab.form.set_group_visible(
            "Standard Connector", connector == "standard"
        )

    def create_extra_buttons(self):
        """Create the Check Detection button."""
        button = QtWidgets.QPushButton("Check Detection")
        button.setToolTip(
            "Select the upper lip found from the loop and the guide. Turn on "
            "Invert Upper/Lower when the lower lip is selected."
        )
        button.clicked.connect(self.check_detection)
        return [button]

    def check_detection(self):
        """Select the upper lip found from the loop and the guide.

        Returns:
            LipsGeometry: The geometry, or None when it can't be solved.
        """
        root = self.root.name()
        positions = {"root": root}
        for child in cmds.listRelatives(root, children=True, fullPath=True) or []:
            for name in ("aim", "lip"):
                if child.endswith("_" + name):
                    positions[name] = child
        if len(positions) < 3:
            cmds.warning("Lips Rigger: the guide has no aim or lip locator")
            return None
        positions = {
            key: cmds.xform(node, query=True, worldSpace=True, translation=True)
            for key, node in positions.items()
        }
        try:
            _, geometry = solve(self.guide_settings(), positions)
        except ValueError as error:
            cmds.warning("Lips Rigger: {}".format(error))
            return None
        cmds.select(lips_solver.detection_selection(geometry))
        return geometry
