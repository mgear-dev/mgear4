"""Guide Eyelid 01 module"""

from maya import cmds

from mgear.shifter.component import guide
from mgear.shifter.component import facial_guide
from mgear.core import transform
from mgear.core.facial import eyelid_schema
from mgear.core.facial import eyelid_solver

from mgear.vendor.Qt import QtWidgets

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
    source = "external" if follow_eye else "own"
    return facial_guide.rig_settings(
        eyelid_schema.SCHEMA,
        values,
        {"trackingSource": eyelid_schema.TRACKING_SOURCES.index(source)},
    )


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
    return facial_guide.shared_params(eyelid_schema.SCHEMA, GUIDE_DECIDED)


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
        facial_guide.add_params(self, guide_schema())
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
        facial_guide.mirror_index_params(self, INDEX_KEYS)
        return True


##########################################################
# Setting Page
##########################################################


class componentSettings(facial_guide.FacialComponentSettings):
    """Create the component setting window"""

    toolName = TYPE
    connectors = Guide.connectors
    schema = eyelid_schema
    params = guide_schema()
    title = "Eye Rigger"

    def create_extra_buttons(self):
        """Create the Snap Root to Eyeball button."""
        button = QtWidgets.QPushButton("Snap Root to Eyeball")
        button.clicked.connect(self.snap_root_to_eyeball)
        return [button]

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
