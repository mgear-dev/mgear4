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
        "tooltip",
    ),
)


def with_tooltips(specs, tooltips):
    """Return parameter descriptions with their tooltips set.

    Args:
        specs (tuple): :class:`ParamSpec` items.
        tooltips (dict): ``{attr: tooltip}``. Missing attributes keep
            their tooltip.

    Returns:
        tuple: The parameters.
    """
    return tuple(
        spec._replace(tooltip=tooltips.get(spec.attr, spec.tooltip)) for spec in specs
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
    tooltip="",
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
        tooltip (str, optional): What the parameter does and typical
            values, one paragraph per line.

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
        tooltip,
    )


# Settings and rest values shared by the backends --------------------------
SEPARATOR_ATTR = "springSettings"
REST_ATTR = "restValues"
MOVED_ATTRS = ("translate", "rotate")
TR_CHANNELS = tuple(attr + axis for attr in MOVED_ATTRS for axis in "XYZ")

BONE_DYNAMICS_BACKEND = "bone_dynamics"

# Legacy setups (Spring Manager before 5.4) ------------------------------
LEGACY_BACKEND = "legacy"
LEGACY_MEMBERS_ATTR = "springSetupMembers"

# Scene node kinds: only "spring" networks are listed as springs, the
# others are shared nodes never deleted with a spring
KIND_ATTR = "mgearSpringKind"
KIND_SPRING = "spring"
KIND_SOLVER = "solver"
KIND_WIND = "wind"
KIND_COLLIDER = "collider"

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
