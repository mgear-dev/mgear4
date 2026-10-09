"""Space Recorder: record world transforms over time and apply them back.

Records the world matrix of objects on every frame of a range, and keys
them back at those world positions later, on the same objects (after a
space switch, a reparent or a parent edit) or on other objects.

The record and apply functions are Qt-free; the window keeps three
buffers (A, B and C) for the Maya session.
"""

from mgear.core import anim_utils
from mgear.core import pyqt
from mgear.core import utils

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtWidgets

from maya import cmds
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

BUFFER_NAMES = ("A", "B", "C")
EMPTY = "empty"

# recordings of the window buffers, kept for the Maya session
BUFFERS = {}


class Recording(object):
    """World matrices of objects, by frame number."""

    def __init__(self, objects, frames):
        """Initialize the recording.

        Args:
            objects (list): Recorded objects, full DAG paths.
            frames (dict): ``{frame: [world matrix per object]}``.
        """
        self.objects = list(objects)
        self.frames = dict(frames)

    @property
    def frame_range(self):
        """tuple: First and last recorded frame, or None when empty."""
        if not self.frames:
            return None
        return min(self.frames), max(self.frames)

    def describe(self):
        """Return a short description of the recording.

        Returns:
            str: e.g. ``"3 objects, frames 1-24"``, or :data:`EMPTY`.
        """
        frame_range = self.frame_range
        if not frame_range:
            return EMPTY
        return "{} object{}, frames {:g}-{:g}".format(
            len(self.objects), "" if len(self.objects) == 1 else "s", *frame_range
        )


def record(objects=None, start=None, end=None):
    """Record the world matrices of objects on every frame of a range.

    The current time is restored afterwards. Esc cancels; the frames
    recorded so far are kept.

    Args:
        objects (list, optional): Transforms. Default: the selection.
        start (float, optional): First frame. Default: playback start.
        end (float, optional): Last frame. Default: playback end.

    Returns:
        Recording: The recording, or None when there is nothing to record.
    """
    objects = cmds.ls(objects or cmds.ls(selection=True), long=True, transforms=True)
    if not objects:
        cmds.warning("Space Recorder: select the objects to record")
        return None
    frames = anim_utils.record_world_matrices(
        objects, start, end, "Recording world spaces"
    )
    return Recording(objects, frames)


def apply(recording, targets=None, start=None, end=None):
    """Key the recorded world matrices on the recorded or other objects.

    Only the recorded frames inside the range are applied. Targets are
    paired with the recorded objects in order, and parents are applied
    before their children on each frame. Only the settable translate,
    rotate and scale channels are keyed. One undo step; the current time
    is restored and Esc cancels.

    Args:
        recording (Recording): The recording.
        targets (list, optional): Objects receiving the motion, paired by
            order with the recorded objects. Default: the recorded objects.
        start (float, optional): First frame. Default: playback start.
        end (float, optional): Last frame. Default: playback end.

    Returns:
        dict: Report with ``applied_frames`` (list), ``skipped_frames``
        (frames of the range that were not recorded), ``unused_targets``
        (targets beyond the recorded objects) and ``missing_objects``
        (recorded objects that no longer exist).
    """
    report = {
        "applied_frames": [],
        "skipped_frames": [],
        "unused_targets": [],
        "missing_objects": [],
    }
    if targets is None:
        pairs = [
            (index, node)
            for index, node in enumerate(recording.objects)
            if cmds.objExists(node)
        ]
        report["missing_objects"] = [
            node for node in recording.objects if not cmds.objExists(node)
        ]
    else:
        # one by one: the pairing follows the given order
        resolved = []
        for node in targets:
            resolved.extend(cmds.ls(node, long=True, transforms=True)[:1])
        count = min(len(resolved), len(recording.objects))
        pairs = list(enumerate(resolved[:count]))
        report["unused_targets"] = resolved[count:]
    start, end = anim_utils.get_playback_range(start, end)
    frames = {}
    for frame in range(int(round(start)), int(round(end)) + 1):
        if frame in recording.frames:
            matrices = recording.frames[frame]
            frames[frame] = [matrices[index] for index, _ in pairs]
        else:
            report["skipped_frames"].append(frame)
    if not pairs or not frames:
        return report
    with utils.undo_chunk("spaceRecorderApply"):
        report["applied_frames"] = anim_utils.key_world_matrices(
            [node for _, node in pairs], frames, "Applying world spaces"
        )
    return report


def warn_report(report):
    """Show warnings for the skipped parts of an apply report.

    Args:
        report (dict): Report from :func:`apply`.
    """
    if report["skipped_frames"]:
        frames = report["skipped_frames"]
        cmds.warning(
            "Space Recorder: {} frames of the range were not recorded "
            "({:g}-{:g}), they were skipped".format(len(frames), frames[0], frames[-1])
        )
    if report["unused_targets"]:
        cmds.warning(
            "Space Recorder: more objects selected than recorded, not used: "
            "{}".format(", ".join(cmds.ls(report["unused_targets"])))
        )
    if report["missing_objects"]:
        cmds.warning(
            "Space Recorder: recorded objects not found: {}".format(
                ", ".join(report["missing_objects"])
            )
        )


class SpaceRecorderUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    """Space Recorder window with three buffers."""

    def __init__(self, parent=None):
        super(SpaceRecorderUI, self).__init__(parent)
        self.record_buttons = {}
        self.apply_buttons = {}
        self.apply_selected_buttons = {}

        self.setWindowTitle("World Space Recorder")
        self.setMinimumWidth(275)
        self.setWindowFlags(QtCore.Qt.Tool)
        # Delete UI on close to avoid winEvent error
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.create_widgets()
        self.create_layout()
        self.create_connections()
        self.update_buttons()

    def create_widgets(self):
        for name in BUFFER_NAMES:
            self.record_buttons[name] = QtWidgets.QPushButton(
                "Record Buffer {}".format(name)
            )
            self.apply_buttons[name] = QtWidgets.QPushButton(
                "Apply Buffer {}".format(name)
            )
            self.apply_selected_buttons[name] = QtWidgets.QPushButton(
                "Apply Sel Buffer {}".format(name)
            )

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        for title, buttons in (
            ("Record World Spaces", self.record_buttons),
            ("Apply World Spaces", self.apply_buttons),
            ("Apply to Selection", self.apply_selected_buttons),
        ):
            group = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QHBoxLayout(group)
            for name in BUFFER_NAMES:
                layout.addWidget(buttons[name])
            main_layout.addWidget(group)
        main_layout.addStretch()

    def create_connections(self):
        for name in BUFFER_NAMES:
            self.record_buttons[name].clicked.connect(
                lambda *args, n=name: self.record(n)
            )
            self.apply_buttons[name].clicked.connect(
                lambda *args, n=name: self.apply(n)
            )
            self.apply_selected_buttons[name].clicked.connect(
                lambda *args, n=name: self.apply(n, selection=True)
            )

    def update_buttons(self):
        """Show what each buffer holds on its apply buttons."""
        for name in BUFFER_NAMES:
            recording = BUFFERS.get(name)
            text = recording.describe() if recording else EMPTY
            for buttons in (self.apply_buttons, self.apply_selected_buttons):
                buttons[name].setEnabled(bool(recording and recording.frames))
                buttons[name].setToolTip("Buffer {}: {}".format(name, text))
            self.record_buttons[name].setToolTip(
                "Record the selection over the playback range "
                "(buffer {}: {})".format(name, text)
            )

    def record(self, name):
        """Record the selection in a buffer.

        Args:
            name (str): Buffer name.
        """
        recording = record()
        if recording:
            BUFFERS[name] = recording
        self.update_buttons()

    def apply(self, name, selection=False):
        """Apply a buffer to its objects or to the selection.

        Args:
            name (str): Buffer name.
            selection (bool, optional): Apply to the selected objects, by
                order, instead of the recorded objects.
        """
        recording = BUFFERS.get(name)
        if not recording:
            cmds.warning("Space buffer is empty. Please record before")
            return
        targets = None
        if selection:
            targets = cmds.ls(selection=True, transforms=True)
            if not targets:
                cmds.warning("Please select object to apply spaces")
                return
        warn_report(apply(recording, targets))


def open(*args):
    return pyqt.showDialog(SpaceRecorderUI)


if __name__ == "__main__":
    open()
