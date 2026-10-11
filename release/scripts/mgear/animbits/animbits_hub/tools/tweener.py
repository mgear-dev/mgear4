"""Tweener tool of the Animbits Hub.

One slider for the selection, then one for each selection bookmark with
the tweener enabled. Dragging the ``TW`` handle keys the animated
attributes between their previous and next keys, as a tween machine.
"""

from maya import cmds

from mgear.core import anim_utils
from mgear.utilbits.bookmarks import core as bm_core

from .. import registry
from ..widgets import HubRow
from ..widgets import TweenSlider

TOOL_ID = "tweener"
TOOL_LABEL = "Tweener"
SELECTION_ROW_NAME = "Selection"
NOTHING_TO_TWEEN = "Nothing to tween: no animated attribute with keys on both sides"


def scene_bookmarks():
    """Return the bookmarks stored in the scene.

    Returns:
        list: Bookmark dictionaries.
    """
    config = bm_core.load_from_scene()
    if not config:
        return []
    return bm_core.config_to_bookmarks(config)[0]


def row_specs(bookmarks, selection_color):
    """Return the rows of the tweener, the selection row first.

    Args:
        bookmarks (list): Bookmark dictionaries.
        selection_color (tuple): RGB 0-1 color of the selection row.

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
    for bookmark in bm_core.bookmarks_for_tool(bookmarks, TOOL_ID):
        specs.append(
            {
                "name": bookmark["name"],
                "color": tuple(bookmark["color"]),
                "bookmark": bookmark,
            }
        )
    return specs


def tween_targets(bookmark=None, namespace=None):
    """Return the keyable nodes a row tweens.

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
            items, _missing = bm_core.resolve_bookmark_items(bookmark, namespace)
        except RuntimeError as e:
            cmds.warning(str(e))
            return []
    return anim_utils.keyable_nodes(items)


class TweenRow(HubRow):
    """Hub row with a tween slider for the selection or a bookmark.

    The tween cache is collected when the handle is pressed, and the
    whole drag is one undo step.

    Args:
        spec (dict): Row spec from :func:`row_specs`.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, spec, parent=None):
        super(TweenRow, self).__init__(spec["name"], spec["color"], parent)
        self.bookmark = spec["bookmark"]
        self.uses_namespace = bool(
            self.bookmark and self.bookmark.get("use_selected_namespace")
        )
        self._cache = None
        self._chunk_open = False

        self.slider = TweenSlider(spec["color"])
        self.set_content(self.slider)
        self.slider.pressed.connect(self._on_pressed)
        self.slider.drag_started.connect(self._on_drag_started)
        self.slider.fraction_changed.connect(self._on_fraction_changed)
        self.slider.drag_finished.connect(self._on_drag_finished)
        self.slider.stop_clicked.connect(self._on_stop_clicked)

    def _collect(self):
        nodes = tween_targets(self.bookmark, self.namespace)
        return anim_utils.get_tween_cache(nodes)

    def _on_pressed(self):
        self._cache = self._collect()

    def _on_drag_started(self):
        if self._cache:
            cmds.undoInfo(openChunk=True, chunkName="animbitsHubTween")
            self._chunk_open = True
        else:
            cmds.warning(NOTHING_TO_TWEEN)
        self.drag_started.emit(self)

    def _on_fraction_changed(self, fraction):
        if self._cache:
            anim_utils.apply_tween(self._cache, fraction)

    def _on_drag_finished(self):
        try:
            if self._chunk_open:
                cmds.undoInfo(closeChunk=True)
        finally:
            self._chunk_open = False
            self._cache = None
            self.drag_finished.emit(self)

    def _on_stop_clicked(self, fraction):
        cache = self._collect()
        if not cache:
            cmds.warning(NOTHING_TO_TWEEN)
            return
        cmds.undoInfo(openChunk=True, chunkName="animbitsHubTween")
        try:
            anim_utils.apply_tween(cache, fraction)
        finally:
            cmds.undoInfo(closeChunk=True)


def build_rows(context):
    """Build the tweener rows of the hub.

    Args:
        context (HubContext): The hub context.

    Returns:
        list: TweenRow widgets.
    """
    specs = row_specs(scene_bookmarks(), context.settings.selection_color)
    return [TweenRow(spec) for spec in specs]


registry.register_tool(TOOL_ID, build_rows, order=10)
bm_core.register_bookmark_tool(TOOL_ID, TOOL_LABEL)
