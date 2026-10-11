"""Bookmarks core logic.

Data model, scene storage, export/import, selection/isolate recall,
and shelf button generation. No UI code.
"""

import colorsys
import copy
import json
import logging
import random

import maya.mel as mel
from maya import cmds

from mgear.core import anim_utils
from mgear.core import node_remap
from mgear.core.pyqt import get_icon_path
from mgear.core.pyqt import get_user_settings

# moved to mgear.core.pyqt, kept here for backward compatibility
from mgear.core.pyqt import text_color_for_background  # noqa: F401

logger = logging.getLogger("mgear.utilbits.bookmarks")

#############################################
# CONSTANTS
#############################################

BOOKMARK_SELECTION = "selection"
BOOKMARK_ISOLATE = "isolate"
CONFIG_FILE_EXT = ".sbk"
CONFIG_VERSION = "2.0"
LEGACY_CONFIG_VERSION = "1.0"
SCENE_NODE_NAME = "mgear_selection_bookmarks"
SCENE_NODE_TYPE_ATTR = "is_selection_bookmarks_data"
SCENE_NODE_DATA_ATTR = "bookmarks_data"

LAYOUT_NAMES = ("horizontal", "vertical", "grid")
LAYOUT_MAP = {name: i for i, name in enumerate(LAYOUT_NAMES)}

LAST_NAMESPACE_KEY = "sel_bookmarks/last_namespace"

# Tools that read bookmarks, as {tool_id: label}, filled by the tools
# themselves through register_bookmark_tool
_registered_tools = {}


#############################################
# DATA MODEL
#############################################


def random_pastel_color():
    """Generate a random pastel color.

    Uses HSV with full hue range, low saturation, and high value
    to produce soft pastel tones.

    Returns:
        tuple: RGB 0-1 tuple.
    """
    h = random.random()
    s = random.uniform(0.25, 0.45)
    v = random.uniform(0.80, 0.95)
    return colorsys.hsv_to_rgb(h, s, v)


def create_bookmark(name, bookmark_type, items, color=None):
    """Create a bookmark dictionary.

    Args:
        name (str): Display name for the bookmark.
        bookmark_type (str): BOOKMARK_SELECTION or BOOKMARK_ISOLATE.
        items (list): List of Maya object or component names.
        color (tuple, optional): RGB 0-1 tuple. Random pastel if None.

    Returns:
        dict: Bookmark dictionary.
    """
    if color is None:
        color = random_pastel_color()
    return {
        "name": name,
        "color": list(color),
        "type": bookmark_type,
        "items": list(items),
        "use_selected_namespace": False,
        "tools": {},
    }


def bookmark_from_selection(name, bookmark_type, color=None):
    """Create a bookmark from the current Maya selection.

    Args:
        name (str): Display name for the bookmark.
        bookmark_type (str): BOOKMARK_SELECTION or BOOKMARK_ISOLATE.
        color (tuple, optional): RGB 0-1 tuple. Auto-assigned if None.

    Returns:
        dict: Bookmark dictionary, or None if nothing selected.
    """
    sel = cmds.ls(selection=True, long=True, flatten=True)
    if not sel:
        return None
    items = [to_storage_form(s) for s in sel]
    return create_bookmark(name, bookmark_type, items, color)


def validate_bookmark_items(bookmark):
    """Filter bookmark items to only those that exist in the scene.

    Resolves stored short names through ``resolve_bookmark_items`` so
    namespace handling is consistent with recall.

    Args:
        bookmark (dict): The bookmark to validate.

    Returns:
        list: Valid long DAG paths for items that exist in the
            current scene. Returns an empty list if resolution fails
            (ambiguous items, etc.) -- callers that need detailed
            error reporting should call ``resolve_bookmark_items``.
    """
    if not bookmark.get("items"):
        return []
    try:
        resolved, _missing = resolve_bookmark_items(bookmark)
    except RuntimeError:
        return []
    return resolved


def build_tooltip(bookmark):
    """Build a detailed tooltip string for a bookmark.

    Lists objects (truncated at 50) and summarizes components
    by type per object.

    Args:
        bookmark (dict): The bookmark dictionary.

    Returns:
        str: Multi-line tooltip text.
    """
    if bookmark["type"] == BOOKMARK_SELECTION:
        type_label = "Selection Bookmark"
    else:
        type_label = "Isolate Bookmark"

    items = bookmark["items"]
    objects = []
    components = {}
    for item in items:
        if "." in item and "[" in item:
            obj, comp = item.split(".", 1)
            comp_type = comp.split("[")[0]
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


#############################################
# TOOL SETTINGS
#############################################


def register_bookmark_tool(tool_id, label):
    """Register a tool that reads bookmarks.

    Registered tools are listed in the "Show In Tools" menu of each
    selection bookmark. Registering an id again updates its label.

    Args:
        tool_id (str): Key of the tool in the bookmark ``tools`` dict.
        label (str): Name shown in the menu.
    """
    _registered_tools[tool_id] = label


def registered_bookmark_tools():
    """Return the registered tools that read bookmarks.

    Returns:
        list: ``(tool_id, label)`` tuples in registration order.
    """
    return list(_registered_tools.items())


def get_tool_config(bookmark, tool_id):
    """Return the settings of a tool stored on a bookmark.

    Args:
        bookmark (dict): The bookmark dictionary.
        tool_id (str): The tool id.

    Returns:
        dict: The tool settings, empty when the tool has none.
    """
    return bookmark.get("tools", {}).get(tool_id, {})


def set_tool_config(bookmark, tool_id, **values):
    """Merge settings of a tool into a bookmark.

    Args:
        bookmark (dict): The bookmark dictionary to modify.
        tool_id (str): The tool id.
        **values: Settings to set, e.g. ``enabled=True``.
    """
    tools = bookmark.setdefault("tools", {})
    tools.setdefault(tool_id, {}).update(values)


def is_tool_enabled(bookmark, tool_id):
    """Return True when a tool is enabled on a bookmark.

    Args:
        bookmark (dict): The bookmark dictionary.
        tool_id (str): The tool id.

    Returns:
        bool: The ``enabled`` setting of the tool.
    """
    return bool(get_tool_config(bookmark, tool_id).get("enabled", False))


def bookmarks_for_tool(bookmarks, tool_id):
    """Return the selection bookmarks a tool is enabled on.

    Args:
        bookmarks (list): Bookmark dictionaries.
        tool_id (str): The tool id.

    Returns:
        list: The enabled selection bookmarks, in order.
    """
    return [
        bm
        for bm in bookmarks
        if bm.get("type") == BOOKMARK_SELECTION and is_tool_enabled(bm, tool_id)
    ]


#############################################
# NAME / NAMESPACE HELPERS
#############################################


def to_storage_form(name):
    """Convert a long DAG path or any node name to v2.0 storage form.

    Strips the DAG path, keeping ``namespace:short[.component]``.

    Args:
        name (str): Maya node name, possibly with full DAG path.

    Returns:
        str: Storage-form name.
    """
    return name.rsplit("|", 1)[-1]


def extract_namespace(name):
    """Return the namespace prefix of a node name (without trailing colon).

    Handles nested namespaces (``char01:rig:body`` -> ``char01:rig``).
    Returns an empty string if the node has no namespace.

    Args:
        name (str): Node name (long path, short, or with components).

    Returns:
        str: Namespace string, possibly nested, or empty string.
    """
    short = name.rsplit("|", 1)[-1]
    obj = short.split(".", 1)[0]
    if ":" not in obj:
        return ""
    return obj.rsplit(":", 1)[0]


def strip_namespace(name):
    """Return the node's bare short name with no DAG path or namespace.

    Components are preserved (``char01:body.f[0:10]`` -> ``body.f[0:10]``).

    Args:
        name (str): Node name (long path, short, or with components).

    Returns:
        str: Short name without namespace.
    """
    short = name.rsplit("|", 1)[-1]
    if "." in short:
        obj, comp = short.split(".", 1)
        return obj.rsplit(":", 1)[-1] + "." + comp
    return short.rsplit(":", 1)[-1]


def swap_namespace(stored_item, new_ns):
    """Replace the namespace prefix of a v2.0 storage-form item.

    Args:
        stored_item (str): Item in storage form (``ns:short[.comp]``).
        new_ns (str): New namespace, possibly nested. Empty string
            means root namespace.

    Returns:
        str: Item with the namespace replaced.
    """
    bare = strip_namespace(stored_item)
    if new_ns:
        return "{}:{}".format(new_ns, bare)
    return bare


def get_last_namespace():
    """Return the last namespace used by namespace-following bookmarks.

    The value is kept in the mGear user settings, so it survives Maya
    sessions.

    Returns:
        str: The namespace (empty string for the root namespace), or None
            when none was stored.
    """
    value = get_user_settings().value(LAST_NAMESPACE_KEY)
    if value is None:
        return None
    return str(value)


def set_last_namespace(namespace):
    """Store the last namespace used by namespace-following bookmarks.

    Args:
        namespace (str): The namespace, empty string for the root.
    """
    settings = get_user_settings()
    settings.setValue(LAST_NAMESPACE_KEY, namespace)
    settings.sync()


# Moved to mgear.core.node_remap, kept for the callers of this module
scene_namespaces = node_remap.scene_namespaces


def namespace_exists(namespace):
    """Return True when a namespace exists in the scene.

    Args:
        namespace (str): Namespace name, empty string for the root.

    Returns:
        bool: True for the root and for existing namespaces.
    """
    if namespace is None:
        return False
    return not namespace or cmds.namespace(exists=":" + namespace)


def selection_namespace():
    """Return the namespace of the first selected object and store it.

    The namespace becomes the last namespace, see
    :func:`get_last_namespace`.

    Returns:
        str: The namespace (empty string for the root namespace), or None
            when nothing is selected.
    """
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        return None
    namespace = extract_namespace(sel[0])
    if namespace != get_last_namespace():
        set_last_namespace(namespace)
    return namespace


def resolve_bookmark_items(bookmark, namespace=None):
    """Resolve a bookmark's items to long DAG paths in the current scene.

    Honors the ``use_selected_namespace`` toggle: when on, every item's
    stored namespace is replaced before lookup with, in order, the
    ``namespace`` argument, the namespace of the currently selected
    object (which is then stored as the last namespace), or the last
    stored namespace.

    Components like ``ns:body.f[0:10]`` are resolved by looking up the
    parent transform first (so ambiguity is detected on the transform),
    then re-attaching the component suffix to the long path.

    Args:
        bookmark (dict): The bookmark dictionary.
        namespace (str, optional): Namespace to use for a bookmark with
            ``use_selected_namespace`` on, instead of the selection's.

    Returns:
        tuple: ``(resolved, missing)`` where ``resolved`` is a list of
            long DAG paths (with components if present) and ``missing``
            is a list of stored items that did not resolve.

    Raises:
        RuntimeError: If any item is ambiguous, or if
            ``use_selected_namespace`` is on with no namespace argument,
            no current selection and no stored last namespace.
    """
    items = bookmark.get("items", [])
    if bookmark.get("use_selected_namespace"):
        new_ns = namespace
        if new_ns is None:
            new_ns = selection_namespace()
        if new_ns is None:
            new_ns = get_last_namespace()
        if new_ns is None:
            raise RuntimeError(
                "'Use selected namespace' is on but nothing is selected."
            )
        items = [swap_namespace(i, new_ns) for i in items]

    resolved = []
    ambiguous = []
    missing = []
    # Resolve each distinct object once and reuse the result for every item
    # on it. Component-heavy bookmarks (hundreds of ``ns:mesh.f[N]`` faces on
    # a single mesh) then cost one ``cmds.ls`` instead of one per item.
    lookup = {}
    for item in items:
        if "." in item and "[" in item:
            obj, comp = item.split(".", 1)
        else:
            obj, comp = item, None
        if obj not in lookup:
            lookup[obj] = cmds.ls(obj, long=True) or []
        matches = lookup[obj]
        if not matches:
            missing.append(item)
            continue
        if len(matches) > 1:
            ambiguous.append((item, matches))
            continue
        resolved.append(matches[0] + ("." + comp if comp else ""))

    if ambiguous:
        details = "\n".join(
            "  '{}' -> {}".format(name, ", ".join(m))
            for name, m in ambiguous
        )
        raise RuntimeError(
            "Bookmark items are ambiguous:\n{}".format(details)
        )
    return resolved, missing


#############################################
# SELECTION LOGIC
#############################################


def recall_selection(bookmark, mode="replace"):
    """Recall a selection bookmark.

    Args:
        bookmark (dict): The bookmark dictionary.
        mode (str): "replace", "add", or "deselect".
    """
    try:
        valid, missing = resolve_bookmark_items(bookmark)
    except RuntimeError as e:
        cmds.warning(str(e))
        return
    if not valid:
        cmds.warning("No bookmark items found in scene")
        return
    if missing:
        cmds.warning(
            "{} bookmark item(s) not found in scene".format(len(missing))
        )
    if mode == "add":
        cmds.select(valid, add=True)
    elif mode == "deselect":
        cmds.select(valid, deselect=True)
    else:
        cmds.select(valid, replace=True)


def add_selected_to_bookmark(bookmark):
    """Add the current Maya selection to a bookmark's items.

    Args:
        bookmark (dict): The bookmark dictionary to modify.

    Returns:
        int: Number of items added.
    """
    sel = cmds.ls(selection=True, long=True, flatten=True)
    if not sel:
        return 0
    existing = set(bookmark["items"])
    new_items = [
        item for item in (to_storage_form(s) for s in sel)
        if item not in existing
    ]
    bookmark["items"].extend(new_items)
    return len(new_items)


def remove_selected_from_bookmark(bookmark):
    """Remove the current Maya selection from a bookmark's items.

    Args:
        bookmark (dict): The bookmark dictionary to modify.

    Returns:
        int: Number of items removed.
    """
    sel = cmds.ls(selection=True, long=True, flatten=True) or []
    if not sel:
        return 0
    sel_storage = {to_storage_form(s) for s in sel}
    original_count = len(bookmark["items"])
    bookmark["items"] = [
        i for i in bookmark["items"] if i not in sel_storage
    ]
    return original_count - len(bookmark["items"])


def key_bookmark_members(bookmark, namespace=None):
    """Key all keyable attributes of a selection bookmark's nodes.

    Components and nodes without keyable attributes are skipped. The
    selection does not change, and the keying is one undo step.

    Args:
        bookmark (dict): The bookmark dictionary.
        namespace (str, optional): Namespace for a bookmark with
            ``use_selected_namespace`` on, see
            :func:`resolve_bookmark_items`.

    Returns:
        list: The keyed nodes.
    """
    if bookmark.get("type") != BOOKMARK_SELECTION:
        return []
    try:
        valid, _missing = resolve_bookmark_items(bookmark, namespace)
    except RuntimeError as e:
        cmds.warning(str(e))
        return []
    nodes = anim_utils.keyable_nodes(valid)
    if not nodes:
        cmds.warning("No keyable bookmark items found in scene")
        return []
    cmds.undoInfo(openChunk=True, chunkName="keyBookmarkMembers")
    try:
        cmds.setKeyframe(nodes)
    finally:
        cmds.undoInfo(closeChunk=True)
    return nodes


#############################################
# ISOLATE LOGIC
#############################################


def toggle_isolate(bookmark):
    """Toggle isolate visibility for bookmark items in the active viewport.

    For components, extracts parent transforms to isolate the objects
    and selects the components so Maya displays them in isolate mode.
    Uses enableIsolateSelect MEL command to properly sync the viewport
    toolbar button.

    Args:
        bookmark (dict): The bookmark dictionary.
    """
    try:
        valid, missing = resolve_bookmark_items(bookmark)
    except RuntimeError as e:
        cmds.warning(str(e))
        return
    if not valid:
        cmds.warning("No bookmark items found in scene")
        return
    if missing:
        cmds.warning(
            "{} bookmark item(s) not found in scene".format(len(missing))
        )

    panel = _get_active_model_panel()
    if not panel:
        cmds.warning("No active model panel found")
        return

    is_isolated = cmds.isolateSelect(panel, query=True, state=True)
    if is_isolated:
        mel.eval("enableIsolateSelect {} {}".format(panel, 0))
    else:
        # Isolate builds its object set from the selection, so select the
        # items to capture them (objects and components alike), then restore
        # whatever the user had selected -- clicking an isolate bookmark
        # should not change the current selection.
        prev_sel = cmds.ls(selection=True, long=True) or []
        cmds.select(valid, replace=True)
        mel.eval("enableIsolateSelect {} {}".format(panel, 1))
        cmds.isolateSelect(panel, addSelectedObjects=True)
        if prev_sel:
            cmds.select(prev_sel, replace=True)
        else:
            cmds.select(clear=True)


def _get_active_model_panel():
    """Get the active model panel name.

    Returns:
        str: Model panel name, or None if none found.
    """
    panel = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    panels = cmds.getPanel(type="modelPanel") or []
    return panels[0] if panels else None


#############################################
# CONFIGURATION
#############################################


def bookmarks_to_config(bookmarks, layout="horizontal"):
    """Convert bookmarks list to exportable config dictionary.

    Args:
        bookmarks (list): List of bookmark dicts.
        layout (str): Layout mode.

    Returns:
        dict: Configuration dictionary.
    """
    return {
        "version": CONFIG_VERSION,
        "layout": layout,
        "bookmarks": [
            {
                "name": bm["name"],
                "color": list(bm["color"]),
                "type": bm["type"],
                "items": list(bm["items"]),
                "use_selected_namespace": bool(
                    bm.get("use_selected_namespace", False)
                ),
                # copied whole, so settings of unknown tools are kept
                "tools": copy.deepcopy(bm.get("tools", {})),
            }
            for bm in bookmarks
        ],
    }


def config_to_bookmarks(config):
    """Extract bookmarks list and layout from config dictionary.

    Args:
        config (dict): Configuration dictionary.

    Returns:
        tuple: (list of bookmark dicts, layout string).
    """
    version = config.get("version", LEGACY_CONFIG_VERSION)
    layout = config.get("layout", "horizontal")
    bookmarks = []
    for raw in config.get("bookmarks", []):
        items = raw.get("items", [])
        if version == LEGACY_CONFIG_VERSION:
            # Legacy schema stored full DAG paths; trim to storage form
            # (namespace:short[.component]) so the resolver can match.
            items = [to_storage_form(i) for i in items]
        bookmarks.append({
            "name": raw.get("name", "Bookmark"),
            "color": list(raw.get("color", random_pastel_color())),
            "type": raw.get("type", BOOKMARK_SELECTION),
            "items": items,
            "use_selected_namespace": bool(
                raw.get("use_selected_namespace", False)
            ),
            "tools": copy.deepcopy(raw.get("tools", {})),
        })
    return bookmarks, layout


#############################################
# EXPORT / IMPORT
#############################################


def export_bookmarks(file_path, bookmarks, layout="horizontal"):
    """Export bookmarks to a JSON file.

    Args:
        file_path (str): Path to save the .sbk file.
        bookmarks (list): List of bookmark dicts.
        layout (str): Current layout mode.

    Returns:
        bool: True if successful.
    """
    if not file_path.endswith(CONFIG_FILE_EXT):
        file_path += CONFIG_FILE_EXT
    config = bookmarks_to_config(bookmarks, layout)
    try:
        with open(file_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.info("Exported bookmarks to %s", file_path)
        return True
    except Exception as e:
        cmds.warning("Failed to export bookmarks: {}".format(e))
        return False


def import_bookmarks(file_path):
    """Import bookmarks from a JSON file.

    Args:
        file_path (str): Path to the .sbk file.

    Returns:
        dict: Configuration dictionary, or None if failed.
    """
    try:
        with open(file_path, "r") as f:
            config = json.load(f)
        logger.info("Imported bookmarks from %s", file_path)
        return config
    except Exception as e:
        cmds.warning("Failed to import bookmarks: {}".format(e))
        return None


#############################################
# SCENE STORAGE
#############################################

# Cache to avoid scanning all network nodes on every save
_scene_node_cache = None


def save_to_scene(bookmarks, layout="horizontal"):
    """Save bookmarks to a network node in the Maya scene.

    Creates or updates the network node with JSON-serialized data.

    Args:
        bookmarks (list): List of bookmark dicts.
        layout (str): Current layout mode.

    Returns:
        bool: True if successful.
    """
    config = bookmarks_to_config(bookmarks, layout)
    try:
        node = _get_or_create_scene_node()
        cmds.setAttr(
            "{}.{}".format(node, SCENE_NODE_DATA_ATTR),
            json.dumps(config),
            type="string",
        )
        return True
    except Exception as e:
        cmds.warning("Failed to save bookmarks to scene: {}".format(e))
        return False


def load_from_scene():
    """Load bookmarks from the scene's network node.

    Returns:
        dict: Configuration dictionary, or None if no node exists.
    """
    node = _find_scene_node()
    if not node:
        return None
    try:
        data = cmds.getAttr("{}.{}".format(node, SCENE_NODE_DATA_ATTR))
        if not data:
            return None
        return json.loads(data)
    except Exception as e:
        cmds.warning("Failed to load bookmarks from scene: {}".format(e))
        return None


def _get_or_create_scene_node():
    """Get existing or create new network node for storage.

    Returns:
        str: The network node name.
    """
    node = _find_scene_node()
    if node:
        return node
    node = cmds.createNode("network", name=SCENE_NODE_NAME)
    cmds.addAttr(
        node,
        longName=SCENE_NODE_TYPE_ATTR,
        attributeType="bool",
        defaultValue=True,
    )
    cmds.addAttr(node, longName=SCENE_NODE_DATA_ATTR, dataType="string")
    global _scene_node_cache
    _scene_node_cache = node
    return node


def _find_scene_node():
    """Find the bookmarks network node in the scene.

    Uses cached name first, falls back to scanning network nodes.

    Returns:
        str: Node name, or None if not found.
    """
    global _scene_node_cache
    if _scene_node_cache and cmds.objExists(_scene_node_cache):
        return _scene_node_cache

    # Fast path: check well-known name
    if cmds.objExists(SCENE_NODE_NAME):
        if cmds.attributeQuery(
            SCENE_NODE_TYPE_ATTR, node=SCENE_NODE_NAME, exists=True
        ):
            _scene_node_cache = SCENE_NODE_NAME
            return SCENE_NODE_NAME

    # Slow path: scan all network nodes (handles renamed nodes)
    for node in cmds.ls(type="network") or []:
        if cmds.attributeQuery(
            SCENE_NODE_TYPE_ATTR, node=node, exists=True
        ):
            _scene_node_cache = node
            return node
    return None


#############################################
# SHELF
#############################################


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
        current_shelf = mel.eval(
            "tabLayout -query -selectTab $gShelfTopLevel"
        )
    except Exception:
        cmds.warning("Could not find current shelf")
        return None

    name = bookmark["name"]
    r, g, b = bookmark["color"]
    bm_data = json.dumps(bookmark)
    is_selection = bookmark["type"] == BOOKMARK_SELECTION

    command = (
        "from mgear.utilbits.bookmarks import core\n"
        "import json\n"
        "bm = json.loads({data!r})\n"
    ).format(data=bm_data)

    if is_selection:
        command += (
            "import maya.cmds as cmds\n"
            "mods = cmds.getModifiers()\n"
            "if mods & 1:\n"
            "    core.recall_selection(bm, 'add')\n"
            "elif mods & 4:\n"
            "    core.recall_selection(bm, 'deselect')\n"
            "else:\n"
            "    core.recall_selection(bm, 'replace')\n"
        )
        icon = get_icon_path("mgear_mouse-pointer.svg")
    else:
        command += "core.toggle_isolate(bm)\n"
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
