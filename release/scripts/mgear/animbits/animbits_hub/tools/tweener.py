"""Tweener tool of the Animbits Hub.

One slider for the selection, then one for each selection bookmark with
the tweener enabled. The hub mode bar sets the slider mode of every row:
tween between keys, blend to the default, mirror or stored pose, or push
and pull the pose (see ``modes``).
"""

from maya import cmds

from mgear.core import anim_utils
from mgear.core import pyqt
from mgear.core import utils
from mgear.utilbits.bookmarks import core as bm_core

from .. import buffers
from .. import modes
from .. import registry
from .. import settings as hub_settings
from ..widgets import BufferButton
from ..widgets import HubRow
from ..widgets import TweenSlider
from ..widgets import mode_tooltip

TOOL_ID = "tweener"
TOOL_LABEL = "Tweener"
SELECTION_ROW_NAME = "Selection"
NOTHING_TO_TWEEN = "Nothing to tween: no animated attribute with keys on both sides"
NOTHING_TO_BLEND = "Nothing to blend: the controls are already at the target"
NO_BUFFER = "No pose stored on {}: click the circle on the left of the row"
UNDO_CHUNK = "animbitsHubBlend"


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


def row_key(bookmark=None):
    """Return the key of a row, e.g. for its pose buffer.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection row.

    Returns:
        str: ``"selection"`` or ``"bookmark:<name>"``.
    """
    if bookmark is None:
        return "selection"
    return "bookmark:{}".format(bookmark["name"])


def build_cache(mode_id, bookmark=None, namespace=None):
    """Return the blend cache of a row in a slider mode.

    Args:
        mode_id (str): The slider mode id.
        bookmark (dict, optional): The row bookmark. None for the
            selection.
        namespace (str, optional): Hub namespace, for a bookmark with
            ``use_selected_namespace`` on.

    Returns:
        list: ``(plug, a, b, animated)`` tuples.
    """
    nodes = tween_targets(bookmark, namespace)
    mode = modes.get_mode(mode_id)
    if mode.build_cache:
        return mode.build_cache(nodes)
    buffer = buffers.get_buffer(row_key(bookmark))
    if buffer is None:
        return []
    # nothing selected on the selection row: paste on the stored controls
    return anim_utils.get_buffer_cache(buffers.buffer_values(buffer, nodes))


class TweenRow(HubRow):
    """Hub row with a blend slider for the selection or a bookmark.

    The blend cache of the active mode is collected when the handle is
    pressed, and the whole drag is one undo step. In the buffer mode a
    circle on the left stores the pose of the row.

    Args:
        spec (dict): Row spec from :func:`row_specs`.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, spec, parent=None):
        super(TweenRow, self).__init__(spec["name"], spec["color"], parent)
        self.bookmark = spec["bookmark"]
        self.row_key = row_key(self.bookmark)
        self.uses_namespace = bool(
            self.bookmark and self.bookmark.get("use_selected_namespace")
        )
        self.mode = modes.get_mode(modes.TWEEN)
        self._cache = None
        self._time = None
        self._chunk_open = False

        self.slider = TweenSlider(spec["color"])
        self.set_content(self.slider)
        self.buffer_button = BufferButton(spec["color"])
        self.add_leading(self.buffer_button)

        self.slider.pressed.connect(self._on_pressed)
        self.slider.drag_started.connect(self._on_drag_started)
        self.slider.fraction_changed.connect(self._on_fraction_changed)
        self.slider.drag_finished.connect(self._on_drag_finished)
        self.slider.stop_clicked.connect(self._on_stop_clicked)
        self.buffer_button.store_requested.connect(self.store_buffer)
        self.buffer_button.clear_requested.connect(self.clear_buffer)
        self._update_buffer_button()

    # mode and tooltips ------------------------------------------------

    def set_mode(self, mode):
        """Set the slider mode: handle label and buffer button.

        Args:
            mode (SliderMode): The mode.
        """
        self.mode = mode
        self.slider.set_label(mode.label)
        self.buffer_button.set_active(mode.mode_id == modes.BUFFER)
        self._update_buffer_button()

    def set_unit(self, unit):
        """Scale the row, buffer button included.

        Args:
            unit (float): Size unit in pixels.
        """
        super(TweenRow, self).set_unit(unit)
        self.buffer_button.set_unit(unit)

    def set_show_tooltips(self, show):
        """Show rich help tooltips, or only the row name.

        Args:
            show (bool): True for rich tooltips.
        """
        super(TweenRow, self).set_show_tooltips(show)
        self._update_buffer_button()

    def hover_tooltip(self):
        """Return the mode help titled with the row name, or the name.

        Returns:
            str: Plain or rich text, None for no tooltip.
        """
        if not self._show_tooltips:
            return super(TweenRow, self).hover_tooltip()
        title = self.mode.title
        if self._show_names == hub_settings.SHOW_NAMES_HOVER:
            title = "{} · {}".format(title, self.name)
        return mode_tooltip(self.mode, title)

    # buffer -----------------------------------------------------------

    def store_buffer(self):
        """Store the pose of the row targets as the row buffer."""
        nodes = tween_targets(self.bookmark, self.namespace)
        buffer = buffers.capture_pose(nodes) if nodes else None
        if not buffer or not buffer.values:
            cmds.warning("Nothing to store: no keyable control in {}".format(self.name))
            return
        buffers.store_buffer(self.row_key, buffer)
        self._update_buffer_button()

    def clear_buffer(self):
        """Remove the row buffer."""
        buffers.clear_buffer(self.row_key)
        self._update_buffer_button()

    def _update_buffer_button(self):
        buffer = buffers.get_buffer(self.row_key)
        self.buffer_button.set_filled(buffer is not None)
        state = buffer.describe() if buffer else "No pose stored"
        if not self.buffer_button.active:
            tooltip = ""
        elif self._show_tooltips:
            mode = modes.get_mode(modes.BUFFER)
            tooltip = pyqt.rich_tooltip(
                "Pose Buffer · {}".format(self.name),
                state,
                (
                    "Click to store the pose of this row.",
                    "Ctrl+click to clear it.",
                ),
                mode.color,
            )
        else:
            tooltip = state
        self.buffer_button.setToolTip(tooltip)

    # blending ---------------------------------------------------------

    def _collect(self):
        return build_cache(self.mode.mode_id, self.bookmark, self.namespace)

    def _empty_message(self):
        if self.mode.mode_id == modes.BUFFER and not buffers.get_buffer(self.row_key):
            return NO_BUFFER.format(self.name)
        if self.mode.mode_id in (modes.TWEEN, modes.PUSH):
            return NOTHING_TO_TWEEN
        return NOTHING_TO_BLEND

    def _on_pressed(self):
        self._cache = self._collect()
        self._time = cmds.currentTime(query=True)

    def _on_drag_started(self):
        if self._cache:
            # the drag spans many events, so the chunk can't be a with block
            cmds.undoInfo(openChunk=True, chunkName=UNDO_CHUNK)
            self._chunk_open = True
        else:
            cmds.warning(self._empty_message())
        self.drag_started.emit(self)

    def _on_fraction_changed(self, fraction):
        if self._cache:
            anim_utils.apply_blend(
                self._cache, self.mode.weight_from_fraction(fraction), self._time
            )

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
            cmds.warning(self._empty_message())
            return
        with utils.undo_chunk(UNDO_CHUNK):
            anim_utils.apply_blend(cache, self.mode.weight_from_fraction(fraction))


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
