"""HumanIK Mapper batch bake: bake many animation files onto the rig.

Each file is referenced, its HumanIK character is set as the source of
the mGear character and baked over the file's own frame range, in order
and in the same call.
"""

import json
import os

import mgear
from mgear.core import anim_utils
from mgear.core import string
from mgear.core import utils

from maya import cmds

from . import core

MODE_LAYERS = "layers"
MODE_TIMELINE = "timeline"

STATUS_BAKED = "baked"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"

_FILE_TYPES = {".fbx": "FBX", ".ma": "mayaAscii", ".mb": "mayaBinary"}


def read_file_list(path):
    """Read a ``.bkcn`` batch list.

    Args:
        path (str): File path.

    Returns:
        list: Animation file paths.
    """
    with open(path, "r") as stream:
        return list(json.load(stream))


def write_file_list(path, files):
    """Write a ``.bkcn`` batch list.

    Args:
        path (str): File path.
        files (list): Animation file paths.
    """
    with open(path, "w") as stream:
        json.dump(list(files), stream, indent=4)


def clean_name(path):
    """Return a valid Maya node name from a file or node name.

    Args:
        path (str): File path or name.

    Returns:
        str: The base name without extension, invalid characters replaced.
    """
    return string.normalize2(os.path.splitext(os.path.basename(path))[0])


def reference_file(path):
    """Reference an animation file in its own namespace.

    Args:
        path (str): ``.fbx``, ``.ma`` or ``.mb`` file.

    Returns:
        tuple: ``(reference file path, namespace)``.
    """
    file_type = _FILE_TYPES.get(os.path.splitext(path)[1].lower())
    if file_type == "FBX":
        utils.ensure_plugin("fbxmaya")
    kwargs = {"type": file_type} if file_type else {}
    # suffixed: a namespace would take the name of the file's layer
    namespace = clean_name(path) + "_src"
    reference = cmds.file(
        path, reference=True, namespace=namespace, returnNewNodes=False, **kwargs
    )
    namespace = cmds.referenceQuery(reference, namespace=True).lstrip(":")
    return reference, namespace


def file_frame_range(namespace):
    """Return the keyed frame range of a namespace's nodes.

    Args:
        namespace (str): Namespace of a referenced animation file.

    Returns:
        tuple: ``(start, end)``, or ``(None, None)`` when nothing is keyed.
    """
    times = anim_utils.get_keyframe_times(cmds.ls("{}:*".format(namespace)))
    if not times:
        return None, None
    return round(times[0]), round(times[-1])


def bake_to_clip(character, name, start=None, end=None, clip_start=None, **kwargs):
    """Bake the source and move the keys into a Time Editor clip.

    Args:
        character (str): The mGear HumanIK character.
        name (str): Clip name.
        start (float, optional): Bake start. Default: playback start.
        end (float, optional): Bake end. Default: playback end.
        clip_start (float, optional): Clip start frame. Default: ``start``.
        **kwargs: ``track`` (Time Editor track, default a new one) and the
            :func:`core.bake` options ``pre_roll``, ``mapping`` and
            ``unlock_channels``.

    Returns:
        int: The clip id.
    """
    track = kwargs.pop("track", None)
    mapping = kwargs.pop("mapping", None) or core.get_mapping(character)
    if start is None:
        start = cmds.playbackOptions(query=True, minTime=True)
    core.bake(character, start, end, mapping=mapping, **kwargs)
    return anim_utils.add_time_editor_clip(
        name,
        core.mapped_controls(mapping),
        start if clip_start is None else clip_start,
        track,
    )


def _report(path, status=STATUS_SKIPPED, message=""):
    return {"file": path, "status": status, "message": message, "range": None}


def bake_file(
    path,
    character,
    track=None,
    start_at=None,
    pre_roll=0,
    mapping=None,
    remove_reference=False,
):
    """Reference one animation file and bake it onto the mapped controls.

    Args:
        path (str): Animation file.
        character (str): The mGear HumanIK character.
        track (str, optional): Time Editor track: the file becomes a clip
            on it instead of an animation layer.
        start_at (float, optional): Clip start frame. Default: the file's
            start frame.
        pre_roll (int, optional): See :func:`core.bake`.
        mapping (dict, optional): The character's mapping, when known.
        remove_reference (bool, optional): Remove the file's reference after
            the bake, even when it fails.

    Returns:
        dict: Report with ``file``, ``status``, ``message``, ``range`` and,
        when baked, ``layer`` or ``clip``.
    """
    report = _report(path)
    mapping = mapping or core.get_mapping(character)
    reference, namespace = reference_file(path)
    try:
        sources = cmds.ls("{}:*".format(namespace), type="HIKCharacterNode")
        if not sources:
            report["message"] = "No HumanIK character in the file"
            return report
        start, end = file_frame_range(namespace)
        if start is None:
            start = cmds.playbackOptions(query=True, minTime=True)
            end = cmds.playbackOptions(query=True, maxTime=True)
        report["range"] = (start, end)
        core.set_source(character, sources[0], mapping=mapping, refresh_ui=False)
        name = clean_name(path)
        options = {"pre_roll": pre_roll, "mapping": mapping}
        if track:
            report["clip"] = bake_to_clip(
                character, name, start, end, start_at, track=track, **options
            )
        else:
            report["layer"] = core.bake(character, start, end, layer=name, **options)
        report["status"] = STATUS_BAKED
        return report
    finally:
        if remove_reference:
            cmds.file(reference, removeReference=True)


def batch_bake(
    files,
    mode=MODE_LAYERS,
    remove_references=False,
    character=None,
    start_frame=None,
    pre_roll=0,
    unlock_channels=False,
):
    """Bake animation files onto the mapped controls, one after the other.

    In layers mode each file bakes to an animation layer named after the
    file. In timeline mode each file becomes a Time Editor clip, placed
    right after the previous one. Files without a HumanIK character are
    skipped, and errors are reported per file. Esc cancels the remaining
    files.

    Args:
        files (list): ``.fbx``, ``.ma`` or ``.mb`` animation files.
        mode (str, optional): :data:`MODE_LAYERS` or :data:`MODE_TIMELINE`.
        remove_references (bool, optional): Remove each file's reference
            after its bake.
        character (str, optional): The mGear HumanIK character.
        start_frame (float, optional): Timeline mode: start of the first
            clip. Default: playback start.
        pre_roll (int, optional): See :func:`core.bake`.
        unlock_channels (bool, optional): See :func:`core.check_controls`.

    Returns:
        list: One report dict per processed file, see :func:`bake_file`.

    Raises:
        core.HumanIKMapperError: If nothing is mapped.
        core.LockedChannelsError: See :func:`core.check_controls`.
    """
    character = core.require_character(character)
    mapping = core.get_mapping(character)
    if not mapping:
        raise core.HumanIKMapperError("{} has no mapped controls".format(character))
    core.check_controls(core.mapped_controls(mapping), unlock_channels)
    timeline = mode == MODE_TIMELINE
    offset = start_frame
    if offset is None:
        offset = cmds.playbackOptions(query=True, minTime=True)
    first = offset
    reports = []
    track = None
    if timeline:
        cmds.timeEditor(mute=True)
        track = anim_utils.new_time_editor_track()
    try:
        with utils.main_progress_bar(
            "HumanIK batch bake", len(files), interruptable=True
        ) as step:
            for path in files:
                if step("Baking {}".format(os.path.basename(path))):
                    break
                try:
                    report = bake_file(
                        path,
                        character,
                        track,
                        offset,
                        pre_roll,
                        mapping,
                        remove_references,
                    )
                except Exception as error:
                    report = _report(path, STATUS_ERROR, str(error))
                    cmds.warning("HumanIK batch bake: {}: {}".format(path, error))
                reports.append(report)
                if timeline and report["range"]:
                    start, end = report["range"]
                    offset += end - start + 1
    finally:
        if timeline:
            cmds.timeEditor(mute=False)
        core.refresh_hik_ui()
    if timeline and offset > first:
        cmds.playbackOptions(minTime=first, maxTime=offset - 1)
    mgear.log(
        "HumanIK batch bake: {} of {} files baked".format(
            len([r for r in reports if r["status"] == STATUS_BAKED]), len(files)
        )
    )
    return reports
