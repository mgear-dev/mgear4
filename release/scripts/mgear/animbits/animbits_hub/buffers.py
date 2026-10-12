"""Pose buffers of the Animbits Hub rows, kept for the Maya session.

Rows are rebuilt each time the hub shows, so their buffers live here,
keyed by row. They are cleared on a new or opened scene, also while the
hub is hidden. No Qt code.
"""

import time

import maya.api.OpenMaya as om2
from maya import cmds

from mgear.core import anim_utils
from mgear.core import callbackManager
from mgear.core import node_remap

_buffers = {}
_callbacks = None


class PoseBuffer(object):
    """A stored pose: attribute values of a list of nodes.

    Args:
        values (dict): ``{node: {attribute: value}}``, nodes in stored
            order.
        frame (float): Frame the pose was stored on.
        namespace (str): Namespace of the first node, empty for the root.
        created (float, optional): Store time, seconds since the epoch.
            Defaults to now.
    """

    def __init__(self, values, frame, namespace, created=None):
        self.values = values
        self.frame = frame
        self.namespace = namespace
        self.created = time.time() if created is None else created

    def describe(self):
        """Return a one line summary, e.g. for a tooltip.

        Returns:
            str: ``"Frame 24 · 18 controls · chrA · 14:32"``.
        """
        count = len(self.values)
        return "Frame {:g} · {} control{} · {} · {}".format(
            self.frame,
            count,
            "" if count == 1 else "s",
            self.namespace or ":",
            time.strftime("%H:%M", time.localtime(self.created)),
        )


def capture_pose(nodes, frame=None):
    """Store the keyable values of nodes.

    Args:
        nodes (list): Node names.
        frame (float, optional): Frame to record in the buffer. Defaults to
            the current time.

    Returns:
        PoseBuffer: The buffer, empty when no node has a keyable value.
    """
    if frame is None:
        frame = cmds.currentTime(query=True)
    values = anim_utils.get_pose_values(nodes)
    namespace = node_remap.get_namespace(next(iter(values), "")).rstrip(":")
    return PoseBuffer(values, frame, namespace)


def buffer_values(buffer, targets):
    """Map a buffer onto target nodes with ``node_remap.match_nodes``.

    Args:
        buffer (PoseBuffer): The stored pose.
        targets (list): Nodes to paste on. Empty to use the stored nodes.

    Returns:
        dict: ``{target: {attribute: value}}``.
    """
    matches = node_remap.match_nodes(list(buffer.values), targets)
    return {target: buffer.values[source] for source, target in matches.items()}


def store_buffer(row_key, buffer):
    """Store the buffer of a row, replacing the previous one.

    Args:
        row_key (str): Row key, e.g. ``"selection"``.
        buffer (PoseBuffer): The buffer.
    """
    _start_callbacks()
    _buffers[row_key] = buffer


def get_buffer(row_key):
    """Return the buffer of a row.

    Args:
        row_key (str): Row key.

    Returns:
        PoseBuffer: The buffer, or None.
    """
    return _buffers.get(row_key)


def clear_buffer(row_key):
    """Remove the buffer of a row.

    Args:
        row_key (str): Row key.
    """
    _buffers.pop(row_key, None)


def clear_all(*args):
    """Remove every buffer."""
    _buffers.clear()


def _start_callbacks():
    """Clear the buffers on new and opened scenes, once per session."""
    global _callbacks
    if _callbacks is not None:
        return
    _callbacks = callbackManager.CallbackManager()
    _callbacks.sceneMessageCB("beforeNew", clear_all, om2.MSceneMessage.kBeforeNew)
    _callbacks.sceneMessageCB("beforeOpen", clear_all, om2.MSceneMessage.kBeforeOpen)
