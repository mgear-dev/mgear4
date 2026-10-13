"""Guide Brow 01 module"""

from maya import cmds

from mgear.shifter.component import guide
from mgear.shifter.component import facial_guide
from mgear.core import transform
from mgear.core.facial import brow_schema
from mgear.core.facial import brow_solver
from mgear.core.settings_schema import Param

from mgear.vendor.Qt import QtWidgets

# guide info
AUTHOR = "Miquel Campos"
URL = "www.mcsgear.com"
EMAIL = ""
VERSION = [1, 0, 0]
TYPE = "brow_01"
NAME = "brow"
DESCRIPTION = (
    "Brow rig from a path along the brow (Brow Rigger 3.0), one side per "
    "component. The root is near the brow, root to aim is the front "
    "direction and the aim depth is the control offset. A center brow can "
    "follow the inner controls of the left and right brows."
)

# settings holding mesh component indices, mirrored with the guide
INDEX_KEYS = ("edgeLoop", "vertexLoop")

# guide defaults replacing the tool ones
GUIDE_DEFAULTS = {"doSkin": False}

# the component's own settings, for a center brow
HOOK_PARAMS = (
    Param(
        "leftBrow",
        "string",
        "",
        label="Left Brow",
        kind="node",
        tooltip="Center brow only: root of the left brow_01 guide. The left "
        "end follows its inner control.",
    ),
    Param(
        "rightBrow",
        "string",
        "",
        label="Right Brow",
        kind="node",
        tooltip="Center brow only: root of the right brow_01 guide. The right "
        "end follows its inner control.",
    ),
)
HOOK_GROUP = "Center Brow"


def brow_settings(values):
    """Get complete brow settings from the guide values.

    Args:
        values (dict): Guide settings.

    Returns:
        dict: Coerced brow settings.
    """
    return facial_guide.rig_settings(brow_schema.SCHEMA, values)


def solve(values, positions, side):
    """Solve the brow geometry of a guide.

    Args:
        values (dict): Guide settings.
        positions (dict): Guide locator positions, with "root" and "aim".
        side (str): Component side.

    Returns:
        tuple: (brow settings, BrowGeometry)

    Raises:
        ValueError: If the guide doesn't describe a valid brow.
    """
    settings = brow_settings(values)
    geometry = brow_solver.solve(
        settings,
        center=tuple(positions["root"]),
        aim=tuple(positions["aim"]),
        side=side,
    )
    return settings, geometry


def hooked(values):
    """Tell if a guide is a center brow following the side brows.

    Args:
        values (dict): Guide settings.

    Returns:
        bool: True for a center brow with both side brows set.
    """
    return (
        values["comp_side"] == "C"
        and bool(values["leftBrow"])
        and bool(values["rightBrow"])
    )


def guide_schema():
    """Get the brow settings stored on the guide.

    Returns:
        list: Shared brow schema params.
    """
    return facial_guide.shared_params(brow_schema.SCHEMA)


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

    def postInit(self):
        """Initialize the position for the guide"""
        self.save_transform = ["root", "aim"]
        # brow geometry solved by validate, reused by the build
        self.geometry = None

    def addObjects(self):
        """Add the Guide Root and the aim locator"""
        self.root = self.addRoot()
        position = transform.getOffsetPosition(self.root, [0, 0, 1])
        self.aim = self.addLoc("aim", self.root, position)
        self.dispcrv = self.addDispCurve("crv", [self.root, self.aim])

    def addParameters(self):
        """Add the configurations settings"""
        facial_guide.add_params(
            self, guide_schema() + list(HOOK_PARAMS), GUIDE_DEFAULTS
        )
        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None
        )

    def validate(self):
        """Check the brow can be solved, and the side brows of a center one.

        Returns:
            list: Problem messages, empty when the brow can build.
        """
        try:
            self.geometry = solve(self.values, self.pos, self.values["comp_side"])[1]
        except ValueError as error:
            self.geometry = None
            return ["{}. Check the {} component settings".format(error, TYPE)]
        if not hooked(self.values):
            return []
        problems = []
        for key in ("leftBrow", "rightBrow"):
            name = self.values[key]
            if (
                not cmds.objExists(name)
                or not cmds.attributeQuery("comp_type", node=name, exists=True)
                or cmds.getAttr(name + ".comp_type") != TYPE
            ):
                problems.append("{} {} is not a {} guide root".format(key, name, TYPE))
        return problems

    def symmetrize(self):
        """Mirror the guide, and the brow path on the mesh.

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
    connectors = []
    schema = brow_schema
    params = guide_schema() + list(HOOK_PARAMS)
    extra_groups = ((HOOK_GROUP, [param.key for param in HOOK_PARAMS]),)
    title = "Brow Rigger"

    def populate_componentControls(self):
        """Populate the controls, showing the hooks for a center brow."""
        super(componentSettings, self).populate_componentControls()
        self.update_side_rows()

    def create_componentConnections(self):
        """Connect the controls."""
        super(componentSettings, self).create_componentConnections()
        self.mainSettingsTab.side_comboBox.currentIndexChanged.connect(
            self.update_side_rows
        )

    def update_side_rows(self, *args):
        """Show the center brow settings for a center brow only."""
        # the side items are Center, Left and Right
        center = self.mainSettingsTab.side_comboBox.currentIndex() == 0
        self.settingsTab.form.set_group_visible(HOOK_GROUP, center)

    def create_extra_buttons(self):
        """Create the Check Detection button."""
        button = QtWidgets.QPushButton("Check Detection")
        button.setToolTip(
            "Select the inner end of the brow found from the path and the "
            "guide (the right end of a center brow)."
        )
        button.clicked.connect(self.check_detection)
        return [button]

    def check_detection(self):
        """Select the first brow end found from the path and the guide.

        Returns:
            BrowGeometry: The geometry, or None when it can't be solved.
        """
        positions = self.locator_positions(("aim",))
        if positions is None:
            return None
        side = self.root.attr("comp_side").get()
        try:
            _, geometry = solve(self.guide_settings(), positions, side)
        except ValueError as error:
            cmds.warning("Brow Rigger: {}".format(error))
            return None
        cmds.select(brow_solver.detection_selection(geometry))
        return geometry
