"""Bookmark helpers used by the window: tooltip text and shelf buttons."""

import json

import maya.mel as mel
from maya import cmds

from mgear.core import node_remap
from mgear.core import selection_bookmarks
from mgear.core.pyqt import get_icon_path


def build_tooltip(bookmark):
    """Build a detailed tooltip string for a bookmark.

    Lists objects (truncated at 50) and summarizes components
    by type per object.

    Args:
        bookmark (dict): The bookmark dictionary.

    Returns:
        str: Multi-line tooltip text.
    """
    if bookmark["type"] == selection_bookmarks.BOOKMARK_SELECTION:
        type_label = "Selection Bookmark"
    else:
        type_label = "Isolate Bookmark"

    items = bookmark["items"]
    objects = []
    components = {}
    for item in items:
        obj, comp = node_remap.split_component(item)
        if "[" in comp:
            comp_type = comp[1:].split("[")[0]
            if obj not in components:
                components[obj] = {}
            components[obj].setdefault(comp_type, 0)
            components[obj][comp_type] += 1
        else:
            objects.append(item)

    lines = [type_label]
    lines.append("{} items total".format(len(items)))
    lines.append("")

    if objects:
        lines.append("Objects ({}):".format(len(objects)))
        for obj in objects[:50]:
            lines.append("  " + obj)
        if len(objects) > 50:
            lines.append("  ... +{} more".format(len(objects) - 50))

    if components:
        if objects:
            lines.append("")
        lines.append("Components:")
        for obj, types in sorted(components.items()):
            parts = []
            for comp_type, count in sorted(types.items()):
                parts.append("{} {}".format(count, comp_type))
            lines.append("  {}: {}".format(obj, ", ".join(parts)))

    if bookmark.get("use_selected_namespace"):
        lines.append("")
        lines.append("Namespace: from current selection")

    return "\n".join(lines)


def add_bookmark_to_shelf(bookmark):
    """Add a bookmark as a button on Maya's current shelf.

    The shelf button calls core functions directly via a compact
    Python command.

    Args:
        bookmark (dict): The bookmark dictionary.

    Returns:
        str: The shelf button name, or None if failed.
    """
    try:
        current_shelf = mel.eval("tabLayout -query -selectTab $gShelfTopLevel")
    except Exception:
        cmds.warning("Could not find current shelf")
        return None

    name = bookmark["name"]
    r, g, b = bookmark["color"]
    bm_data = json.dumps(bookmark)
    is_selection = bookmark["type"] == selection_bookmarks.BOOKMARK_SELECTION

    command = (
        "from mgear.core import selection_bookmarks\n"
        "import json\n"
        "bm = json.loads({data!r})\n"
    ).format(data=bm_data)

    if is_selection:
        command += (
            "import maya.cmds as cmds\n"
            "mods = cmds.getModifiers()\n"
            "if mods & 1:\n"
            "    selection_bookmarks.recall_selection(bm, 'add')\n"
            "elif mods & 4:\n"
            "    selection_bookmarks.recall_selection(bm, 'deselect')\n"
            "else:\n"
            "    selection_bookmarks.recall_selection(bm, 'replace')\n"
        )
        icon = get_icon_path("mgear_mouse-pointer.svg")
    else:
        command += "selection_bookmarks.toggle_isolate(bm)\n"
        icon = get_icon_path("mgear_eye.svg")

    btn = cmds.shelfButton(
        parent=current_shelf,
        label=name,
        annotation=build_tooltip(bookmark),
        imageOverlayLabel=name,
        image1=icon,
        overlayLabelColor=[0, 0, 0],
        overlayLabelBackColor=list(bookmark["color"]) + [0.5],
        command=command,
        sourceType="python",
        backgroundColor=[r, g, b],
    )
    return btn
