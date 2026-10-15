"""Spring backends: the interface and the backend registry.

A backend builds and drives one kind of spring setup (classic mGear
spring, boneDynamicsNode chains, ...). The UI, presets and bake code
only talk to backends through :class:`SpringBackend`.
"""

import json
from collections import OrderedDict

from maya import cmds

import mgear
from mgear.core import anim_utils
from mgear.core import attribute
from mgear.core import utils

from .. import constants

_BACKENDS = OrderedDict()


class SpringBackend(object):
    """Base class of the spring backends.

    Attributes:
        name (str): Unique name, stored in the scene and in presets.
        label (str): Display name.
        unavailable_message (str): Tooltip shown when the backend can not
            be used.
        read_only_message (str): Shown in the parameter panel for springs
            of a non editable backend.
        hidden (bool): Not offered in the solver menu (e.g. legacy).
        editable (bool): Parameters can be edited and saved in presets.
    """

    name = ""
    label = ""
    unavailable_message = ""
    read_only_message = ""
    hidden = False
    editable = True
    # collider types its springs can use, see colliders.TYPES
    collider_types = ()
    # its springs have a bone volume that colliders on their nodes can set
    bone_volume = False

    def is_available(self):
        """Return True if the backend can be used in this session.

        Must never raise.

        Returns:
            bool: True if available.
        """
        return True

    def param_specs(self):
        """Return the parameters of the backend.

        Returns:
            tuple: :class:`constants.ParamSpec` items.
        """
        return ()

    def default_params(self):
        """Return the default parameter values.

        Returns:
            dict: ``{attr: default}``.
        """
        return {spec.attr: spec.default for spec in self.param_specs()}

    def param_plugs(self, spring):
        """Return the plugs holding the parameters of a spring.

        The default is one attribute per parameter on the settings node.
        Backends whose parameters fan out to several nodes still return
        the plug the animator edits and keys.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            dict: ``{attr: plug}``.
        """
        settings = spring.settings_node
        return {
            spec.attr: "{}.{}".format(settings, spec.attr)
            for spec in self.param_specs()
        }

    def create(self, controls, params=None, options=None):
        """Create spring setups on controls.

        Args:
            controls (list): Control names.
            params (dict, optional): Parameter values, defaults when None.
            options (dict, optional): Backend specific options.

        Returns:
            list: The created :class:`registry.Spring` records.
        """
        raise NotImplementedError

    def delete(self, spring, transfer_animation=True):
        """Delete a spring setup. Called inside an undo chunk.

        Args:
            spring (registry.Spring): The spring.
            transfer_animation (bool, optional): Give the animation back
                to the controls.
        """
        raise NotImplementedError

    def detach(self, spring):
        """Stop a spring from driving its controls, keeping the setup.

        Called after a bake that keeps the springs.

        Args:
            spring (registry.Spring): The spring.
        """
        raise NotImplementedError

    def get_params(self, spring):
        """Return the parameter values of a spring.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            dict: ``{attr: value}``. Vectors are tuples.
        """
        values = {}
        for attr, plug in self.param_plugs(spring).items():
            try:
                value = cmds.getAttr(plug)
            except ValueError:
                continue
            # compound attributes come back as [(x, y, z)]
            values[attr] = tuple(value[0]) if isinstance(value, list) else value
        return values

    def set_params(self, springs, values):
        """Set parameter values on springs, in one undo chunk.

        Values are clamped to the parameter range. Animated parameters are
        keyed at the current time.

        Args:
            springs (list): :class:`registry.Spring` records.
            values (dict): ``{attr: value}``. Unknown attributes are
                ignored.
        """
        specs = {spec.attr: spec for spec in self.param_specs()}
        with utils.undo_chunk("springManagerSetParams"):
            for spring in springs:
                plugs = self.param_plugs(spring)
                for attr, value in values.items():
                    spec = specs.get(attr)
                    if spec and attr in plugs:
                        set_param(plugs[attr], spec, value)

    def set_enabled(self, springs, enabled):
        """Turn springs on or off.

        Args:
            springs (list): :class:`registry.Spring` records.
            enabled (bool): True to turn on.
        """
        raise NotImplementedError

    def bake_channels(self, spring):
        """Return the channels a bake must key for a spring.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            dict: ``{node: [attr, ...]}``.
        """
        raise NotImplementedError

    def prepare_bake(self, springs, start):
        """Get springs ready to be simulated from a frame before baking.

        The default does nothing: the solver runs from any frame. Solvers
        with their own start frame set it here.

        Args:
            springs (list): :class:`registry.Spring` records of this backend.
            start (float): First evaluated frame, pre-roll included.
        """

    def finish_bake(self, springs):
        """Restore what :meth:`prepare_bake` changed.

        Args:
            springs (list): :class:`registry.Spring` records of this backend.
        """

    def param_warnings(self, springs, values):
        """Return warnings about parameter values, shown in the panel.

        Args:
            springs (list): :class:`registry.Spring` records.
            values (list): Their parameter values, from :meth:`get_params`.

        Returns:
            list: Warning strings.
        """
        return []

    def update_existing(self, control, params):
        """Update the spring already on a control, for preset application.

        Args:
            control (str): Control name.
            params (dict): Parameter values.

        Returns:
            tuple: ``(handled, spring)``. ``handled`` is True when the
            control already has a spring: it is updated when it is of this
            backend (``spring``), skipped otherwise (``spring`` is None).
        """
        from .. import registry

        existing = registry.spring_from_node(control)
        if not existing:
            return False, None
        if existing.backend != self.name:
            mgear.log(
                "{} has a {} spring, preset entry skipped".format(
                    control, existing.backend
                ),
                mgear.sev_warning,
            )
            return True, None
        self.set_params([existing], params)
        return True, existing

    def accepts_shared(self, spring, shared):
        """Return True if a shared node can be assigned to a spring.

        Args:
            spring (registry.Spring): The spring.
            shared (str): Shared network node.

        Colliders are refused, with a warning, when their type is outside
        :attr:`collider_types`, or when they follow the spring itself
        (driven by one of its nodes, its controls or a child of its
        controls): the spring would push its own collider, a cycle.

        Returns:
            bool: True when the spring can use it.
        """
        from .. import colliders
        from .. import registry

        if registry.node_kind(shared) != constants.KIND_COLLIDER:
            return True
        kind_type = colliders.collider_type(shared)
        if kind_type not in self.collider_types:
            reason = "{} colliders are not used by {} springs".format(
                kind_type, self.label
            )
        elif follows_spring(spring, colliders.driver(shared)):
            reason = "it follows the spring itself"
        else:
            return True
        mgear.log(
            "{}: {}, not assigned to {}".format(
                colliders.label(shared), reason, spring.label
            ),
            mgear.sev_warning,
        )
        return False

    def link_collider(self, network):
        """Let a collider driven by a node of a spring set its volume.

        Called when a collider is created on a node of one of this
        backend's springs. The default does nothing.

        Args:
            network (str): Collider network.

        Returns:
            bool: True when the collider drives the spring volume.
        """
        return False

    def unlink_collider(self, network):
        """Undo :meth:`link_collider` before a collider is deleted.

        Args:
            network (str): Collider network.
        """

    def shared_changed(self, spring, kind):
        """Rewire the shared nodes of a kind (wind, colliders) of a spring.

        Called by the registry after assignments change, once per spring
        and kind in a batch. The default does nothing.

        Args:
            spring (registry.Spring): The spring.
            kind (str): Shared kind, e.g. :data:`constants.KIND_COLLIDER`.
        """

    def get_solver_settings(self):
        """Return the scene-wide solver settings saved in rig presets.

        Returns:
            dict: Settings, empty when the backend has none.
        """
        return {}

    def set_solver_settings(self, settings):
        """Apply solver settings from a rig preset.

        Args:
            settings (dict): Settings from :meth:`get_solver_settings`.
        """

    def to_preset(self, spring):
        """Return the preset ``springs`` entry describing a spring.

        Control names are returned as in the scene; namespaces are
        stripped by the preset module.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            dict: ``{"backend", "controls", "options", "params"}``.
        """
        raise NotImplementedError

    def from_preset(self, entry, controls):
        """Create or update a spring from a preset entry.

        Args:
            entry (dict): Preset ``springs`` entry.
            controls (list): Resolved control names in the scene.

        Returns:
            registry.Spring: The created or updated spring, or None.
        """
        raise NotImplementedError

    def preset_extras(self, spring):
        """Return data of a spring saved in preset entries besides values.

        Saved in rig and values presets, e.g. a radius profile.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            dict: Entry keys and values, empty by default.
        """
        return {}

    def apply_preset_extras(self, springs, entry):
        """Apply the :meth:`preset_extras` data of a preset entry to springs.

        Args:
            springs (list): :class:`registry.Spring` records.
            entry (dict): Preset ``springs`` entry.
        """


# -----------------------------------------------------------------------------
# Parameter values
# -----------------------------------------------------------------------------


def clamp(spec, value):
    """Clamp a value to a parameter range and type.

    Args:
        spec (constants.ParamSpec): The parameter.
        value (object): Value. A sequence for vectors.

    Returns:
        object: The clamped value.
    """
    if spec.kind == constants.PARAM_BOOL:
        return bool(value)
    if spec.kind == constants.PARAM_VECTOR:
        # None components (mixed in the UI) are kept as None: unchanged
        return tuple(
            None if v is None else max(spec.minimum, min(spec.maximum, v))
            for v in value
        )
    value = max(spec.minimum, min(spec.maximum, value))
    return int(round(value)) if spec.kind == constants.PARAM_INT else value


def values_differ(values, tolerance=1e-5):
    """Return True if parameter values are not all the same.

    Args:
        values (list): Values of one parameter, numbers or sequences.
        tolerance (float, optional): Largest difference seen as equal.

    Returns:
        bool: True when at least two values differ.
    """
    first = values[0]
    for value in values[1:]:
        pairs = (
            zip(first, value) if isinstance(first, (list, tuple)) else ((first, value),)
        )
        if any(abs(a - b) > tolerance for a, b in pairs):
            return True
    return False


def set_param(plug, spec, value):
    """Set a parameter plug, keying it when animated.

    Args:
        plug (str): Plug name.
        spec (constants.ParamSpec): The parameter.
        value (object): New value, clamped to the parameter range.

    Returns:
        bool: True if the value was set or keyed.
    """
    value = clamp(spec, value)
    if spec.kind == constants.PARAM_VECTOR:
        children = cmds.attributeQuery(
            plug.split(".", 1)[1], node=plug.split(".")[0], listChildren=True
        )
        return all(
            anim_utils.set_or_key("{}.{}".format(plug.split(".")[0], child), v)
            for child, v in zip(children, value)
            if v is not None
        )
    return anim_utils.set_or_key(plug, value)


# -----------------------------------------------------------------------------
# Settings attributes and rest values
# -----------------------------------------------------------------------------

_ATTRIBUTE_TYPES = {constants.PARAM_BOOL: "bool", constants.PARAM_INT: "long"}


def follows_spring(spring, node):
    """Return True if a node is moved by a spring.

    The spring's nodes, its controls and their children move with the
    spring.

    Args:
        spring (registry.Spring): The spring.
        node (str): Node name, or None.

    Returns:
        bool: True when the node follows the spring.
    """
    if not node or not cmds.objExists(node):
        return False
    path = cmds.ls(node, long=True)[0]
    if path in set(cmds.ls(spring.members, long=True)):
        return True
    return any(
        path == control or path.startswith(control + "|")
        for control in cmds.ls(spring.controls, long=True)
    )


def nodes_of_type(spring, node_type, members=None):
    """Return the members of a spring of a node type.

    Args:
        spring (registry.Spring): The spring.
        node_type (str): Node type.
        members (list, optional): Members already read from the spring.

    Returns:
        list: Node names.
    """
    nodes = members if members is not None else spring.members
    return cmds.ls(nodes, type=node_type) or [] if nodes else []


def add_settings(control, specs, values):
    """Add the parameter attributes of a spring to its settings control.

    A separator enum is added first. Keyable parameters are keyable, the
    others are shown in the channel box.

    Args:
        control (str): Settings control.
        specs (tuple): :class:`constants.ParamSpec` items.
        values (dict): ``{attr: value}``, defaults for missing ones.
    """
    if not cmds.attributeQuery(constants.SEPARATOR_ATTR, node=control, exists=True):
        cmds.addAttr(
            control,
            longName=constants.SEPARATOR_ATTR,
            niceName="__________",
            attributeType="enum",
            enumName="Spring",
        )
        cmds.setAttr(
            "{}.{}".format(control, constants.SEPARATOR_ATTR),
            channelBox=True,
            keyable=False,
        )
    for spec in specs:
        if spec.kind == constants.PARAM_VECTOR:
            _add_vector_setting(control, spec, values.get(spec.attr, spec.default))
            continue
        kwargs = {}
        if spec.kind != constants.PARAM_BOOL:
            kwargs = {"minValue": spec.minimum, "maxValue": spec.maximum}
            if spec.soft_maximum is not None:
                kwargs["softMaxValue"] = spec.soft_maximum
        cmds.addAttr(
            control,
            longName=spec.attr,
            attributeType=_ATTRIBUTE_TYPES.get(spec.kind, "double"),
            defaultValue=spec.default,
            **kwargs
        )
        plug = "{}.{}".format(control, spec.attr)
        cmds.setAttr(plug, clamp(spec, values.get(spec.attr, spec.default)))
        if spec.keyable:
            cmds.setAttr(plug, keyable=True)
        else:
            cmds.setAttr(plug, keyable=False, channelBox=True)


def _add_vector_setting(control, spec, value):
    """Add a vector parameter: a double3 with keyable X, Y, Z children.

    Args:
        control (str): Settings control.
        spec (constants.ParamSpec): A :data:`constants.PARAM_VECTOR` spec.
        value (tuple): Initial value.
    """
    cmds.addAttr(control, longName=spec.attr, attributeType="double3")
    for axis, default in zip("XYZ", spec.default):
        cmds.addAttr(
            control,
            longName=spec.attr + axis,
            attributeType="double",
            parent=spec.attr,
            defaultValue=default,
        )
    for axis, component in zip("XYZ", clamp(spec, value)):
        plug = "{}.{}{}".format(control, spec.attr, axis)
        cmds.setAttr(plug, component)
        cmds.setAttr(plug, keyable=spec.keyable, channelBox=not spec.keyable)


def constraint_skips(node):
    """Return the locked translate / rotate axes of a node, for constraints.

    Args:
        node (str): Constrained node.

    Returns:
        tuple: ``(skip_translate, skip_rotate)`` lists of axes ("x"...).
    """
    unlocked = attribute.get_unlocked_channels(node, constants.MOVED_ATTRS)
    return tuple(
        [axis.lower() for axis in "XYZ" if attr + axis not in unlocked]
        for attr in constants.MOVED_ATTRS
    )


def remove_settings(control, specs):
    """Remove the parameter attributes and separator from a control.

    Args:
        control (str): Settings control.
        specs (tuple): :class:`constants.ParamSpec` items.
    """
    attribute.delete_attrs(
        control, [spec.attr for spec in specs] + [constants.SEPARATOR_ATTR]
    )


def rest_values(controls):
    """Return the static translate / rotate values of controls.

    Args:
        controls (list): Control names.

    Returns:
        dict: ``{control: {channel: value}}`` for channels without input.
    """
    return {
        control: {
            channel: cmds.getAttr("{}.{}".format(control, channel))
            for channel in constants.TR_CHANNELS
            if not attribute.has_input("{}.{}".format(control, channel))
        }
        for control in controls
    }


def restore_rest_values(network):
    """Give the controls of a spring their static values back.

    Channels that are connected or locked are left unchanged.

    Args:
        network (str): Spring network holding :data:`constants.REST_ATTR`.
    """
    rest = json.loads(attribute.get_string_attr(network, constants.REST_ATTR) or "{}")
    for control, channels in rest.items():
        if not isinstance(channels, dict):
            # older format, before the values were stored per control
            continue
        for channel, value in channels.items():
            plug = "{}.{}".format(control, channel)
            if not attribute.has_input(plug) and not cmds.getAttr(plug, lock=True):
                cmds.setAttr(plug, value)


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------


def register_backend(backend):
    """Register a backend instance, replacing one with the same name.

    Args:
        backend (SpringBackend): The backend.
    """
    _BACKENDS[backend.name] = backend


def get_backends(include_hidden=False):
    """Return the registered backends, in registration order.

    Args:
        include_hidden (bool, optional): Include hidden backends (legacy).

    Returns:
        list: :class:`SpringBackend` instances.
    """
    _register_builtin()
    return [
        backend
        for backend in _BACKENDS.values()
        if include_hidden or not backend.hidden
    ]


def get_backend(name):
    """Return a registered backend by name.

    Args:
        name (str): Backend name.

    Returns:
        SpringBackend: The backend, or None.
    """
    _register_builtin()
    return _BACKENDS.get(name)


def editable_springs(springs):
    """Return the springs whose backend is registered and editable.

    Args:
        springs (list): :class:`registry.Spring` records.

    Returns:
        list: ``(spring, backend)`` tuples.
    """
    pairs = []
    for spring in springs:
        backend = get_backend(spring.backend)
        if backend and backend.editable:
            pairs.append((spring, backend))
    return pairs


def _register_builtin():
    if _BACKENDS:
        return
    from . import bone_dynamics
    from . import classic
    from . import classic_gravity
    from .. import legacy

    register_backend(classic.ClassicBackend())
    register_backend(classic_gravity.ClassicGravityBackend())
    register_backend(bone_dynamics.BoneDynamicsBackend())
    register_backend(legacy.LegacyBackend())
