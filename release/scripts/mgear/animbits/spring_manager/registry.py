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


def node_kind(network):
    """Return the kind of a Spring Manager network node.

    Args:
        network (str): Network node name.

    Returns:
        str: :data:`constants.KIND_SPRING` when the kind is not stored.
    """
    return attribute.get_string_attr(
        network, constants.KIND_ATTR, constants.KIND_SPRING
    )


def _network_spring(network):
    """Return the spring of a network node, or None if it is not a spring.

    Args:
        network (str): Network node name.

    Returns:
        Spring: The spring, or None for untagged and shared nodes.
    """
    if cmds.nodeType(network) != "network" or not cmds.attributeQuery(
        constants.TAG_ATTR, node=network, exists=True
    ):
        return None
    if node_kind(network) != constants.KIND_SPRING:
        return None
    return Spring(network, cmds.getAttr("{}.{}".format(network, constants.TAG_ATTR)))


def list_shared(kind, backend=None):
    """Return the shared Spring Manager nodes of a kind (solver, wind...).

    Args:
        kind (str): Node kind, e.g. :data:`constants.KIND_SOLVER`.
        backend (str, optional): Only nodes of this backend.

    Returns:
        list: Network node names.
    """
    nodes = []
    for node in attribute.ls_nodes_with_attr(constants.KIND_ATTR):
        if node_kind(node) != kind:
            continue
        if backend and attribute.get_string_attr(node, constants.TAG_ATTR) != backend:
            continue
        nodes.append(node)
    return nodes


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


def selected_springs(known=None):
    """Return the springs owning the selected nodes.

    Args:
        known (dict, optional): ``{long control name: Spring}`` looked up
            first, see :func:`node_map`.

    Returns:
        list: :class:`Spring` records.
    """
    return springs_from_nodes(cmds.ls(selection=True, long=True), known)


# -----------------------------------------------------------------------------
# Creation
# -----------------------------------------------------------------------------


def create_network(
    name, backend, controls, settings_node, extra=None, kind=constants.KIND_SPRING
):
    """Create and tag the network node owning a spring setup or shared node.

    Args:
        name (str): Network node name.
        backend (str): Backend name stored in the tag.
        controls (list): Driven controls. Empty for shared nodes.
        settings_node (str): Node holding the animatable parameters, or
            None for shared nodes.
        extra (dict, optional): Additional string attributes to store.
        kind (str, optional): :data:`constants.KIND_SPRING` or a shared
            kind (solver, wind, collider).

    Returns:
        str: The network node.
    """
    network = cmds.createNode("network", name=name)
    attribute.set_string_attr(network, constants.TAG_ATTR, backend)
    attribute.set_string_attr(network, constants.KIND_ATTR, kind)
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
    if settings_node:
        cmds.connectAttr(
            settings_node + ".message",
            "{}.{}".format(network, constants.SETTINGS_ATTR),
        )
    return network


def shared_nodes():
    """Return the shared Spring Manager networks and their members.

    Returns:
        set: Node names of every non-spring network (solver, wind,
        collider) and of the nodes they own.
    """
    nodes = set()
    for network in attribute.ls_nodes_with_attr(constants.KIND_ATTR):
        if node_kind(network) == constants.KIND_SPRING:
            continue
        nodes.add(network)
        nodes.update(attribute.get_message_inputs(network, constants.MEMBERS_ATTR))
    return nodes


def delete_members(network, members=None):
    """Delete the members of a spring, keeping the shared nodes it uses.

    Maya deletes upstream nodes left without outputs, so the connections
    from shared nodes (solver, wind, colliders) into the members are
    removed first.

    Args:
        network (str): Spring network node.
        members (list, optional): Members, read from the network when None.
    """
    members = (
        cmds.ls(
            members
            if members is not None
            else attribute.get_message_inputs(network, constants.MEMBERS_ATTR)
        )
        or []
    )
    if not members:
        return
    shared = shared_nodes()
    for member in members:
        connections = (
            cmds.listConnections(
                member,
                source=True,
                destination=False,
                plugs=True,
                connections=True,
            )
            or []
        )
        for destination, source in zip(connections[::2], connections[1::2]):
            if source.split(".")[0] in shared:
                cmds.disconnectAttr(source, destination)
    cmds.delete(members)


def node_map(springs):
    """Return a lookup of springs by the long names of their nodes.

    Args:
        springs (list): :class:`Spring` records.

    Returns:
        dict: ``{long name: Spring}`` for controls and members.
    """
    lookup = {}
    for spring in springs:
        for node in cmds.ls(spring.members + spring.controls, long=True) or []:
            lookup[node] = spring
    return lookup


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
