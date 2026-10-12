"""Registry of the tools shown in the Animbits Hub.

A tool registers a factory that builds its slider rows, or its widgets
for the tool area above the sliders. The hub calls every factory each
time it is shown, in ``order``, so the hub always reflects the current
scene. No Qt code, so tools and tests can import it freely.
"""

AREA_ROWS = "rows"
AREA_TOOLS = "tools"

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
        # scene bookmarks, loaded once per hub refresh by the first tool
        self.bookmarks = None


def register_tool(tool_id, factory, order=100, area=AREA_ROWS):
    """Register a tool, or replace the one registered with the same id.

    Tool ids of Shifter components or custom scripts should be
    namespaced, e.g. ``"component:arm_2jnt_01:ikfk"``, to never clash with
    the built-in tools.

    Args:
        tool_id (str): Unique tool id.
        factory (callable): Called with a :class:`HubContext`, returns a
            list of ``HubRow`` widgets (e.g. ``HubToolRow`` for the tool
            area).
        order (int, optional): Tools with a lower order come first.
        area (str, optional): Where the rows go: ``"rows"`` with the
            sliders, ``"tools"`` in the tool area above the mode bar.
    """
    _tools[tool_id] = (factory, order, area)


def unregister_tool(tool_id):
    """Remove a registered tool. Unknown ids are ignored.

    Args:
        tool_id (str): The tool id.
    """
    _tools.pop(tool_id, None)


def registered_tools(area=AREA_ROWS):
    """Return the tools registered for an area, sorted by order.

    Tools with the same order keep their registration order.

    Args:
        area (str, optional): ``"rows"`` or ``"tools"``.

    Returns:
        list: ``(tool_id, factory)`` tuples.
    """
    items = sorted(
        (item for item in _tools.items() if item[1][2] == area),
        key=lambda item: item[1][1],
    )
    return [(tool_id, factory) for tool_id, (factory, _order, _area) in items]
