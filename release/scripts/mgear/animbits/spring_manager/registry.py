"""Find and describe the spring setups in the scene.

Every setup created by the Spring Manager is owned by a ``network`` node
tagged with :data:`constants.TAG_ATTR`. Setups built by the previous
Spring Manager are found through their ``springSetupMembers`` attribute
and reported as :class:`LegacySpring` (backend ``"legacy"``).
"""

from maya import cmds

from mgear.core import attribute

from . import constants


class Spring(object):
    """Lightweight record of a spring setup in the scene.

    The controls and settings node are cached: they do not change during
    the life of a setup. Members and state are read live.

    Attributes:
        node (str): The network node.
        backend (str): Backend name.
    """

    legacy = False

    def __init__(self, node, backend):
        self.node = node
        self.backend = backend
        self._controls = None
        self._settings_node = None
        self._settings_loaded = False

    def __eq__(self, other):
        return isinstance(other, Spring) and other.node == self.node

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.node)

    def __repr__(self):
        return "{}({!r}, {!r})".format(type(self).__name__, self.node, self.backend)

    def exists(self):
        """Return True if the spring node still exists.

        Returns:
            bool: True if the node exists.
        """
        return cmds.objExists(self.node)

    @property
    def controls(self):
        """list: The driven controls."""
        if self._controls is None:
            self._controls = attribute.get_message_inputs(
                self.node, constants.CONTROLS_ATTR
            )
        return self._controls

    @property
    def settings_node(self):
        """str: The node holding the animatable parameters, or None."""
        if not self._settings_loaded:
            nodes = attribute.get_message_inputs(self.node, constants.SETTINGS_ATTR)
            self._settings_node = nodes[0] if nodes else None
            self._settings_loaded = True
        return self._settings_node

    @property
    def members(self):
        """list: The nodes created by the setup."""
        return attribute.get_message_inputs(self.node, constants.MEMBERS_ATTR)

    @property
    def state(self):
        """str: ``"active"`` or ``"baked"``."""
        return attribute.get_string_attr(
            self.node, constants.STATE_ATTR, constants.STATE_ACTIVE
        )

    def set_state(self, state):
        """Store the state of the spring.

        Args:
            state (str): ``"active"`` or ``"baked"``.
        """
        attribute.set_string_attr(self.node, constants.STATE_ATTR, state)

    @property
    def label(self):
        """str: Display name, the short name of the first control."""
        controls = self.controls
        name = controls[0] if controls else self.node
        return name.split("|")[-1]


class LegacySpring(Spring):
    """Setup made by the previous Spring Manager, owned by its control.

    Attributes:
        node (str): The control holding ``springSetupMembers``.
    """

    legacy = True

    def __init__(self, node):
        super(LegacySpring, self).__init__(node, constants.LEGACY_BACKEND)

    @property
    def controls(self):
        """list: The control."""
        return [self.node]

    @property
    def settings_node(self):
        """str: The control."""
        return self.node

    @property
    def members(self):
        """list: The nodes of the legacy setup, the root first."""
        return attribute.get_message_inputs(self.node, constants.LEGACY_MEMBERS_ATTR)

    @property
    def state(self):
        """str: Always ``"active"``."""
        return constants.STATE_ACTIVE

    def set_state(self, state):
        """Legacy setups have no state: does nothing.

        Args:
            state (str): Ignored.
        """


# -----------------------------------------------------------------------------
# Queries
# -----------------------------------------------------------------------------


def _network_spring(network):
    """Return the spring of a network node, or None if it is not tagged.

    Args:
        network (str): Network node name.

    Returns:
        Spring: The spring, or None.
    """
    if cmds.nodeType(network) != "network" or not cmds.attributeQuery(
        constants.TAG_ATTR, node=network, exists=True
    ):
        return None
    return Spring(network, cmds.getAttr("{}.{}".format(network, constants.TAG_ATTR)))


def list_springs(previous=None):
    """Return every spring setup in the scene, legacy ones included.

    Only Spring Manager setups are returned: Shifter spring components and
    other ``mgear_springNode`` users are ignored.

    Args:
        previous (list, optional): Springs from an earlier call. Records
            that still exist are reused, keeping their cached data.

    Returns:
        list: :class:`Spring` records, sorted by label.
    """
    known = {spring.node: spring for spring in previous or []}
    springs = []
    for node in attribute.ls_nodes_with_attr(constants.TAG_ATTR):
        spring = known.get(node) or _network_spring(node)
        if spring:
            springs.append(spring)
    for control in attribute.ls_nodes_with_attr(constants.LEGACY_MEMBERS_ATTR):
        springs.append(known.get(control) or LegacySpring(control))
    return sorted(springs, key=lambda spring: spring.label)


def spring_from_node(node):
    """Return the spring setup a node belongs to.

    The node can be the network node, a driven control, the settings node
    or any node created by the setup.

    Args:
        node (str): Node name.

    Returns:
        Spring: The owning spring, or None.
    """
    if not node or not cmds.objExists(node):
        return None
    spring = _network_spring(node)
    if spring:
        return spring
    for network in (
        cmds.listConnections(
            node + ".message", source=False, destination=True, type="network"
        )
        or []
    ):
        spring = _network_spring(network)
        if spring:
            return spring

    # legacy: the control itself or one of its members
    if cmds.attributeQuery(constants.LEGACY_MEMBERS_ATTR, node=node, exists=True):
        return LegacySpring(node)
    for plug in (
        cmds.listConnections(
            node + ".message", source=False, destination=True, plugs=True
        )
        or []
    ):
        if constants.LEGACY_MEMBERS_ATTR in plug:
            return LegacySpring(plug.split(".")[0])
    return None


def map_nodes_to_springs(nodes, known=None):
    """Return the spring owning each node.

    Args:
        nodes (list): Node names.
        known (dict, optional): ``{long control name: Spring}`` looked up
            first, to skip the scene queries for known controls.

    Returns:
        dict: ``{node: Spring or None}``.
    """
    known = known or {}
    return {node: known.get(node) or spring_from_node(node) for node in nodes or []}


def springs_from_nodes(nodes, known=None):
    """Return the unique springs that own the given nodes, in order.

    Args:
        nodes (list): Node names.
        known (dict, optional): ``{long control name: Spring}`` looked up
            first, see :func:`map_nodes_to_springs`.

    Returns:
        list: :class:`Spring` records.
    """
    springs = []
    seen = set()
    for spring in map_nodes_to_springs(nodes, known).values():
        if spring and spring not in seen:
            seen.add(spring)
            springs.append(spring)
    return springs


def control_map(springs):
    """Return a lookup of the springs by long control name.

    Args:
        springs (list): :class:`Spring` records.

    Returns:
        dict: ``{long control name: Spring}``.
    """
    lookup = {}
    for spring in springs:
        for control in cmds.ls(spring.controls, long=True) or []:
            lookup[control] = spring
    return lookup


def selected_springs(known=None):
    """Return the springs owning the selected nodes.

    Args:
        known (dict, optional): ``{long control name: Spring}`` looked up
            first, see :func:`control_map`.

    Returns:
        list: :class:`Spring` records.
    """
    return springs_from_nodes(cmds.ls(selection=True, long=True), known)


# -----------------------------------------------------------------------------
# Creation
# -----------------------------------------------------------------------------


def create_network(name, backend, controls, settings_node, extra=None):
    """Create and tag the network node owning a spring setup.

    Args:
        name (str): Network node name.
        backend (str): Backend name stored in the tag.
        controls (list): Driven controls.
        settings_node (str): Node holding the animatable parameters.
        extra (dict, optional): Additional string attributes to store.

    Returns:
        str: The network node.
    """
    network = cmds.createNode("network", name=name)
    attribute.set_string_attr(network, constants.TAG_ATTR, backend)
    cmds.addAttr(
        network,
        longName=constants.VERSION_ATTR,
        attributeType="long",
        defaultValue=constants.SCENE_VERSION,
    )
    for attr in (constants.CONTROLS_ATTR, constants.MEMBERS_ATTR):
        cmds.addAttr(network, longName=attr, attributeType="message", multi=True)
    cmds.addAttr(network, longName=constants.SETTINGS_ATTR, attributeType="message")
    extra = dict(extra or {})
    extra.setdefault(constants.STATE_ATTR, constants.STATE_ACTIVE)
    for attr, value in extra.items():
        attribute.set_string_attr(network, attr, value)

    attribute.connect_messages(controls, network, constants.CONTROLS_ATTR)
    cmds.connectAttr(
        settings_node + ".message",
        "{}.{}".format(network, constants.SETTINGS_ATTR),
    )
    return network


def add_members(network, nodes):
    """Register created nodes as members of a spring setup.

    The network node itself and the driven controls are skipped.

    Args:
        network (str): Network node.
        nodes (list): Node names.
    """
    skip = {network}
    skip.update(attribute.get_message_inputs(network, constants.CONTROLS_ATTR))
    skip.update(attribute.get_message_inputs(network, constants.SETTINGS_ATTR))
    members = [node for node in nodes if node not in skip and cmds.objExists(node)]
    attribute.connect_messages(members, network, constants.MEMBERS_ATTR)
