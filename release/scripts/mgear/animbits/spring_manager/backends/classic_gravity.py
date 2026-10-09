"""Classic Gravity backend: the classic spring rig on ``mgear_springGravityNode``.

Same per-control rig as :mod:`classic` (position and direction springs,
aim driver, arrow), with the gravity spring node. It adds gravity along a
direction, sphere colliders and a ground plane, taken from the shared
colliders (:mod:`colliders`): spheres feed the nodes' ``colliders_list``,
the first plane their ``ground_transform``.
"""

from maya import cmds

from mgear.core import attribute
from mgear.core import node as node_utils
from mgear.core import utils

from . import nodes_of_type
from . import set_param
from .classic import CLASSIC_PARAMS
from .classic import RIG_SCALE
from .classic import ClassicBackend
from .classic import _plug
from .. import colliders
from .. import constants
from .. import registry

CLASSIC_GRAVITY_BACKEND = "classic_gravity"
SOLVER_TYPE = "mgear_springGravityNode"

GRAVITY = "springGravityStrength"
GRAVITY_DIRECTION = "springGravityDirection"
COLLIDE_SOFTNESS = "springCollideSoftness"
USE_GROUND = "springUseGround"

# solver gravity = strength x Rig Scale x GRAVITY_SCALE: the goal sits at
# Rig Scale from the control, so the droop is alike on any rig size
GRAVITY_SCALE = 0.1

GRAVITY_TOOLTIPS = {
    GRAVITY: (
        "How strongly the spring is pulled along the gravity direction, "
        "scaled with the Rig Scale.\n"
        "0: no gravity, a classic spring. 0.5-1: hair, ears, light "
        "pieces. 2-5: heavy, hanging parts (cables, pouches, chains). "
        "Higher values need more Stiffness to keep the shape."
    ),
    GRAVITY_DIRECTION: (
        "Direction of the gravity, in world space. Defaults to the scene "
        "down axis (-Y, or -Z in Z-up scenes).\n"
        "Tilt it for wind-like pulls, e.g. (0.5, -1, 0) for a side breeze."
    ),
    COLLIDE_SOFTNESS: (
        "How softly the assigned sphere colliders and the ground push the "
        "spring out.\n"
        "0: hard, no penetration. 0.5: default, a soft contact. 1: the "
        "colliders have no effect."
    ),
    USE_GROUND: (
        "Keep the spring above the ground: the XZ plane of the assigned "
        "plane collider (or world Y 0 without one). Turned on when a plane "
        "collider is assigned."
    ),
}

GRAVITY_PARAMS = constants.with_tooltips(
    (
        constants.param(
            GRAVITY, "Gravity", 1.0, "Gravity", maximum=100.0, soft_maximum=10.0
        ),
        constants.param(
            GRAVITY_DIRECTION,
            "Direction",
            (0.0, -1.0, 0.0),
            "Gravity",
            minimum=-1.0,
            maximum=1.0,
            kind=constants.PARAM_VECTOR,
            # depends on the scene up axis: not copied by values presets
            rig_dependent=True,
        ),
        constants.param(COLLIDE_SOFTNESS, "Collide Softness", 0.5, "Collision"),
        constants.param(
            USE_GROUND,
            "Use Ground",
            False,
            "Collision",
            minimum=False,
            maximum=True,
            kind=constants.PARAM_BOOL,
        ),
    ),
    GRAVITY_TOOLTIPS,
)

# Use Ground is set by the backend when planes are assigned
USE_GROUND_SPEC = next(spec for spec in GRAVITY_PARAMS if spec.attr == USE_GROUND)


class ClassicGravityBackend(ClassicBackend):
    """Per-control spring using the ``mgear_springGravityNode`` solver."""

    name = CLASSIC_GRAVITY_BACKEND
    label = "Classic Gravity"
    solver_type = SOLVER_TYPE
    # the gravity spring node has sphere colliders and a ground plane
    collider_types = (colliders.SPHERE, colliders.PLANE)

    def param_specs(self):
        # the gravity direction defaults to the scene down axis
        down = tuple(-component for component in utils.get_up_vector())
        return CLASSIC_PARAMS + tuple(
            spec._replace(default=down) if spec.attr == GRAVITY_DIRECTION else spec
            for spec in GRAVITY_PARAMS
        )

    def _connect_solvers(self, settings, solvers):
        gravity = str(node_utils.createMulNode(settings[GRAVITY], settings[RIG_SCALE]))
        # one channel per solver: createMulNode pairs outputs with X, Y, Z
        node_utils.createMulNode(
            [gravity + ".outputX"] * len(solvers),
            [GRAVITY_SCALE] * len(solvers),
            [solver + ".gravity" for solver in solvers],
        )
        for solver in solvers:
            # gravity_direction is not storable: the connection keeps it
            cmds.connectAttr(settings[GRAVITY_DIRECTION], solver + ".gravity_direction")
            cmds.connectAttr(settings[COLLIDE_SOFTNESS], solver + ".collide_softness")
            cmds.connectAttr(settings[USE_GROUND], solver + ".use_ground")

    # shared colliders ------------------------------------------------------

    def shared_changed(self, spring, kind):
        if kind == constants.KIND_COLLIDER:
            self._connect_colliders(spring)

    def _connect_colliders(self, spring):
        """Rewire the sphere colliders and the ground of a spring's nodes.

        Spheres feed ``colliders_list`` (world position and radius); the
        first plane is the ground and turns Use Ground on.

        Args:
            spring (registry.Spring): The spring.
        """
        solvers = nodes_of_type(spring, SOLVER_TYPE)
        by_type = {}
        for network in colliders.usable(
            registry.shared_of(spring, constants.KIND_COLLIDER)
        ):
            by_type.setdefault(colliders.collider_type(network), []).append(network)
        spheres = by_type.get(colliders.SPHERE, [])
        planes = by_type.get(colliders.PLANE, [])
        for solver in solvers:
            attribute.clear_multi(solver + ".colliders_list")
            for index, network in enumerate(spheres):
                item = "{}.colliders_list[{}]".format(solver, index)
                cmds.connectAttr(colliders.world_position(network), item + ".collider")
                cmds.connectAttr(
                    _plug(colliders.dimension_node(network), "radius"),
                    item + ".collide_radius",
                )
            ground = solver + ".ground_transform"
            attribute.disconnect_plug_inputs(ground)
            if planes:
                cmds.connectAttr(
                    colliders.collider_transform(planes[0]) + ".worldMatrix[0]", ground
                )
        set_param(
            _plug(spring.settings_node, USE_GROUND), USE_GROUND_SPEC, bool(planes)
        )
