"""Right-click context of the dag menu."""

from functools import cached_property

from maya import cmds

from mgear.core import anim_utils
from mgear.core.pickWalk import get_controls_with_children

IKFK_SUFFIXES = ("_blend", "_switch")
SPACE_SUFFIXES = ("ref", "follow")


def list_switch_attrs(node):
    """List the keyable user attributes of a node that can be switches.

    Proxy attributes are skipped.

    Args:
        node (str): Node to search.

    Returns:
        list: (attribute name, is enum) tuples.
    """
    attrs = []
    for attr in cmds.listAttr(node, userDefined=True, keyable=True) or []:
        plug = "{}.{}".format(node, attr)
        if cmds.addAttr(plug, query=True, usedAsProxy=True):
            continue
        attrs.append((attr, cmds.getAttr(plug, type=True) == "enum"))
    return attrs


class MenuContext(object):
    """The right-clicked node and the data the menu sections need.

    Values are computed on first access and cached, so each one is queried
    at most once per right-click.

    Args:
        node (str): The right-clicked node.
        selection (list, optional): Selected nodes. Defaults to the current
            selection.
    """

    def __init__(self, node, selection=None):
        self.node = node
        if selection is None:
            selection = cmds.ls(selection=True)
        self.selection = selection
        self._switch_attrs = {}

    def switch_attrs(self, node, suffixes, enum_only=False):
        """Get the switch attributes of a node ending with the suffixes.

        The node attributes are listed once per context.

        Args:
            node (str): Node to search, None returns an empty list.
            suffixes (tuple): Lower case attribute name suffixes.
            enum_only (bool, optional): Keep only enum attributes.

        Returns:
            list: Attribute names, grouped by suffix in the given order.
        """
        if not node:
            return []
        if node not in self._switch_attrs:
            self._switch_attrs[node] = list_switch_attrs(node)
        return [
            attr
            for suffix in suffixes
            for attr, is_enum in self._switch_attrs[node]
            if attr.lower().endswith(suffix) and (is_enum or not enum_only)
        ]

    def _has_switch_attrs(self, node, space_suffixes):
        return bool(
            self.switch_attrs(node, IKFK_SUFFIXES)
            or self.switch_attrs(node, space_suffixes, enum_only=True)
        )

    @cached_property
    def ui_host(self):
        """str: Node holding the IK/FK and space switch attributes, or None.

        The node itself when it has switch attributes, else the node
        connected to its uiHost_cnx attribute.
        """
        if self._has_switch_attrs(self.node, ("ref",)):
            return self.node
        if not cmds.attributeQuery("uiHost_cnx", node=self.node, exists=True):
            return None
        hosts = cmds.listConnections("{}.uiHost_cnx".format(self.node))
        if hosts and self._has_switch_attrs(hosts[0], SPACE_SUFFIXES):
            return hosts[0]
        return None

    @cached_property
    def ikfk_attrs(self):
        """list: (attribute, suffix) IK/FK switch attributes of the ui host."""
        return [
            (attr, suffix)
            for suffix in IKFK_SUFFIXES
            for attr in self.switch_attrs(self.ui_host, (suffix,))
        ]

    @cached_property
    def space_attrs(self):
        """list: (node, attribute) space switch enum attributes.

        Attributes of the ui host first, then the ones of the node itself
        when it is not the ui host.
        """
        nodes = [self.ui_host]
        if self.node != self.ui_host:
            nodes.append(self.node)
        return [
            (node, attr)
            for node in nodes
            for attr in self.switch_attrs(node, SPACE_SUFFIXES, enum_only=True)
        ]

    @cached_property
    def child_controls(self):
        """list: The selected controls, the node, and all their children."""
        return get_controls_with_children(self.selection + [self.node])

    @cached_property
    def all_controls(self):
        """list: Controls of the rig."""
        return anim_utils.get_rig_controls(self.node)

    @cached_property
    def rig_root(self):
        """str: Short name of the rig top node, or None."""
        return anim_utils.find_rig_root(self.node)

    @cached_property
    def comp_type(self):
        """str: Shifter component type of the node, or None."""
        from .components import get_comp_type

        return get_comp_type(self.node)
