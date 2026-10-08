"""Classic backend: one ``mgear_springNode`` rig per control.

Rig built under the control's parent::

    <ctl>_sprg_root          receives the control animation
      <ctl>_sprg_trans       position spring
        <ctl>_sprg_aim       offset along the spring direction
          <ctl>_sprg_goal    direction spring
        <ctl>_sprg_driver    aims at the goal, drives the control
          <ctl>_sprg_arrow   direction display
"""

import json

from maya import cmds
import maya.api.OpenMaya as om2

import mgear
from mgear.core import anim_utils
from mgear.core import applyop
from mgear.core import attribute
from mgear.core import icon
from mgear.core import node as node_utils
from mgear.core import node_remap
from mgear.core import transform
from mgear.core import utils
from mgear.core.node import create_dag_node

from . import SpringBackend
from . import add_settings
from . import constraint_skips
from . import remove_settings
from . import rest_values
from . import restore_rest_values
from .. import constants
from .. import registry

# Constants --------------------------------------------------------
CLASSIC_BACKEND = "classic"
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
    constants.param(TOTAL_INTENSITY, "Total Intensity", 1.0, "Global"),
    constants.param(
        RIG_SCALE,
        "Rig Scale",
        1.0,
        "Global",
        maximum=100.0,
        soft_maximum=10.0,
        rig_dependent=True,
    ),
    constants.param(TRANS_INTENSITY, "Intensity", 0.0, "Translation"),
    constants.param(TRANS_DAMPING, "Damping", 0.5, "Translation"),
    constants.param(TRANS_STIFFNESS, "Stiffness", 0.5, "Translation"),
    constants.param(ROT_INTENSITY, "Intensity", 1.0, "Rotation"),
    constants.param(ROT_DAMPING, "Damping", 0.5, "Rotation"),
    constants.param(ROT_STIFFNESS, "Stiffness", 0.5, "Rotation"),
    constants.param(
        DIRECTION_VIS_ATTR,
        "Show Arrow",
        True,
        "Display",
        minimum=False,
        maximum=True,
        kind=constants.PARAM_BOOL,
        keyable=False,
        rig_dependent=True,
    ),
)

CLASSIC_TOOLTIPS = {
    TOTAL_INTENSITY: (
        "Master blend between the animation (0) and the spring (1).\n"
        "1: full spring. 0.5: half the overlap, handy to tone down a "
        "shot without retuning. Key it to fade the spring in or out."
    ),
    RIG_SCALE: (
        "Scales the spring to the size of the rig, so the same values "
        "behave alike on small and big characters.\n"
        "1: rig at the default size. 10: a rig ten times bigger. Not "
        "copied by values presets."
    ),
    TRANS_INTENSITY: (
        "How much the spring moves the control position (follow "
        "through in translation).\n"
        "0: rotation only, the usual choice for tails, hair and "
        "antennas. 0.2-0.5: jiggle (belly, cheeks, pouches)."
    ),
    TRANS_DAMPING: (
        "How fast the translation bounce dies out.\n"
        "0.2: wobbly, keeps bouncing (jelly). 0.5: balanced. 0.8: one "
        "soft overshoot and settles."
    ),
    TRANS_STIFFNESS: (
        "How strongly the position is pulled back to the animation.\n"
        "0.2: slow, heavy lag. 0.5: balanced. 0.8: tight, small and "
        "fast jiggle."
    ),
    ROT_INTENSITY: (
        "How much the spring rotates the control (overlap and follow "
        "through).\n"
        "1: full overlap for tails, hair and ears. 0.5-0.7: subtle "
        "secondary motion (clothes, straps)."
    ),
    ROT_DAMPING: (
        "How fast the rotation swing dies out.\n"
        "0.2: floppy, swings several times (floppy ears, ribbons). "
        "0.5: natural (hair, tails). 0.7+: settles quickly (stiff "
        "appendages)."
    ),
    ROT_STIFFNESS: (
        "How strongly the rotation is pulled back to the animation.\n"
        "0.15: loose, big lag (Floppy). 0.3: natural (Soft, Tail). "
        "0.8: tight, small fast overlap (Stiff, antennas)."
    ),
    DIRECTION_VIS_ATTR: (
        "Shows the arrow of the spring aim direction in the viewport. "
        "Display only, not keyed."
    ),
}
CLASSIC_PARAMS = constants.with_tooltips(CLASSIC_PARAMS, CLASSIC_TOOLTIPS)

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

SOLVER_PLUGIN = "mgear_solvers"
ROOT_ATTR = "root"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _plug(node, attr):
    return "{}.{}".format(node, attr)


def _aim_channel(direction):
    """Return the aim channel and sign of a direction.

    Args:
        direction (str): One of :data:`DIRECTIONS`.

    Returns:
        tuple: ``("translateX", -1)`` for ``"-x"``.
    """
    return "translate" + direction[-1].upper(), -1 if direction[0] == "-" else 1


def resolve_direction(control):
    """Return the spring direction pointing along a control's chain.

    Uses the local position of the first transform child. Without child,
    uses the direction from the parent to the control, in control space.

    Args:
        control (str): Control name.

    Returns:
        str: One of :data:`DIRECTIONS`. ``"x"`` when no
        direction can be found.
    """
    children = (
        cmds.listRelatives(control, children=True, type="transform", fullPath=True)
        or []
    )
    vector = None
    for child in children:
        if cmds.listRelatives(child, shapes=True):
            # skip curves / meshes parented under the control
            continue
        vector = om2.MVector(cmds.getAttr(child + ".translate")[0])
        if vector.length() > 1e-6:
            break
        vector = None

    if vector is None:
        parent = cmds.listRelatives(control, parent=True, fullPath=True)
        if parent:
            start = om2.MPoint(
                cmds.xform(parent[0], query=True, worldSpace=True, translation=True)
            )
            matrix = om2.MMatrix(
                cmds.xform(control, query=True, worldSpace=True, matrix=True)
            )
            end = om2.MPoint(matrix[12], matrix[13], matrix[14])
            vector = (end - start) * matrix.inverse()

    if vector is None or vector.length() < 1e-6:
        mgear.log(
            "Can't find a direction for {}, using x".format(control),
            mgear.sev_warning,
        )
        return "x"

    values = (vector.x, vector.y, vector.z)
    index = max(range(3), key=lambda i: abs(values[i]))
    axis = "xyz"[index]
    return axis if values[index] > 0 else "-" + axis


def _delete_constraints(members):
    """Delete the parent constraints among the members of a setup.

    Args:
        members (list): Member node names.
    """
    constraints = [
        node
        for node in members
        if cmds.objExists(node) and cmds.nodeType(node) == "parentConstraint"
    ]
    if constraints:
        cmds.delete(constraints)


# -----------------------------------------------------------------------------
# Backend
# -----------------------------------------------------------------------------


class ClassicBackend(SpringBackend):
    """Per-control spring using the ``mgear_springNode`` solver."""

    name = CLASSIC_BACKEND
    label = "Classic"
    unavailable_message = (
        "The mgear_solvers plug-in could not be loaded. Check the mGear "
        "installation."
    )

    def is_available(self):
        return utils.is_plugin_available(SOLVER_PLUGIN)

    def param_specs(self):
        return CLASSIC_PARAMS

    # create ---------------------------------------------------------------

    def create(self, controls, params=None, options=None):
        """Create classic springs on controls, in one undo chunk.

        Args:
            controls (list): Control names.
            params (dict, optional): Parameter values.
            options (dict, optional): ``direction``, one of
                :data:`DIRECTIONS` or ``"auto"`` (default).

        Returns:
            list: The created :class:`registry.Spring` records.
        """
        utils.ensure_plugin(SOLVER_PLUGIN)
        values = self.default_params()
        values.update(params or {})
        direction = (options or {}).get("direction") or AUTO_DIRECTION
        springs = []
        with utils.undo_chunk("springManagerCreate"):
            for control in controls:
                spring = self._create_one(control, values, direction)
                if spring:
                    springs.append(spring)
        return springs

    def _create_one(self, control, values, direction):
        if not cmds.objExists(control) or not cmds.objectType(
            control, isAType="transform"
        ):
            mgear.log(
                "{} is not a transform, skipped".format(control),
                mgear.sev_warning,
            )
            return None
        if registry.spring_from_node(control):
            mgear.log(
                "{} already has a spring, skipped".format(control),
                mgear.sev_warning,
            )
            return None
        skips = constraint_skips(control)
        if len(skips[0]) == 3 and len(skips[1]) == 3:
            mgear.log(
                "{} has locked translate and rotate, skipped".format(control),
                mgear.sev_warning,
            )
            return None

        if direction == AUTO_DIRECTION:
            direction = resolve_direction(control)
        if direction not in DIRECTION_TABLE:
            raise ValueError("Invalid spring direction: {}".format(direction))

        rest = rest_values([control])
        with utils.capture_created_nodes() as created:
            root = self._build(control, direction, values, skips)
        network = registry.create_network(
            "{}_{}".format(node_remap.flat_name(control), constants.NETWORK_SUFFIX),
            self.name,
            [control],
            control,
            {DIRECTION_ATTR: direction, constants.REST_ATTR: json.dumps(rest)},
        )
        cmds.addAttr(network, longName=ROOT_ATTR, attributeType="message")
        cmds.connectAttr(root + ".message", _plug(network, ROOT_ATTR))
        registry.add_members(network, created)
        return registry.Spring(network, self.name)

    def _build(self, control, direction, values, skips):
        base = node_remap.flat_name(control)
        aim_channel, sign = _aim_channel(direction)
        aim_axis, up_vector = DIRECTION_TABLE[direction]
        add_settings(control, self.param_specs(), values)
        settings = {spec.attr: _plug(control, spec.attr) for spec in self.param_specs()}

        parent = cmds.listRelatives(control, parent=True, fullPath=True)
        node_type = "joint" if cmds.nodeType(control) == "joint" else "transform"
        root = create_dag_node(
            node_type, base + "_sprg_root", parent[0] if parent else None
        )
        transform.copy_local_transform(control, root)
        trans = create_dag_node("transform", base + "_sprg_trans", root)
        aim = create_dag_node("transform", base + "_sprg_aim", trans)
        goal = create_dag_node("transform", base + "_sprg_goal", aim)
        driver = create_dag_node("transform", base + "_sprg_driver", trans)

        node_utils.createMulNode(settings[RIG_SCALE], sign, _plug(aim, aim_channel))

        position_solver = str(applyop.gear_spring_op(trans))
        direction_solver = str(applyop.gear_spring_op(goal))
        for solver, damping, stiffness in (
            (position_solver, TRANS_DAMPING, TRANS_STIFFNESS),
            (direction_solver, ROT_DAMPING, ROT_STIFFNESS),
        ):
            cmds.connectAttr(settings[damping], solver + ".damping")
            cmds.connectAttr(settings[stiffness], solver + ".stiffness")
        node_utils.createMulNode(
            [settings[TOTAL_INTENSITY]] * 2,
            [
                settings[TRANS_INTENSITY],
                settings[ROT_INTENSITY],
            ],
            [position_solver + ".intensity", direction_solver + ".intensity"],
        )

        applyop.aimCns(driver, goal, aim_axis, "objectrotation", list(up_vector), trans)

        arrow = str(
            icon.direction_arrow(
                axis=direction, name=base + "_sprg_arrow", parent_name=driver
            )
        )
        cmds.xform(arrow, objectSpace=True, translation=(0, 0, 0), rotation=(0, 0, 0))
        cmds.setAttr(arrow + ".overrideEnabled", 1)
        cmds.setAttr(arrow + ".overrideDisplayType", 1)
        for axis in "XYZ":
            cmds.connectAttr(settings[RIG_SCALE], arrow + ".scale" + axis)
        for shape in cmds.listRelatives(arrow, shapes=True, fullPath=True):
            cmds.connectAttr(settings[DIRECTION_VIS_ATTR], shape + ".visibility")

        anim_utils.move_animation_curves(control, root, constants.MOVED_ATTRS)

        constraint = cmds.parentConstraint(
            driver,
            control,
            maintainOffset=False,
            skipTranslate=skips[0] or "none",
            skipRotate=skips[1] or "none",
        )[0]
        cmds.setAttr(constraint + ".isHistoricallyInteresting", False)
        return root

    # delete ---------------------------------------------------------------

    def detach(self, spring):
        _delete_constraints(spring.members)

    def delete(self, spring, transfer_animation=True):
        network = spring.node
        controls = spring.controls
        control = controls[0] if controls else None
        members = spring.members
        roots = attribute.get_message_inputs(network, ROOT_ATTR)
        if spring.state == constants.STATE_BAKED:
            transfer_animation = False

        # the control constraint first, to avoid offsets
        _delete_constraints(members)
        if control and roots and transfer_animation:
            anim_utils.move_animation_curves(roots[0], control, constants.MOVED_ATTRS)
        restore_rest_values(network)
        registry.delete_members(network, members)
        if control:
            remove_settings(control, self.param_specs())
        if cmds.objExists(network):
            cmds.delete(network)

    # parameters -----------------------------------------------------------

    def set_enabled(self, springs, enabled):
        self.set_params(springs, {TOTAL_INTENSITY: float(enabled)})

    # bake -----------------------------------------------------------------

    def bake_channels(self, spring):
        control = spring.controls[0]
        settings = spring.settings_node
        attrs = []
        for attr, intensity in (
            ("translate", TRANS_INTENSITY),
            ("rotate", ROT_INTENSITY),
        ):
            plug = _plug(settings, intensity)
            if cmds.getAttr(plug) > 0 or anim_utils.is_animated(plug):
                attrs.append(attr)
        channels = attribute.get_unlocked_channels(control, attrs) if attrs else []
        return {control: channels}

    # presets --------------------------------------------------------------

    def to_preset(self, spring):
        return {
            "backend": self.name,
            "controls": spring.controls,
            "options": {
                "direction": attribute.get_string_attr(
                    spring.node, DIRECTION_ATTR, AUTO_DIRECTION
                )
            },
            "params": self.get_params(spring),
        }

    def from_preset(self, entry, controls):
        params = entry.get("params") or {}
        handled, spring = self.update_existing(controls[0], params)
        if handled:
            return spring
        springs = self.create([controls[0]], params, entry.get("options"))
        return springs[0] if springs else None
