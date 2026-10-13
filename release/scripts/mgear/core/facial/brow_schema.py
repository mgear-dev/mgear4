"""Brow Rigger settings: the single source of the brow rig settings.

Used by the Brow Rigger 3.0 tool, its ``.brows`` configuration files and the
brow Shifter component. Brow Rigger 1.0 snake_case keys are legacy keys, so
1.0 files load. No Qt.
"""

from mgear.core import settings_schema
from mgear.core.settings_schema import Param

FILE_TYPE = "brow_rigger"
FILE_EXT = ".brows"
FILE_FILTER = "Brow Rigger Configuration (*{})".format(FILE_EXT)
SCHEMA_VERSION = 3

LOOP_TYPES = ("edge", "vertex")
SIDES = ("auto", "L", "R", "C")

# Brow Rigger 1.0 keys 3.0 doesn't use: it builds one brow per run
DROPPED_KEYS = (
    "symmetry_mode",
    "brow_jnt_L",
    "brow_jnt_R",
    "ctl_parent_C",
    "ctl_parent_L",
    "ctl_parent_R",
)

SCHEMA = [
    # Tool only, a Shifter component gets these from the guide
    Param(
        "namePrefix",
        "string",
        "brow",
        scope="tool",
        label="Name Prefix",
        legacy_keys=("name_prefix",),
        tooltip="Prefix of every node name: <prefix>_<side>_<name>.",
    ),
    Param(
        "ctlName",
        "string",
        "ctl",
        scope="tool",
        label="Control Name",
        legacy_keys=("ctl_name",),
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
        "side",
        "enum",
        0,
        scope="tool",
        label="Side",
        choices=SIDES,
        tooltip="Brow side. Auto finds it from the brow position: L or R off "
        "the head center, C on it (the brow between the eyebrows).",
    ),
    Param(
        "parent_node",
        "string",
        "",
        scope="tool",
        label="Rig Parent",
        kind="node",
        tooltip="Parent of the rig root, for example the head control. The "
        "brow controls follow it.",
    ),
    Param(
        "headJnt",
        "string",
        "",
        scope="tool",
        label="Head Joint",
        kind="node",
        legacy_keys=("brow_jnt_C",),
        tooltip="Parent of the brow joints, and the skin influence of a mesh "
        "without skin cluster.",
    ),
    Param(
        "frontNode",
        "string",
        "",
        scope="tool",
        label="Brow Front",
        kind="node",
        tooltip="Transform in front of the brow, e.g. a locator: the brow "
        "faces it. Set it for a rotated head. The scene front (+Z, or -Y in a "
        "Z up scene) when empty.",
    ),
    Param(
        "hookLeft",
        "string",
        "",
        scope="tool",
        label="Hook Left",
        kind="node",
        tooltip="Center brow only: transform the left end follows, usually "
        "the inner control of the left brow (e.g. brow_L_in_ctl).",
    ),
    Param(
        "hookRight",
        "string",
        "",
        scope="tool",
        label="Hook Right",
        kind="node",
        tooltip="Center brow only: transform the right end follows, usually "
        "the inner control of the right brow (e.g. brow_R_in_ctl).",
    ),
    # Geometry
    Param(
        "loopType",
        "enum",
        1,
        label="Path Type",
        choices=LOOP_TYPES,
        tooltip="Pick the path along the brow as edges or as vertices.",
    ),
    Param(
        "edgeLoop",
        "string",
        "",
        label="Edge Path",
        kind="edges",
        legacy_keys=("edge_loop",),
        tooltip="Open edge path along the brow.",
    ),
    Param(
        "vertexLoop",
        "string",
        "",
        label="Vertex Path",
        kind="vertices",
        tooltip="Open vertex path along the brow.",
    ),
    Param(
        "thickness",
        "double",
        0.0,
        minimum=0.0,
        maximum=10.0,
        label="Joint Depth",
        tooltip="Depth of the joints under the brow surface.",
    ),
    Param(
        "slideSurface",
        "string",
        "",
        label="Slide Surface",
        kind="node",
        tooltip="Optional NURBS surface with the skull shape. The brow "
        "control points slide on it, so the brow follows the skull, and each "
        "control gets a surfaceOffset channel. Empty: no sliding.",
    ),
    # Controls
    Param(
        "mainControls",
        "long",
        3,
        minimum=3,
        maximum=20,
        label="Main Controls",
        legacy_keys=("main_div",),
        tooltip="Main controls along the brow, ends included. The ends get "
        "tangent controls.",
    ),
    Param(
        "useSecondary",
        "bool",
        True,
        label="Secondary Controls",
        legacy_keys=("secondary_ctl_check",),
        tooltip="Add a row of secondary controls riding the main controls.",
    ),
    Param(
        "secondaryControls",
        "long",
        5,
        minimum=3,
        maximum=30,
        label="Secondary Count",
        legacy_keys=("sec_div",),
        tooltip="Secondary controls along the brow, ends included.",
    ),
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
        tooltip="Right brow controls mirror the left ones: the same values "
        "give a mirrored pose.",
    ),
    Param(
        "squeezeDistance",
        "double",
        0.3,
        minimum=0.0,
        maximum=2.0,
        label="Squeeze Distance",
        tooltip="How far the squeeze attribute slides the inner brow toward "
        "the center at 1, as a part of the brow length.",
    ),
    # Joints
    Param(
        "ropeCount",
        "long",
        10,
        minimum=5,
        maximum=100,
        label="Rope Points",
        tooltip="Points of the curves the joints slide on. Fewer points give "
        "smoother shapes, more points follow the controls closer.",
    ),
    Param(
        "upvOffset",
        "double",
        0.02,
        minimum=0.001,
        maximum=10.0,
        label="Up Vector Offset",
        tooltip="Distance in front of the brow of the joint orientation up " "vectors.",
    ),
    Param(
        "jointsFollowCurve",
        "bool",
        True,
        label="Joints Rotate with Curve",
        tooltip="The joints aim along the brow curve, with their up vector "
        "in front. Off: the joints only translate along the brow and keep "
        "the brow orientation, rotating with the rig only.",
    ),
    Param(
        "everyNVertex",
        "long",
        1,
        minimum=1,
        maximum=100,
        label="Joint Every N Vertex",
        tooltip="One brow joint every N path vertices.",
    ),
    Param(
        "fixedJoints",
        "bool",
        False,
        label="Fixed Joint Number",
        tooltip="Spread a fixed number of joints along the brow instead.",
    ),
    Param(
        "fixedJointsNumber",
        "long",
        5,
        minimum=2,
        maximum=99,
        label="Brow Joints",
        tooltip="Joints along the brow, ends included.",
    ),
    # Skin
    Param(
        "doSkin",
        "bool",
        True,
        label="Topological Autoskin",
        legacy_keys=("do_skin",),
        tooltip="Skin the brow joints to the vertex rings around the path, "
        "blended with the strongest existing influence. A new skin cluster "
        "uses the head joint.",
    ),
    Param(
        "rigidLoops",
        "long",
        1,
        minimum=0,
        maximum=30,
        label="Rigid Loops",
        legacy_keys=("rigid_loops",),
        tooltip="Vertex rings around the path fully weighted to the brow joints.",
    ),
    Param(
        "falloffLoops",
        "long",
        2,
        minimum=0,
        maximum=30,
        label="Falloff Loops",
        legacy_keys=("falloff_loops",),
        tooltip="Vertex rings after the rigid ones, fading to the existing weights.",
    ),
    Param(
        "skinSmooth",
        "long",
        3,
        minimum=0,
        maximum=20,
        label="Smooth Iterations",
        tooltip="Smooth the autoskin weights around the brow, so they blend "
        "between neighbor joints. 0 keeps the hard topological weights.",
    ),
]


# settings form layout: (group title, setting keys)
FORM_GROUPS = (
    (
        "Geometry",
        ["loopType", "edgeLoop", "vertexLoop", "thickness", "slideSurface"],
    ),
    ("Naming", ["namePrefix", "ctlName", "side"]),
    (
        "Rig",
        [
            "frontNode",
            "headJnt",
            "parent_node",
            "hookLeft",
            "hookRight",
            "ctlSet",
            "defSet",
        ],
    ),
    (
        "Controls",
        [
            "mainControls",
            "useSecondary",
            "secondaryControls",
            "ctlSize",
            "mirrorBehavior",
            "squeezeDistance",
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


def legacy_upgrade(data):
    """Update settings saved before 3.0.

    Brow Rigger 1.0 settings only have an edge loop, while 3.0 defaults to
    a vertex path, and their side index is 0 C, 1 L, 2 R, while 3.0 adds
    auto first.

    Args:
        data (dict): Saved or passed settings, changed in place.

    Returns:
        dict: The settings.
    """
    edges = data.get("edgeLoop") or data.get("edge_loop")
    if "loopType" not in data and edges and not data.get("vertexLoop"):
        data["loopType"] = LOOP_TYPES.index("edge")
    if "edge_loop" in data and isinstance(data.get("side"), int):
        data["side"] = SIDES.index(("C", "L", "R")[data["side"]])
    return data


def loop_string(settings):
    """Get the brow path component string of the selected path type.

    Args:
        settings (dict): Brow settings.

    Returns:
        str: The edge or vertex path.
    """
    if LOOP_TYPES[settings["loopType"]] == "vertex":
        return settings["vertexLoop"]
    return settings["edgeLoop"]


# settings showing or hiding other settings in a settings form
ROW_KEYS = (
    "loopType",
    "useSecondary",
    "jointsFollowCurve",
    "fixedJoints",
    "doSkin",
    "side",
)


def row_visibility(settings):
    """Get which settings apply, from the settings that switch them.

    Args:
        settings (dict): Brow settings (only ROW_KEYS are read).

    Returns:
        dict: {setting key: visible}
    """
    vertex = LOOP_TYPES[settings["loopType"]] == "vertex"
    fixed = bool(settings["fixedJoints"])
    skin = bool(settings["doSkin"])
    center = SIDES[settings.get("side", 0)] == "C"
    return {
        "upvOffset": bool(settings["jointsFollowCurve"]),
        "edgeLoop": not vertex,
        "vertexLoop": vertex,
        "secondaryControls": bool(settings["useSecondary"]),
        "everyNVertex": not fixed,
        "fixedJointsNumber": fixed,
        "rigidLoops": skin,
        "falloffLoops": skin,
        "skinSmooth": skin,
        "hookLeft": center,
        "hookRight": center,
    }


def settings_from_data(data):
    """Get brow settings from loaded ``.brows`` file data, 3.0 or 1.0.

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
        label="Brow Rigger",
        upgrade=legacy_upgrade,
    )


def load_settings(path):
    """Load brow settings from a ``.brows`` file, 3.0 or 1.0.

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
        label="Brow Rigger",
        upgrade=legacy_upgrade,
    )


def save_settings(path, settings):
    """Save brow settings to a ``.brows`` file.

    Args:
        path (str): File path.
        settings (dict): Brow settings.
    """
    settings_schema.save_settings(path, FILE_TYPE, SCHEMA_VERSION, settings)
