"""Registry of the tools shown in the Animbits Hub.

A tool registers a factory that builds its rows. The hub calls every
factory each time it is shown, in ``order``, so rows always reflect the
current scene. No Qt code, so tools and tests can import it freely.
"""

_tools = {}


class HubContext(object):
    """What a tool factory gets to build its rows.

    Args:
        settings (HubSettings): The hub settings.
        namespace (str, optional): The hub namespace, see
            :meth:`HubOverlay.set_namespace`.
        namespace_valid (bool, optional): True when the namespace exists.
    """

    def __init__(self, settings, namespace=None, namespace_valid=False):
        self.settings = settings
        self.namespace = namespace
        self.namespace_valid = namespace_valid


def register_tool(tool_id, factory, order=100):
    """Register a tool, or replace the one registered with the same id.

    Tool ids of Shifter components or custom scripts should be
    namespaced, e.g. ``"component:arm_2jnt_01:ikfk"``, to never clash with
    the built-in tools.

    Args:
        tool_id (str): Unique tool id.
        factory (callable): Called with a :class:`HubContext`, returns a
            list of ``HubRow`` widgets.
        order (int, optional): Tools with a lower order come first.
    """
    _tools[tool_id] = (factory, order)


def unregister_tool(tool_id):
    """Remove a registered tool. Unknown ids are ignored.

    Args:
        tool_id (str): The tool id.
    """
    _tools.pop(tool_id, None)


def registered_tools():
    """Return the registered tools sorted by order.

    Tools with the same order keep their registration order.

    Returns:
        list: ``(tool_id, factory)`` tuples.
    """
    items = sorted(_tools.items(), key=lambda item: item[1][1])
    return [(tool_id, factory) for tool_id, (factory, _order) in items]
