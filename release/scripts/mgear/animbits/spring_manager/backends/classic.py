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
from mgear.core import transform
from mgear.core import utils

from . import SpringBackend
from . import clamp
from .. import constants
from .. import registry

SOLVER_PLUGIN = "mgear_solvers"
ROOT_ATTR = "root"
REST_ATTR = "restValues"
MOVED_ATTRS = ("translate", "rotate")
TR_CHANNELS = tuple(attr + axis for attr in MOVED_ATTRS for axis in "XYZ")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _base_name(control):
    """Return a namespace-free name prefix for the nodes of a control.

    Args:
        control (str): Control name.

    Returns:
        str: ``ns:arm_ctl`` gives ``ns_arm_ctl``.
    """
    return control.split("|")[-1].replace(":", "_")


def _plug(node, attr):
    return "{}.{}".format(node, attr)


def _has_input(plug):
    return bool(cmds.listConnections(plug, source=True, destination=False))


def _create(node_type, name, parent=None):
    """Create a DAG node and return its long name.

    Args:
        node_type (str): Node type.
        name (str): Node name.
        parent (str, optional): Parent node.

    Returns:
        str: The long name.
    """
    kwargs = {"parent": parent} if parent else {}
    return cmds.ls(cmds.createNode(node_type, name=name, **kwargs), long=True)[0]


def _aim_channel(direction):
    """Return the aim channel and sign of a direction.

    Args:
        direction (str): One of :data:`constants.DIRECTIONS`.

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
        str: One of :data:`constants.DIRECTIONS`. ``"x"`` when no
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


def _rest_values(control):
    """Return the static translate / rotate values of a control.

    Args:
        control (str): Control name.

    Returns:
        dict: ``{channel: value}`` for channels without input.
    """
    return {
        channel: cmds.getAttr(_plug(control, channel))
        for channel in TR_CHANNELS
        if not _has_input(_plug(control, channel))
    }


def _constraint_skips(control):
    """Return the locked translate / rotate axes of a control.

    Args:
        control (str): Control name.

    Returns:
        tuple: ``(skip_translate, skip_rotate)`` lists of axes.
    """
    unlocked = attribute.get_unlocked_channels(control, MOVED_ATTRS)
    return tuple(
        [axis.lower() for axis in "XYZ" if attr + axis not in unlocked]
        for attr in MOVED_ATTRS
    )


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

    name = constants.CLASSIC_BACKEND
    label = "Classic"
    unavailable_message = (
        "The mgear_solvers plug-in could not be loaded. Check the mGear "
        "installation."
    )
    supports_direction = True

    def is_available(self):
        return utils.is_plugin_available(SOLVER_PLUGIN)

    def param_specs(self):
        return constants.CLASSIC_PARAMS

    # create ---------------------------------------------------------------

    def create(self, controls, params=None, options=None):
        """Create classic springs on controls, in one undo chunk.

        Args:
            controls (list): Control names.
            params (dict, optional): Parameter values.
            options (dict, optional): ``direction``, one of
                :data:`constants.DIRECTIONS` or ``"auto"`` (default).

        Returns:
            list: The created :class:`registry.Spring` records.
        """
        utils.ensure_plugin(SOLVER_PLUGIN)
        values = self.default_params()
        values.update(params or {})
        direction = (options or {}).get("direction") or constants.AUTO_DIRECTION
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
        skips = _constraint_skips(control)
        if len(skips[0]) == 3 and len(skips[1]) == 3:
            mgear.log(
                "{} has locked translate and rotate, skipped".format(control),
                mgear.sev_warning,
            )
            return None

        if direction == constants.AUTO_DIRECTION:
            direction = resolve_direction(control)
        if direction not in constants.DIRECTION_TABLE:
            raise ValueError("Invalid spring direction: {}".format(direction))

        rest = _rest_values(control)
        with utils.capture_created_nodes() as created:
            root = self._build(control, direction, values, skips)
        network = registry.create_network(
            "{}_{}".format(_base_name(control), constants.NETWORK_SUFFIX),
            self.name,
            [control],
            control,
            {constants.DIRECTION_ATTR: direction, REST_ATTR: json.dumps(rest)},
        )
        cmds.addAttr(network, longName=ROOT_ATTR, attributeType="message")
        cmds.connectAttr(root + ".message", _plug(network, ROOT_ATTR))
        registry.add_members(network, created)
        return registry.Spring(network, self.name)

    def _add_settings(self, control, values):
        cmds.addAttr(
            control,
            longName=constants.SEPARATOR_ATTR,
            niceName="__________",
            attributeType="enum",
            enumName="Spring",
        )
        cmds.setAttr(
            _plug(control, constants.SEPARATOR_ATTR),
            channelBox=True,
            keyable=False,
        )
        for spec in self.param_specs():
            plug = _plug(control, spec.attr)
            value = clamp(spec, values.get(spec.attr, spec.default))
            if spec.kind == constants.PARAM_BOOL:
                cmds.addAttr(
                    control,
                    longName=spec.attr,
                    attributeType="bool",
                    defaultValue=spec.default,
                )
            else:
                cmds.addAttr(
                    control,
                    longName=spec.attr,
                    attributeType="float",
                    minValue=spec.minimum,
                    maxValue=spec.maximum,
                    defaultValue=spec.default,
                )
            cmds.setAttr(plug, value)
            if spec.keyable:
                cmds.setAttr(plug, keyable=True)
            else:
                cmds.setAttr(plug, channelBox=True, keyable=False)

    def _build(self, control, direction, values, skips):
        base = _base_name(control)
        aim_channel, sign = _aim_channel(direction)
        aim_axis, up_vector = constants.DIRECTION_TABLE[direction]
        self._add_settings(control, values)
        settings = {spec.attr: _plug(control, spec.attr) for spec in self.param_specs()}

        parent = cmds.listRelatives(control, parent=True, fullPath=True)
        node_type = "joint" if cmds.nodeType(control) == "joint" else "transform"
        root = _create(node_type, base + "_sprg_root", parent[0] if parent else None)
        transform.copy_local_transform(control, root)
        trans = _create("transform", base + "_sprg_trans", root)
        aim = _create("transform", base + "_sprg_aim", trans)
        goal = _create("transform", base + "_sprg_goal", aim)
        driver = _create("transform", base + "_sprg_driver", trans)

        node_utils.createMulNode(
            settings[constants.RIG_SCALE], sign, _plug(aim, aim_channel)
        )

        position_solver = str(applyop.gear_spring_op(trans))
        direction_solver = str(applyop.gear_spring_op(goal))
        for solver, damping, stiffness in (
            (position_solver, constants.TRANS_DAMPING, constants.TRANS_STIFFNESS),
            (direction_solver, constants.ROT_DAMPING, constants.ROT_STIFFNESS),
        ):
            cmds.connectAttr(settings[damping], solver + ".damping")
            cmds.connectAttr(settings[stiffness], solver + ".stiffness")
        node_utils.createMulNode(
            [settings[constants.TOTAL_INTENSITY]] * 2,
            [
                settings[constants.TRANS_INTENSITY],
                settings[constants.ROT_INTENSITY],
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
            cmds.connectAttr(settings[constants.RIG_SCALE], arrow + ".scale" + axis)
        for shape in cmds.listRelatives(arrow, shapes=True, fullPath=True):
            cmds.connectAttr(
                settings[constants.DIRECTION_VIS_ATTR], shape + ".visibility"
            )

        anim_utils.move_animation_curves(control, root, MOVED_ATTRS)

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
        if control:
            if roots and transfer_animation:
                anim_utils.move_animation_curves(roots[0], control, MOVED_ATTRS)
            self._restore_rest_values(network, control)
        members = [node for node in members if cmds.objExists(node)]
        if members:
            cmds.delete(members)
        if control:
            attribute.delete_attrs(
                control,
                [spec.attr for spec in self.param_specs()] + [constants.SEPARATOR_ATTR],
            )
        cmds.delete(network)

    def _restore_rest_values(self, network, control):
        rest = attribute.get_string_attr(network, REST_ATTR)
        if not rest:
            return
        for channel, value in json.loads(rest).items():
            plug = _plug(control, channel)
            if _has_input(plug) or cmds.getAttr(plug, lock=True):
                continue
            cmds.setAttr(plug, value)

    # parameters -----------------------------------------------------------

    def set_enabled(self, springs, enabled):
        self.set_params(springs, {constants.TOTAL_INTENSITY: float(enabled)})

    # bake -----------------------------------------------------------------

    def bake_channels(self, spring):
        control = spring.controls[0]
        settings = spring.settings_node
        attrs = []
        for attr, intensity in (
            ("translate", constants.TRANS_INTENSITY),
            ("rotate", constants.ROT_INTENSITY),
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
                    spring.node, constants.DIRECTION_ATTR, constants.AUTO_DIRECTION
                )
            },
            "params": self.get_params(spring),
        }

    def from_preset(self, entry, controls):
        control = controls[0]
        existing = registry.spring_from_node(control)
        params = entry.get("params") or {}
        if existing:
            if existing.backend != self.name:
                mgear.log(
                    "{} has a {} spring, preset entry skipped".format(
                        control, existing.backend
                    ),
                    mgear.sev_warning,
                )
                return None
            self.set_params([existing], params)
            return existing
        springs = self.create([control], params, entry.get("options"))
        return springs[0] if springs else None
