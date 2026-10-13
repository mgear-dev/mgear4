"""Settings of the eyelid rig (Eye Rigger 3.0 and the eyelid component).

The keys are the Eye Rigger 2.1 keys, so its ``.eyes`` files still load.
"""

from mgear.core import settings_schema
from mgear.core.settings_schema import Param

FILE_TYPE = "eye_rigger"
FILE_EXT = ".eyes"
FILE_FILTER = "Eye Rigger Configuration (*{})".format(FILE_EXT)
SCHEMA_VERSION = 3

LOOP_TYPES = ("edge", "vertex")
TRACKING_SOURCES = ("own", "external")

# Eye Rigger 2.1 keys that 3.0 doesn't use
DROPPED_KEYS = ("blinkH", "orderFromCenter")

SCHEMA = [
    # Tool only, a Shifter component gets these from the guide
    Param(
        "namePrefix",
        "string",
        "eye",
        scope="tool",
        label="Name Prefix",
        tooltip="Prefix of every node name: <prefix>_<side>_<name>.",
    ),
    Param(
        "ctlName",
        "string",
        "ctl",
        scope="tool",
        label="Control Name",
        tooltip="Suffix of the control names. With a '_ghost' ending, e.g. "
        "'ctl_ghost', the controls are left out of the controls set.",
    ),
    Param(
        "ctlSet",
        "string",
        "rig_controllers_grp",
        scope="tool",
        label="Controls Set",
        kind="set",
        tooltip="Object set getting the controls. Created if missing.",
    ),
    Param(
        "defSet",
        "string",
        "rig_deformers_grp",
        scope="tool",
        label="Deformers Set",
        kind="set",
        tooltip="Object set getting the deform joints. Created if missing.",
    ),
    Param(
        "parent_node",
        "string",
        "",
        scope="tool",
        label="Rig Parent",
        kind="node",
        tooltip="Parent of the rig root, for example the head control.",
    ),
    Param(
        "headJnt",
        "string",
        "",
        scope="tool",
        label="Head or Eye Area Joint",
        kind="node",
        tooltip="Parent of the eyelid joints, and the joint the autoskin "
        "blends the eyelid weights with.",
    ),
    Param(
        "deformers_group",
        "string",
        "",
        scope="tool",
        label="Static Rig Parent",
        kind="node",
        tooltip="Static group getting the joints root when no head joint is "
        "set. The joints root follows the rig root.",
    ),
    Param(
        "aim_controller",
        "string",
        "",
        scope="tool",
        label="Aim Controller",
        kind="node",
        tooltip="Existing control that aims the eye. The rig makes its own "
        "aim control when empty.",
    ),
    # Geometry
    Param(
        "eyeMesh",
        "string",
        "",
        label="Eyeball",
        kind="mesh",
        tooltip="Eyeball mesh. Its bounding box center is the eye pivot.",
    ),
    Param(
        "loopType",
        "enum",
        1,
        label="Loop Type",
        choices=LOOP_TYPES,
        tooltip="Pick the closed loop around the eyelid as edges or as vertices.",
    ),
    Param(
        "edgeLoop",
        "string",
        "",
        label="Edge Loop",
        kind="edges",
        tooltip="Closed edge loop around the eyelid opening.",
    ),
    Param(
        "vertexLoop",
        "string",
        "",
        label="Vertex Loop",
        kind="vertices",
        tooltip="Closed vertex loop around the eyelid opening.",
    ),
    Param(
        "customCorner",
        "bool",
        False,
        label="Custom Corners",
        tooltip="Pick the eye corner vertices instead of finding them.",
    ),
    Param(
        "intCorner",
        "string",
        "",
        label="Internal Corner",
        kind="vertex",
        tooltip="Inner (nose side) corner vertex, on the loop.",
    ),
    Param(
        "extCorner",
        "string",
        "",
        label="External Corner",
        kind="vertex",
        tooltip="Outer corner vertex, on the loop.",
    ),
    Param(
        "sideRange",
        "bool",
        False,
        label="Side Range",
        tooltip="Eyes looking to the side (horse, fish): the corners are "
        "found front to back.",
    ),
    # Controls
    Param(
        "offset",
        "double",
        0.05,
        minimum=0.0,
        maximum=10.0,
        label="Offset",
        tooltip="Distance of the control shapes in front of the eyelid.",
    ),
    Param(
        "ctl_size",
        "double",
        1.0,
        minimum=0.01,
        maximum=10.0,
        label="Control Size",
        tooltip="Size multiplier of the control shapes.",
    ),
    Param(
        "simplified",
        "bool",
        False,
        label="Simplified Controls",
        tooltip="The blink controls also move the mid eyelid point, and the "
        "side mid controls can be hidden.",
    ),
    Param(
        "mirrorBehavior",
        "bool",
        True,
        label="Mirror Behavior",
        tooltip="Right side eyelid controls mirror the left ones: the same "
        "values give a mirrored pose. The aim control never mirrors.",
    ),
    # Tracking
    Param(
        "trackingSource",
        "enum",
        0,
        label="Tracking Source",
        choices=TRACKING_SOURCES,
        tooltip="Aim the eye with the rig's own control or an external one.",
    ),
    Param(
        "upperVTrack",
        "double",
        0.02,
        minimum=0.0,
        label="Upper Vertical",
        tooltip="How much the upper eyelid follows the eye looking up and down.",
    ),
    Param(
        "upperHTrack",
        "double",
        0.01,
        minimum=0.0,
        label="Upper Horizontal",
        tooltip="How much the upper eyelid follows the eye looking sideways.",
    ),
    Param(
        "lowerVTrack",
        "double",
        0.02,
        minimum=0.0,
        label="Lower Vertical",
        tooltip="How much the lower eyelid follows the eye looking up and down.",
    ),
    Param(
        "lowerHTrack",
        "double",
        0.01,
        minimum=0.0,
        label="Lower Horizontal",
        tooltip="How much the lower eyelid follows the eye looking sideways.",
    ),
    # Joints
    Param(
        "everyNVertex",
        "long",
        1,
        minimum=1,
        maximum=100,
        label="Joint Every N Vertex",
        tooltip="One eyelid joint every N loop vertices.",
    ),
    Param(
        "fixedJoints",
        "bool",
        False,
        label="Fixed Joint Number",
        tooltip="Spread a fixed number of joints along each eyelid instead.",
    ),
    Param(
        "fixedJointsNumber",
        "long",
        3,
        minimum=3,
        maximum=99,
        label="Joints Per Eyelid",
        tooltip="Joints on the upper eyelid, corners included. The lower "
        "eyelid shares the corners.",
    ),
    # Skin
    Param(
        "doSkin",
        "bool",
        True,
        label="Topological Autoskin",
        tooltip="Skin the eyelid joints to the vertex rings around the loop, "
        "and the eyeball to the eye joint. Needs the head joint.",
    ),
    Param(
        "rigidLoops",
        "long",
        2,
        minimum=0,
        maximum=30,
        label="Rigid Loops",
        tooltip="Vertex rings around the loop fully weighted to the eyelid joints.",
    ),
    Param(
        "falloffLoops",
        "long",
        4,
        minimum=0,
        maximum=30,
        label="Falloff Loops",
        tooltip="Vertex rings after the rigid ones, fading to the head joint.",
    ),
]


# settings form layout: (group title, setting keys)
FORM_GROUPS = (
    (
        "Geometry",
        [
            "eyeMesh",
            "loopType",
            "edgeLoop",
            "vertexLoop",
            "customCorner",
            "intCorner",
            "extCorner",
            "sideRange",
        ],
    ),
    ("Naming", ["namePrefix", "ctlName"]),
    (
        "Rig",
        [
            "headJnt",
            "aim_controller",
            "parent_node",
            "deformers_group",
            "ctlSet",
            "defSet",
        ],
    ),
    ("Controls", ["offset", "ctl_size", "simplified", "mirrorBehavior"]),
    (
        "Tracking",
        ["upperVTrack", "upperHTrack", "lowerVTrack", "lowerHTrack"],
    ),
    (
        "Joints",
        ["everyNVertex", "fixedJoints", "fixedJointsNumber"],
    ),
    ("Skin", ["doSkin", "rigidLoops", "falloffLoops"]),
)


def legacy_loop_type(data):
    """Set the loop type of settings saved before it existed.

    Eye Rigger 2.1 settings only have an edge loop, while 3.0 defaults to a
    vertex loop.

    Args:
        data (dict): Saved or passed settings, changed in place.

    Returns:
        dict: The settings.
    """
    if "loopType" not in data and data.get("edgeLoop") and not data.get("vertexLoop"):
        data["loopType"] = LOOP_TYPES.index("edge")
    return data


def uses_own_aim(settings):
    """Tell if the rig makes its own eye aim control.

    It does with the "own" tracking source and no aim controller set.

    Args:
        settings (dict): Coerced eyelid settings.

    Returns:
        bool: True for an own aim control.
    """
    own = TRACKING_SOURCES[settings["trackingSource"]] == "own"
    return own and not settings.get("aim_controller")


# settings showing or hiding other settings in a settings form
ROW_KEYS = ("loopType", "customCorner", "fixedJoints", "doSkin")


def row_visibility(settings):
    """Get which settings apply, from the settings that switch them.

    Args:
        settings (dict): Eyelid settings (only ROW_KEYS are read).

    Returns:
        dict: {setting key: visible}
    """
    vertex = LOOP_TYPES[settings["loopType"]] == "vertex"
    custom = bool(settings["customCorner"])
    fixed = bool(settings["fixedJoints"])
    skin = bool(settings["doSkin"])
    return {
        "edgeLoop": not vertex,
        "vertexLoop": vertex,
        "intCorner": custom,
        "extCorner": custom,
        "everyNVertex": not fixed,
        "fixedJointsNumber": fixed,
        "rigidLoops": skin,
        "falloffLoops": skin,
    }


def settings_from_data(data):
    """Get eyelid settings from loaded ``.eyes`` file data, 3.0 or 2.1.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        tuple: (settings dict, list of warning strings)
    """
    return settings_schema.settings_from_data(
        data,
        FILE_TYPE,
        SCHEMA,
        DROPPED_KEYS,
        label="Eye Rigger",
        upgrade=legacy_loop_type,
    )


def load_settings(path):
    """Load eyelid settings from a ``.eyes`` file, 3.0 or 2.1.

    Args:
        path (str): File path.

    Returns:
        tuple: (settings dict, list of warning strings)
    """
    return settings_schema.load_settings(
        path,
        FILE_TYPE,
        SCHEMA,
        DROPPED_KEYS,
        label="Eye Rigger",
        upgrade=legacy_loop_type,
    )


def save_settings(path, settings):
    """Save eyelid settings to a ``.eyes`` file.

    Args:
        path (str): File path.
        settings (dict): Eyelid settings.
    """
    settings_schema.save_settings(path, FILE_TYPE, SCHEMA_VERSION, settings)
