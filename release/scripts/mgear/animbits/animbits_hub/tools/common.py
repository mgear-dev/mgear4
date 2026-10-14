"""Row helpers shared by the Animbits Hub tools.

Tools show one row for the selection, then one row per selection bookmark
enabled for the tool in the bookmark "Show In Tools" menu.
"""

from maya import cmds

from mgear.core import attribute
from mgear.core import selection_bookmarks

SELECTION_ROW_NAME = "Selection"
SELECTION_ROW_KEY = "selection"


def context_bookmarks(context):
    """Return the scene bookmarks, loaded once per hub refresh.

    Args:
        context (HubContext): The hub context.

    Returns:
        list: Bookmark dictionaries.
    """
    if context.bookmarks is None:
        context.bookmarks = selection_bookmarks.load_scene_bookmarks()
    return context.bookmarks


def row_specs(bookmarks, selection_color, tool_id):
    """Return the rows of a tool, the selection row first.

    Args:
        bookmarks (list): Bookmark dictionaries.
        selection_color (tuple): RGB 0-1 color of the selection row.
        tool_id (str): Bookmark tool id, e.g. ``"tweener"``.

    Returns:
        list: ``{"name", "color", "bookmark"}`` dicts. ``bookmark`` is
            None for the selection row.
    """
    specs = [
        {
            "name": SELECTION_ROW_NAME,
            "color": tuple(selection_color),
            "bookmark": None,
        }
    ]
    for bookmark in selection_bookmarks.bookmarks_for_tool(bookmarks, tool_id):
        specs.append(
            {
                "name": bookmark["name"],
                "color": tuple(bookmark["color"]),
                "bookmark": bookmark,
            }
        )
    return specs


def row_key(bookmark=None):
    """Return the key of a row, e.g. for its buffers and settings.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection row.

    Returns:
        str: ``"selection"`` or ``"bookmark:<name>"``.
    """
    if bookmark is None:
        return SELECTION_ROW_KEY
    return "bookmark:{}".format(bookmark["name"])


def row_targets(bookmark=None, namespace=None):
    """Return the keyable nodes of a row.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection.
        namespace (str, optional): Hub namespace, for a bookmark with
            ``use_selected_namespace`` on.

    Returns:
        list: Node names.
    """
    if bookmark is None:
        items = cmds.ls(selection=True, long=True) or []
    else:
        try:
            items, _missing = selection_bookmarks.resolve_bookmark_items(
                bookmark, namespace
            )
        except RuntimeError as e:
            cmds.warning(str(e))
            return []
    return attribute.keyable_nodes(items)
