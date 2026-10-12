"""Key tools of the Animbits Hub: Nudge Keys and Copy/Paste World Pose.

They sit in the hub tool area, above the sliders: one row for the
selection, then one per selection bookmark enabled for Key Tools in the
bookmark "Show In Tools" menu. Every row has its own nudge amount, ripple
and world pose buffer.
"""

from maya import cmds

from mgear.core import anim_utils
from mgear.core import attribute
from mgear.core import node_remap
from mgear.core import utils
from mgear.utilbits.bookmarks import core as bm_core

from . import common
from .. import buffers
from .. import registry
from ..widgets import HubToolButton
from ..widgets import HubToolRow
from ..widgets import NudgeWidget

TOOL_ID = "key_tools"
TOOL_LABEL = "Key Tools"
NOTHING_TO_NUDGE = "Nothing to nudge: select keys or controls with keys"
WORLD_COLOR = "#7fc97f"

KEYS = "keys"
RANGE = "range"
FRAME = "frame"


def channel_box_attributes():
    """Return the attributes selected in the Channel Box.

    Returns:
        list: Attribute names, or None when none are selected or there is
            no Channel Box (batch mode).
    """
    box = attribute.get_channelBox()
    if not box or not cmds.channelBox(box, exists=True):
        return None
    attrs = []
    for flag in (
        "selectedMainAttributes",
        "selectedShapeAttributes",
        "selectedHistoryAttributes",
    ):
        attrs.extend(cmds.channelBox(box, query=True, **{flag: True}) or [])
    return attrs or None


def resolve_nudge_target(bookmark=None, namespace=None):
    """Return what a nudge of a key tool row moves.

    Selection row, by priority:

    1. The selected keys.
    2. The keys of the selected controls in the timeline range selection.
    3. The keys of the selected controls on the current frame, only of the
       Channel Box selected attributes when there are some.

    Bookmark row: the keys of the bookmark controls in the timeline range
    selection, else on the current frame.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection row.
        namespace (str, optional): Hub namespace, for a bookmark with
            ``use_selected_namespace`` on.

    Returns:
        tuple: ``(KEYS, None)``, ``(RANGE, (nodes, start, end))``,
            ``(FRAME, (nodes, time, attributes))`` or ``(None, None)``.
    """
    if bookmark is None and anim_utils.has_selected_keys():
        return KEYS, None
    nodes = common.row_targets(bookmark, namespace)
    if not nodes:
        return None, None
    time_range = anim_utils.get_timeline_range()
    if time_range:
        return RANGE, (nodes, time_range[0], time_range[1])
    time = cmds.currentTime(query=True)
    attributes = channel_box_attributes() if bookmark is None else None
    return FRAME, (nodes, time, attributes)


def nudge(offset, ripple=False, bookmark=None, namespace=None):
    """Nudge the keys of a row in time and move the current time with them.

    Args:
        offset (int): Frames, negative to move back.
        ripple (bool, optional): Also move all the later keys.
        bookmark (dict, optional): The row bookmark. None for the
            selection row.
        namespace (str, optional): Hub namespace, for a bookmark with
            ``use_selected_namespace`` on.

    Returns:
        int: Number of moved keys. 0 when nothing moved; a warning tells
            why.
    """
    kind, payload = resolve_nudge_target(bookmark, namespace)
    if kind is None:
        cmds.warning(NOTHING_TO_NUDGE)
        return 0
    time = cmds.currentTime(query=True)
    try:
        with utils.undo_chunk("animbitsHubNudge"):
            if kind == KEYS:
                moved = anim_utils.nudge_selected_keys(offset, ripple)
            elif kind == RANGE:
                nodes, start, end = payload
                moved = anim_utils.nudge_keys(nodes, start, end, offset, ripple)
            else:
                nodes, frame, attributes = payload
                moved = anim_utils.nudge_keys(
                    nodes, frame, frame, offset, ripple, attributes
                )
            if moved:
                # in the same undo step, so one undo restores keys and time
                cmds.currentTime(time + offset, edit=True)
    except ValueError as e:
        cmds.warning(str(e))
        return 0
    if not moved:
        cmds.warning(NOTHING_TO_NUDGE)
    return moved


def world_buffer_key(bookmark=None):
    """Return the session buffer key of a row's world pose.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection row.

    Returns:
        str: ``"world_pose:<row key>"``.
    """
    return "{}:{}".format(buffers.WORLD_POSE, common.row_key(bookmark))


def _row_transforms(bookmark=None, namespace=None):
    if bookmark is None:
        return cmds.ls(selection=True, long=True, type="transform") or []
    nodes = common.row_targets(bookmark, namespace)
    if not nodes:
        return []
    return cmds.ls(nodes, long=True, type="transform") or []


def copy_world_pose(bookmark=None, namespace=None):
    """Store the world matrices of a row's controls.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection.
        namespace (str, optional): Hub namespace, for a bookmark with
            ``use_selected_namespace`` on.

    Returns:
        PoseBuffer: The world pose buffer, or None when there is no control.
    """
    nodes = _row_transforms(bookmark, namespace)
    if not nodes:
        cmds.warning("Nothing to copy: select the controls")
        return None
    matrices = anim_utils.get_world_matrices(nodes)
    buffer = buffers.new_buffer(dict(zip(nodes, matrices)))
    buffers.store_buffer(world_buffer_key(bookmark), buffer)
    return buffer


def paste_world_pose(bookmark=None, namespace=None):
    """Key a row's copied world pose on its controls.

    The selection row pastes on the selection, or on the copied controls
    when nothing is selected; a bookmark row on the bookmark controls.
    Pastes on every frame of the timeline range selection, otherwise on
    the current frame, parents before children, in one undo step.

    Args:
        bookmark (dict, optional): The row bookmark. None for the
            selection.
        namespace (str, optional): Hub namespace, for a bookmark with
            ``use_selected_namespace`` on.

    Returns:
        list: The keyed controls.
    """
    buffer = buffers.get_buffer(world_buffer_key(bookmark))
    if buffer is None:
        cmds.warning("Nothing to paste: copy a world pose first")
        return []
    targets = _row_transforms(bookmark, namespace)
    matches = node_remap.match_nodes(list(buffer.values), targets)
    if not matches:
        cmds.warning("No control to paste the world pose on")
        return []
    nodes = list(matches.values())
    matrices = [buffer.values[source] for source in matches]
    time_range = anim_utils.get_timeline_range()
    if time_range:
        frames = range(int(round(time_range[0])), int(round(time_range[1])) + 1)
    else:
        frames = [cmds.currentTime(query=True)]
    with utils.undo_chunk("animbitsHubPasteWorld"):
        anim_utils.key_world_matrices(
            nodes, {frame: matrices for frame in frames}, status="Pasting"
        )
    return nodes


class KeyToolRow(HubToolRow):
    """Key tools of the selection or of a bookmark: nudge, copy, paste.

    Args:
        spec (dict): Row spec from ``common.row_specs``.
        settings (HubSettings): The hub settings, for the row nudge
            amount and ripple.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, spec, settings, parent=None):
        bookmark = spec["bookmark"]
        color = spec["color"]
        key = common.row_key(bookmark)
        nudge_widget = NudgeWidget(
            settings.nudge_amount_for(key),
            settings.nudge_ripple_for(key),
            tint=color,
        )
        copy_button = HubToolButton(
            "mgear_copy",
            "Copy World Pose",
            "Store the world position, rotation and scale of the controls.",
            ("Paste it on other frames to plant a hand or a foot.",),
            WORLD_COLOR,
            tint=color,
        )
        paste_button = HubToolButton(
            "mgear_clipboard",
            "Paste World Pose",
            "Key the copied world pose on the controls.",
            (
                "Pastes on every frame of the timeline range selection, else "
                "on the current frame.",
                "Matched by name, then by name in another namespace, then by "
                "selection order.",
                "With nothing selected, the selection row pastes on the "
                "copied controls.",
            ),
            WORLD_COLOR,
            tint=color,
        )
        super(KeyToolRow, self).__init__(
            spec["name"], color, [nudge_widget, copy_button, paste_button], parent
        )
        self.bookmark = bookmark
        self.row_key = key
        self.uses_namespace = bool(bookmark and bookmark.get("use_selected_namespace"))
        self.nudge_widget = nudge_widget
        self.copy_button = copy_button
        self.paste_button = paste_button
        paste_button.state = self._world_pose_state

        nudge_widget.nudge_requested.connect(self._on_nudge)
        nudge_widget.amount_changed.connect(
            lambda amount: settings.set_nudge_amount(key, amount)
        )
        nudge_widget.ripple_changed.connect(
            lambda ripple: settings.set_nudge_ripple(key, ripple)
        )
        copy_button.clicked.connect(self._on_copy)
        paste_button.clicked.connect(self._on_paste)
        self._update_paste_button()

    def _buffer(self):
        return buffers.get_buffer(world_buffer_key(self.bookmark))

    def _world_pose_state(self):
        buffer = self._buffer()
        return buffer.describe() + "." if buffer else "Nothing copied."

    def _update_paste_button(self):
        self.paste_button.set_dim(self._buffer() is None)
        self.paste_button.update_tooltip()

    def _on_nudge(self, offset):
        nudge(offset, self.nudge_widget.ripple, self.bookmark, self.namespace)

    def _on_copy(self):
        if copy_world_pose(self.bookmark, self.namespace):
            self._update_paste_button()

    def _on_paste(self):
        paste_world_pose(self.bookmark, self.namespace)


def build_tool_rows(context):
    """Build the key tool rows: the selection, then the enabled bookmarks.

    Args:
        context (HubContext): The hub context.

    Returns:
        list: KeyToolRow widgets.
    """
    specs = common.row_specs(
        common.context_bookmarks(context), context.settings.selection_color, TOOL_ID
    )
    return [KeyToolRow(spec, context.settings) for spec in specs]


registry.register_tool(TOOL_ID, build_tool_rows, order=10, area=registry.AREA_TOOLS)
bm_core.register_bookmark_tool(TOOL_ID, TOOL_LABEL)
