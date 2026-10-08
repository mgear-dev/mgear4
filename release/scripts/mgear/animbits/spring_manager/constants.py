"""Spring Manager constants: scene tags, parameter specs and presets."""

from collections import namedtuple

# Scene metadata ---------------------------------------------------------
# network node tag: string attribute holding the backend name
TAG_ATTR = "mgearSpring"
VERSION_ATTR = "mgearSpringVersion"
CONTROLS_ATTR = "controls"
MEMBERS_ATTR = "members"
SETTINGS_ATTR = "settingsNode"
STATE_ATTR = "state"
SCENE_VERSION = 1

NETWORK_SUFFIX = "sprg_net"

# spring states, stored on the network node
STATE_ACTIVE = "active"
STATE_BAKED = "baked"

# Parameters -------------------------------------------------------------
PARAM_FLOAT = "float"
PARAM_INT = "int"
PARAM_BOOL = "bool"
PARAM_VECTOR = "vector"

ParamSpec = namedtuple(
    "ParamSpec",
    (
        "attr",
        "label",
        "default",
        "group",
        "minimum",
        "maximum",
        "soft_maximum",
        "kind",
        "keyable",
        "rig_dependent",
    ),
)


def param(
    attr,
    label,
    default,
    group,
    minimum=0.0,
    maximum=1.0,
    soft_maximum=None,
    kind=PARAM_FLOAT,
    keyable=True,
    rig_dependent=False,
):
    """Return a parameter description.

    Args:
        attr (str): Attribute name on the settings node.
        label (str): UI label.
        default (object): Default value (a tuple for vectors).
        group (str): UI group name.
        minimum (float, optional): Minimum value (per component).
        maximum (float, optional): Maximum value (per component).
        soft_maximum (float, optional): Initial slider maximum.
        kind (str, optional): ``float``, ``int``, ``bool`` or ``vector``.
        keyable (bool, optional): Keyed by "Key All".
        rig_dependent (bool, optional): Depends on the target rig (its
            size, or a display choice): not copied by a values preset.

    Returns:
        ParamSpec: The parameter.
    """
    return ParamSpec(
        attr,
        label,
        default,
        group,
        minimum,
        maximum,
        soft_maximum,
        kind,
        keyable,
        rig_dependent,
    )


# Classic backend --------------------------------------------------------
CLASSIC_BACKEND = "classic"
SEPARATOR_ATTR = "springSettings"
DIRECTION_VIS_ATTR = "springDirectionVis"
DIRECTION_ATTR = "direction"

TOTAL_INTENSITY = "springTotalIntensity"
RIG_SCALE = "springRigScale"
TRANS_INTENSITY = "springTranslationalIntensity"
TRANS_DAMPING = "springTranslationalDamping"
TRANS_STIFFNESS = "springTranslationalStiffness"
ROT_INTENSITY = "springRotationalIntensity"
ROT_DAMPING = "springRotationalDamping"
ROT_STIFFNESS = "springRotationalStiffness"

CLASSIC_PARAMS = (
    param(TOTAL_INTENSITY, "Total Intensity", 1.0, "Global"),
    param(
        RIG_SCALE,
        "Rig Scale",
        1.0,
        "Global",
        maximum=100.0,
        soft_maximum=10.0,
        rig_dependent=True,
    ),
    param(TRANS_INTENSITY, "Intensity", 0.0, "Translation"),
    param(TRANS_DAMPING, "Damping", 0.5, "Translation"),
    param(TRANS_STIFFNESS, "Stiffness", 0.5, "Translation"),
    param(ROT_INTENSITY, "Intensity", 1.0, "Rotation"),
    param(ROT_DAMPING, "Damping", 0.5, "Rotation"),
    param(ROT_STIFFNESS, "Stiffness", 0.5, "Rotation"),
    param(
        DIRECTION_VIS_ATTR,
        "Show Arrow",
        True,
        "Display",
        minimum=False,
        maximum=True,
        kind=PARAM_BOOL,
        keyable=False,
        rig_dependent=True,
    ),
)

# Legacy setups (Spring Manager before 5.4) ------------------------------
LEGACY_BACKEND = "legacy"
LEGACY_MEMBERS_ATTR = "springSetupMembers"
LEGACY_ATTRS = tuple(spec.attr for spec in CLASSIC_PARAMS) + (
    LEGACY_MEMBERS_ATTR,
    "springConfig",
    "springTranslation",
    "springRotation",
)

# Directions -------------------------------------------------------------
AUTO_DIRECTION = "auto"

# direction: (aim/up axis, up vector). The aim channel and sign are
# derived from the direction name, see backends.classic.
DIRECTION_TABLE = {
    "x": ("xy", (0, 1, 0)),
    "y": ("yx", (1, 0, 0)),
    "z": ("zy", (0, 1, 0)),
    "-x": ("-xy", (0, 1, 0)),
    "-y": ("-yx", (1, 0, 0)),
    "-z": ("-zy", (0, 1, 0)),
}
DIRECTIONS = tuple(DIRECTION_TABLE)

# Presets ----------------------------------------------------------------
PRESET_VERSION = 2
PRESET_EXTENSION = ".spg"
THUMBNAIL_EXTENSION = ".png"
THUMBNAIL_SIZE = 256
# preset types: "values" presets only hold parameter values and apply to
# any spring, "rig" presets also hold the controls of a character
PRESET_VALUES = "values"
PRESET_RIG = "rig"
USER_PRESETS_FOLDER = ("mGear", "spring_presets")

# Settings keys ----------------------------------------------------------
SETTINGS_PREFIX = "spring_manager/"
CUSTOM_LIBRARIES_KEY = SETTINGS_PREFIX + "custom_libraries"
