"""Global solver settings of the Bone Dynamics springs.

One ``mgearSpringSolver`` network per scene holds the settings shared by
every boneDynamicsNode: enable, start frame, fps, gravity, ground and
iterations. It is a shared node (kind ``solver``): never deleted with a
spring.
"""

from maya import cmds

from mgear.core import utils

from . import constants
from . import registry

BACKEND = constants.BONE_DYNAMICS_BACKEND
SOLVER_NAME = "mgearSpringSolver"

ENABLE = "enable"
START_FRAME = "startFrame"
FPS = "fps"
GRAVITY = "gravity"
GROUND_ENABLE = "groundEnable"
GROUND_HEIGHT = "groundHeight"
ITERATIONS = "iterations"

# solver attribute: boneDynamicsNode attribute
NODE_CONNECTIONS = (
    (START_FRAME, "resetTime"),
    (FPS, "fps"),
    (GRAVITY, "gravity"),
    (GROUND_ENABLE, "enableGroundCol"),
    (GROUND_HEIGHT, "groundHeight"),
    (ITERATIONS, "iterations"),
)
# settings key: (solver attribute, type) for the scalar settings
SCALAR_SETTINGS = (
    ("enable", ENABLE, bool),
    ("ground_enable", GROUND_ENABLE, bool),
    ("ground_height", GROUND_HEIGHT, float),
    ("iterations", ITERATIONS, int),
)
GRAVITY_CM = 980.0


def _plug(node, attr):
    return "{}.{}".format(node, attr)


def default_gravity():
    """Return the gravity vector for the scene up axis and linear unit.

    Returns:
        tuple: Gravity in scene units per second squared.
    """
    value = -GRAVITY_CM / utils.get_linear_unit_scale()
    return tuple(component * value for component in utils.get_up_vector())


def find_solver():
    """Return the scene solver node.

    Returns:
        str: The solver network node, or None.
    """
    nodes = registry.list_shared(constants.KIND_SOLVER, BACKEND)
    return nodes[0] if nodes else None


def get_solver():
    """Return the scene solver node, creating it when missing.

    Returns:
        str: The solver network node.
    """
    node = find_solver()
    if node:
        return node
    node = registry.create_network(
        SOLVER_NAME, BACKEND, [], None, kind=constants.KIND_SOLVER
    )
    cmds.addAttr(
        node, longName=ENABLE, attributeType="bool", defaultValue=True, keyable=True
    )
    cmds.addAttr(node, longName=START_FRAME, attributeType="time", keyable=True)
    cmds.addAttr(node, longName=FPS, attributeType="double", minValue=1.0, keyable=True)
    cmds.addAttr(node, longName=GRAVITY, attributeType="double3", keyable=True)
    for axis in "XYZ":
        cmds.addAttr(
            node,
            longName=GRAVITY + axis,
            attributeType="double",
            parent=GRAVITY,
            keyable=True,
        )
    cmds.addAttr(node, longName=GROUND_ENABLE, attributeType="bool", keyable=True)
    cmds.addAttr(node, longName=GROUND_HEIGHT, attributeType="double", keyable=True)
    cmds.addAttr(
        node,
        longName=ITERATIONS,
        attributeType="long",
        minValue=0,
        maxValue=10,
        defaultValue=5,
        keyable=True,
    )
    cmds.setAttr(
        _plug(node, START_FRAME), cmds.playbackOptions(query=True, minTime=True)
    )
    cmds.setAttr(_plug(node, GRAVITY), *default_gravity())
    sync_fps(node)
    return node


def sync_fps(node=None):
    """Set the solver fps from the scene time unit.

    Args:
        node (str, optional): Solver node, the scene solver when None.
    """
    node = node or find_solver()
    if node:
        cmds.setAttr(_plug(node, FPS), utils.get_frame_rate() or 24)


def connect(node, bdn_node):
    """Connect the solver settings to a boneDynamicsNode.

    Args:
        node (str): Solver node.
        bdn_node (str): boneDynamicsNode.
    """
    for source, destination in NODE_CONNECTIONS:
        cmds.connectAttr(_plug(node, source), _plug(bdn_node, destination), force=True)


def set_value(attr, value):
    """Set a solver attribute, creating the solver when missing.

    Args:
        attr (str): Solver attribute, e.g. :data:`START_FRAME`.
        value (object): Value. A sequence for the gravity; None components
            are left unchanged.
    """
    node = get_solver()
    if attr == GRAVITY:
        for axis, component in zip("XYZ", value):
            if component is not None:
                cmds.setAttr(_plug(node, GRAVITY + axis), component)
        return
    cmds.setAttr(_plug(node, attr), value)


def get_settings(node=None):
    """Return the solver settings.

    Args:
        node (str, optional): Solver node, the scene solver when None.

    Returns:
        dict: Settings, an empty dict without solver. ``start_frame`` is
        absolute, ``start_offset`` relative to the playback start.
    """
    node = node or find_solver()
    if not node:
        return {}
    settings = {
        key: cast(cmds.getAttr(_plug(node, attr)))
        for key, attr, cast in SCALAR_SETTINGS
    }
    start = cmds.getAttr(_plug(node, START_FRAME))
    settings["start_frame"] = start
    settings["start_offset"] = start - cmds.playbackOptions(query=True, minTime=True)
    settings["gravity"] = list(cmds.getAttr(_plug(node, GRAVITY))[0])
    return settings


def set_settings(settings, node=None):
    """Apply settings from :func:`get_settings`. Missing keys are kept.

    The start frame is applied from ``start_offset``, relative to the
    playback start.

    Args:
        settings (dict): Settings.
        node (str, optional): Solver node, created when missing.
    """
    node = node or get_solver()
    for key, attr, cast in SCALAR_SETTINGS:
        if key in settings:
            cmds.setAttr(_plug(node, attr), cast(settings[key]))
    if "start_offset" in settings:
        cmds.setAttr(
            _plug(node, START_FRAME),
            cmds.playbackOptions(query=True, minTime=True) + settings["start_offset"],
        )
    if "gravity" in settings:
        cmds.setAttr(_plug(node, GRAVITY), *settings["gravity"])


def get_start_frame(node=None):
    """Return the solver start frame.

    Args:
        node (str, optional): Solver node, the scene solver when None.

    Returns:
        float: Start frame, or None without solver.
    """
    node = node or find_solver()
    return cmds.getAttr(_plug(node, START_FRAME)) if node else None


def set_start_frame(frame, node=None):
    """Set the solver start frame (the boneDynamicsNode reset time).

    Args:
        frame (float): Start frame.
        node (str, optional): Solver node, the scene solver when None.
    """
    node = node or find_solver()
    if node:
        cmds.setAttr(_plug(node, START_FRAME), frame)
