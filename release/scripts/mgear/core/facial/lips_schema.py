"""Lips Rigger settings: the single source of the lips rig settings.

Used by the Lips Rigger 3.0 tool, its ``.lips`` configuration files and the
lips Shifter component. Lips Rigger 1.0 snake_case keys are legacy keys, so
1.0 files load. No Qt.
"""

from mgear.core import settings_schema
from mgear.core.settings_schema import Param

FILE_TYPE = "lips_rigger"
FILE_EXT = ".lips"
FILE_FILTER = "Lips Rigger Configuration (*{})".format(FILE_EXT)
SCHEMA_VERSION = 3

LOOP_TYPES = ("edge", "vertex")

# Lips Rigger 1.0 keys 3.0 doesn't use: the mid vertices are always found
# from the loop, and invertLips fixes a wrong upper/lower detection
DROPPED_KEYS = ("up_vertex", "low_vertex")

SCHEMA = [
    # Tool only, a Shifter component gets these from the guide
    Param(
        "namePrefix",
        "string",
        "lips",
        scope="tool",
        label="Name Prefix",
        legacy_keys=("name_prefix",),
        tooltip="Prefix of every node name: <prefix>_C_<name>.",
    ),
    Param(
        "ctlName",
        "string",
        "ctl",
        scope="tool",
        label="Control Name",
        legacy_keys=("control_name",),
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
        label="Head Joint",
        kind="node",
        legacy_keys=("head_joint",),
        tooltip="Parent of the upper lip joints, and the joint the upper lip "
        "follows when no upper reference is set.",
    ),
    Param(
        "jawJnt",
        "string",
        "",
        scope="tool",
        label="Jaw Joint",
        kind="node",
        legacy_keys=("jaw_joint",),
        tooltip="Parent of the lower lip joints, and the joint the lower lip "
        "follows when no lower reference is set.",
    ),
    Param(
        "frontNode",
        "string",
        "",
        scope="tool",
        label="Mouth Front",
        kind="node",
        tooltip="Transform in front of the mouth, e.g. a locator: the mouth "
        "faces it. Set it for a rotated head. The scene front (+Z, or -Y in a "
        "Z up scene) when empty.",
    ),
    Param(
        "upperRef",
        "string",
        "",
        scope="tool",
        label="Upper Reference",
        kind="node",
        legacy_keys=("upper_lip_ctl",),
        tooltip="Transform the upper lip follows, e.g. an upper lip or head "
        "control. The head joint when empty.",
    ),
    Param(
        "lowerRef",
        "string",
        "",
        scope="tool",
        label="Lower Reference",
        kind="node",
        legacy_keys=("lower_lip_ctl",),
        tooltip="Transform the lower lip follows, e.g. a lower lip or jaw "
        "control. The jaw joint when empty.",
    ),
    # Geometry
    Param(
        "loopType",
        "enum",
        1,
        label="Loop Type",
        choices=LOOP_TYPES,
        tooltip="Pick the closed loop around the lips as edges or as vertices.",
    ),
    Param(
        "edgeLoop",
        "string",
        "",
        label="Edge Loop",
        kind="edges",
        legacy_keys=("edge_loop",),
        tooltip="Closed edge loop along the lips, where the upper and lower "
        "lips meet.",
    ),
    Param(
        "vertexLoop",
        "string",
        "",
        label="Vertex Loop",
        kind="vertices",
        tooltip="Closed vertex loop along the lips, where the upper and lower "
        "lips meet.",
    ),
    Param(
        "invertLips",
        "bool",
        False,
        label="Invert Upper/Lower",
        tooltip="Swap the detected upper and lower lips. Use Check Detection "
        "to see which part of the loop is found as the upper lip.",
    ),
    Param(
        "thickness",
        "double",
        0.03,
        minimum=0.0,
        maximum=10.0,
        label="Lips Thickness",
        tooltip="Depth of the joints inside the lips, from the loop. The lip "
        "roll pivots on them.",
    ),
    Param(
        "upvOffset",
        "double",
        0.02,
        minimum=0.001,
        maximum=10.0,
        label="Up Vector Offset",
        tooltip="Distance in front of the lips of the joint orientation up vectors.",
    ),
    Param(
        "ropeCount",
        "long",
        15,
        minimum=5,
        maximum=100,
        label="Rope Points",
        tooltip="Points of the curves the joints slide on. Fewer points give "
        "smoother lip shapes, more points follow the controls closer and "
        "give a finer zipper.",
    ),
    # Controls
    Param(
        "ctlSize",
        "double",
        1.0,
        minimum=0.01,
        maximum=10.0,
        label="Control Size",
        tooltip="Size multiplier of the control shapes.",
    ),
    Param(
        "mirrorBehavior",
        "bool",
        True,
        label="Mirror Behavior",
        tooltip="Right side controls mirror the left ones: the same values "
        "give a mirrored pose.",
    ),
    Param(
        "jawFollow",
        "double",
        0.5,
        minimum=0.0,
        maximum=1.0,
        label="Corners Jaw Follow",
        tooltip="Default of the corner controls jawFollow attribute: 0 "
        "follows the upper reference, 1 the lower reference.",
    ),
    Param(
        "zipperFalloff",
        "double",
        0.3,
        minimum=0.01,
        maximum=1.0,
        label="Zipper Falloff",
        tooltip="Width of the zipper front, as a part of the lip from the "
        "corner to the center. Higher values zip softer.",
    ),
    Param(
        "rollFalloff",
        "bool",
        True,
        label="Roll Falloff",
        tooltip="The lip roll fades out toward the corners. Off rolls the "
        "whole lip the same.",
    ),
    Param(
        "squashStretch",
        "bool",
        False,
        label="Squash and Stretch",
        tooltip="Lips get thinner when stretched and thicker when compressed. "
        "Animators turn it down or off with the squashStretch attribute of "
        "the upper and lower controls.",
    ),
    # Joints
    Param(
        "jointsFollowCurve",
        "bool",
        True,
        label="Joints Rotate with Curve",
        tooltip="The joints aim along the lip curve, with their up vector "
        "in front. Off: the joints only translate along the lips and keep "
        "the lips orientation, turning with the upper reference, or the "
        "lower reference for the lower lip.",
    ),
    Param(
        "everyNVertex",
        "long",
        1,
        minimum=1,
        maximum=100,
        label="Joint Every N Vertex",
        tooltip="One lip joint every N loop vertices.",
    ),
    Param(
        "fixedJoints",
        "bool",
        False,
        label="Fixed Joint Number",
        tooltip="Spread a fixed number of joints along each lip instead.",
    ),
    Param(
        "fixedJointsNumber",
        "long",
        7,
        minimum=3,
        maximum=99,
        label="Joints Per Lip",
        tooltip="Joints on the upper lip, corners included. The lower lip "
        "shares the corners.",
    ),
    # Skin
    Param(
        "doSkin",
        "bool",
        True,
        label="Topological Autoskin",
        legacy_keys=("do_skin",),
        tooltip="Skin the lip joints to the vertex rings around the loop, "
        "blended with the strongest existing influence. A new skin cluster "
        "uses the head joint.",
    ),
    Param(
        "rigidLoops",
        "long",
        5,
        minimum=0,
        maximum=30,
        label="Rigid Loops",
        legacy_keys=("rigid_loops",),
        tooltip="Vertex rings around the loop fully weighted to the lip joints.",
    ),
    Param(
        "falloffLoops",
        "long",
        8,
        minimum=0,
        maximum=30,
        label="Falloff Loops",
        legacy_keys=("falloff_loops",),
        tooltip="Vertex rings after the rigid ones, fading to the existing " "weights.",
    ),
    Param(
        "skinSmooth",
        "long",
        3,
        minimum=0,
        maximum=20,
        label="Smooth Iterations",
        tooltip="Smooth the autoskin weights around the lips, so the weights "
        "blend between neighbor joints and at the mouth corners instead of "
        "pinching. 0 keeps the hard topological weights.",
    ),
]


# settings form layout: (group title, setting keys)
FORM_GROUPS = (
    (
        "Geometry",
        ["loopType", "edgeLoop", "vertexLoop", "invertLips", "thickness"],
    ),
    ("Naming", ["namePrefix", "ctlName"]),
    (
        "Rig",
        [
            "frontNode",
            "headJnt",
            "jawJnt",
            "upperRef",
            "lowerRef",
            "parent_node",
            "ctlSet",
            "defSet",
        ],
    ),
    (
        "Controls",
        [
            "ctlSize",
            "mirrorBehavior",
            "jawFollow",
            "zipperFalloff",
            "rollFalloff",
            "squashStretch",
        ],
    ),
    (
        "Joints",
        [
            "jointsFollowCurve",
            "everyNVertex",
            "fixedJoints",
            "fixedJointsNumber",
            "ropeCount",
            "upvOffset",
        ],
    ),
    ("Skin", ["doSkin", "rigidLoops", "falloffLoops", "skinSmooth"]),
)


def legacy_loop_type(data):
    """Set the loop type of settings saved before it existed.

    Lips Rigger 1.0 settings only have an edge loop, while 3.0 defaults to a
    vertex loop.

    Args:
        data (dict): Saved or passed settings, changed in place.

    Returns:
        dict: The settings.
    """
    edges = data.get("edgeLoop") or data.get("edge_loop")
    if "loopType" not in data and edges and not data.get("vertexLoop"):
        data["loopType"] = LOOP_TYPES.index("edge")
    return data


def loop_string(settings):
    """Get the lips loop component string of the selected loop type.

    Args:
        settings (dict): Lips settings.

    Returns:
        str: The edge or vertex loop.
    """
    if LOOP_TYPES[settings["loopType"]] == "vertex":
        return settings["vertexLoop"]
    return settings["edgeLoop"]


# settings showing or hiding other settings in a settings form
ROW_KEYS = ("loopType", "jointsFollowCurve", "fixedJoints", "doSkin")


def row_visibility(settings):
    """Get which settings apply, from the settings that switch them.

    Args:
        settings (dict): Lips settings (only ROW_KEYS are read).

    Returns:
        dict: {setting key: visible}
    """
    vertex = LOOP_TYPES[settings["loopType"]] == "vertex"
    fixed = bool(settings["fixedJoints"])
    skin = bool(settings["doSkin"])
    return {
        "upvOffset": bool(settings["jointsFollowCurve"]),
        "edgeLoop": not vertex,
        "vertexLoop": vertex,
        "everyNVertex": not fixed,
        "fixedJointsNumber": fixed,
        "rigidLoops": skin,
        "falloffLoops": skin,
        "skinSmooth": skin,
    }


def settings_from_data(data):
    """Get lips settings from loaded ``.lips`` file data, 3.0 or 1.0.

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
        label="Lips Rigger",
        upgrade=legacy_loop_type,
    )


def load_settings(path):
    """Load lips settings from a ``.lips`` file, 3.0 or 1.0.

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
        label="Lips Rigger",
        upgrade=legacy_loop_type,
    )


def save_settings(path, settings):
    """Save lips settings to a ``.lips`` file.

    Args:
        path (str): File path.
        settings (dict): Lips settings.
    """
    settings_schema.save_settings(path, FILE_TYPE, SCHEMA_VERSION, settings)
