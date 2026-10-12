"""Temp pivot: rotate animation controls around any point.

A temp pivot is a locator the controls follow. The flow is:

1. :func:`create` - add the locator, at a point to move where the pivot
   should be.
2. :func:`activate` - the locator follows the first control on the keyed
   frames, and every control follows a hidden child of the locator baked
   to its own animation. Nothing moves yet; rotating or keying the locator
   then moves all the controls around the pivot.
3. :func:`bake` keys the controls' new world poses and removes the temp
   pivot; :func:`cancel` removes it and leaves the animation as it was.

Everything is stored in the scene (a marked group), so a temp pivot saved
in a scene can be baked or cancelled after reopening it. No Qt code.

Example:
    >>> pivot = temp_pivot.create(cmds.ls(selection=True))
    >>> # move the locator, then
    >>> temp_pivot.activate(pivot)
    >>> # rotate and key the locator, then
    >>> temp_pivot.bake(pivot)
"""

import json

import maya.api.OpenMaya as om2
from maya import cmds

from mgear.core import anim_utils
from mgear.core import attribute
from mgear.core import utils

GROUP_NAME = "mgear_temp_pivot_grp"
LOCATOR_NAME = "mgear_temp_pivot"
FOLLOWER_NAME = "mgear_temp_pivot_follow"
MARKER_ATTR = "is_mgear_temp_pivot"
DATA_ATTR = "temp_pivot_data"

PLACE = "place"
ACTIVE = "active"

AXES = ("X", "Y", "Z")


#############################################
# SCENE STATE
#############################################


def _group():
    """Return the temp pivot group of the scene, or None.

    Looked up by name, in any namespace (e.g. a referenced scene), then
    checked for the marker attribute: much faster on heavy scenes than a
    search by attribute.
    """
    # a prefix, as Maya adds a number when the name is taken
    pattern = GROUP_NAME + "*"
    names = cmds.ls(pattern, long=True, recursive=True) or []
    for group in names:
        if cmds.attributeQuery(MARKER_ATTR, node=group, exists=True):
            return group
    return None


def _group_of(pivot):
    parents = cmds.listRelatives(pivot, parent=True, fullPath=True) or []
    if not parents or not cmds.attributeQuery(
        MARKER_ATTR, node=parents[0], exists=True
    ):
        raise ValueError("{} is not a temp pivot".format(pivot))
    return parents[0]


def _read(group):
    return json.loads(attribute.get_string_attr(group, DATA_ATTR) or "{}")


def _write(group, data):
    attribute.set_string_attr(group, DATA_ATTR, json.dumps(data))


def find():
    """Return the temp pivot locator of the scene.

    Returns:
        str: The locator long name, or None when there is no temp pivot.
    """
    group = _group()
    if not group:
        return None
    children = cmds.listRelatives(group, children=True, type="transform", fullPath=True)
    return children[0] if children else None


def state(pivot):
    """Return the step a temp pivot is at.

    Args:
        pivot (str): The temp pivot locator.

    Returns:
        str: ``"place"`` or ``"active"``.
    """
    return info(pivot)["state"]


def info(pivot):
    """Return what a temp pivot works on.

    Args:
        pivot (str): The temp pivot locator.

    Returns:
        dict: ``controls``, ``frames``, ``label``, ``state`` and
            ``skipped`` (controls left out because their translate is
            locked; known once activated).
    """
    data = _read(_group_of(pivot))
    controls = data.get("controls", [])
    constrained = data.get("constrained", [])
    return {
        "controls": controls,
        "frames": data.get("frames", []),
        "label": data.get("label", ""),
        "state": ACTIVE if constrained else PLACE,
        "skipped": data.get("skipped", []),
    }


#############################################
# CREATE
#############################################


def default_frames(controls):
    """Return the frames a temp pivot works on.

    The keyed frames of the controls inside the timeline range selection,
    or inside the playback range when there is none, plus the current
    frame.

    Args:
        controls (list): Control names.

    Returns:
        list: Sorted frames.
    """
    start, end = anim_utils.get_timeline_range() or anim_utils.get_playback_range()
    keys = [
        t
        for t in anim_utils.get_keyframe_times(controls)
        if start - 1e-6 <= t <= end + 1e-6
    ]
    return sorted(set(keys + [cmds.currentTime(query=True)]))


def center(controls):
    """Return the average world position of the controls' pivots.

    Args:
        controls (list): Transform names.

    Returns:
        tuple: World position.
    """
    points = [
        cmds.xform(c, query=True, worldSpace=True, rotatePivot=True) for c in controls
    ]
    count = float(len(points))
    return tuple(sum(p[i] for p in points) / count for i in range(3))


def manipulator_position():
    """Return where the move tool handle of the selection is.

    Falls back to the center of the selection's bounding box when the move
    tool can't tell (e.g. in batch mode).

    Returns:
        tuple: World position, or None when nothing is selected.
    """
    selection = cmds.ls(selection=True, long=True)
    if not selection:
        return None
    try:
        position = cmds.manipMoveContext("Move", query=True, position=True)
    except RuntimeError:
        position = None
    if position and len(position) == 3:
        return tuple(position)
    box = cmds.exactWorldBoundingBox(selection)
    return tuple((box[i] + box[i + 3]) / 2.0 for i in range(3))


def create(controls, position=None, frames=None, label=""):
    """Create a temp pivot for controls, ready to be placed.

    Args:
        controls (list): Transform names.
        position (tuple, optional): World position of the pivot. Defaults
            to the center of the controls.
        frames (list, optional): Frames to work on. Defaults to
            :func:`default_frames`.
        label (str, optional): Caller tag, e.g. the hub row it comes from.

    Returns:
        str: The temp pivot locator.

    Raises:
        RuntimeError: When the scene already has a temp pivot.
        ValueError: When there is no control.
    """
    controls = cmds.ls(controls, long=True, type="transform") or []
    if not controls:
        raise ValueError("No control for the temp pivot")
    if find():
        raise RuntimeError("A temp pivot already exists: bake or cancel it first")
    if position is None:
        position = center(controls)
    if frames is None:
        frames = default_frames(controls)
    with utils.undo_chunk("mgearTempPivotCreate"):
        orphan = _group()
        if orphan:
            cmds.delete(orphan)
        group = cmds.createNode("transform", name=GROUP_NAME)
        cmds.addAttr(group, longName=MARKER_ATTR, attributeType="bool", defaultValue=1)
        locator = cmds.spaceLocator(name=LOCATOR_NAME)[0]
        locator = cmds.parent(locator, group)[0]
        locator = cmds.ls(locator, long=True)[0]
        cmds.xform(locator, worldSpace=True, translation=position)
        _write(
            group,
            {
                "controls": controls,
                "frames": list(frames),
                "label": label,
            },
        )
    return locator


#############################################
# ACTIVATE
#############################################


def _locked_axes(control):
    """Return the locked translate and rotate axes, e.g. ``{"translate": ["x"]}``."""
    unlocked = set(attribute.get_unlocked_channels(control, ("translate", "rotate")))
    return {
        attr: [a.lower() for a in AXES if attr + a not in unlocked]
        for attr in ("translate", "rotate")
    }


def _free_values(control):
    """Return the transform channel values without an input connection."""
    values = {}
    for attr in ("translate", "rotate", "scale"):
        for axis in AXES:
            plug = "{}.{}{}".format(control, attr, axis)
            if not attribute.has_input(plug):
                values[plug] = cmds.getAttr(plug)
    return values


def activate(pivot):
    """Make the controls follow the temp pivot.

    Controls with all three translate axes locked can't move around
    another point and are skipped. Nothing moves on the temp pivot frames
    until the locator is moved, rotated or keyed.

    Args:
        pivot (str): The temp pivot locator.

    Returns:
        list: The skipped controls. When every control is skipped, nothing
            is constrained and the temp pivot stays in the place step.
    """
    group = _group_of(pivot)
    # one undo step, the time changes of the recording included
    with utils.undo_chunk("mgearTempPivotActivate"):
        data = _read(group)
        controls = [c for c in data["controls"] if cmds.objExists(c)]
        locks = {c: _locked_axes(c) for c in controls}
        usable = [c for c in controls if len(locks[c]["translate"]) < 3]
        skipped = [c for c in controls if c not in usable]
        data["skipped"] = skipped
        if not usable:
            _write(group, data)
            return skipped

        frames = data["frames"]
        ref = usable[0]
        recorded = anim_utils.record_world_matrices(
            usable, frames=frames, status="Temp pivot"
        )
        pivot_matrix = om2.MMatrix(anim_utils.get_world_matrices([pivot])[0])
        ref_matrix = om2.MMatrix(anim_utils.get_world_matrices([ref])[0])
        # the pivot moves with the first control, keeping its offset
        offset = pivot_matrix * ref_matrix.inverse()

        followers = []
        for control in usable:
            follower = cmds.createNode(
                "transform", name=FOLLOWER_NAME, parent=pivot, skipSelect=True
            )
            followers.append(cmds.ls(follower, long=True)[0])
        poses = {}
        for frame in frames:
            matrices = recorded[frame]
            pivot_world = offset * om2.MMatrix(matrices[0])
            poses[frame] = [list(pivot_world)] + matrices
        anim_utils.key_world_matrices([pivot] + followers, poses, status="Temp pivot")

        data["values"] = {}
        constraints = []
        for control, follower in zip(usable, followers):
            data["values"].update(_free_values(control))
            constraint = cmds.parentConstraint(
                follower,
                control,
                maintainOffset=False,
                skipTranslate=locks[control]["translate"] or "none",
                skipRotate=locks[control]["rotate"] or "none",
            )[0]
            constraints.append(cmds.ls(constraint, long=True)[0])
        data.update(constraints=constraints, constrained=usable)
        _write(group, data)
        return skipped


#############################################
# BAKE / CANCEL
#############################################


def _pair_blend_input(pair_blend_plug):
    """Return what fed a pair blend output before the constraint.

    ``outTranslateX`` is fed by ``inTranslateX1``, the animation before.
    """
    node, out_attr = pair_blend_plug.split(".", 1)
    in_plug = "{}.in{}1".format(node, out_attr[len("out") :])
    inputs = cmds.listConnections(in_plug, source=True, destination=False, plugs=True)
    return inputs[0] if inputs else None


def _restore_pair_blends(control):
    """Give back to the channels the inputs the constraint pair blends hold."""
    # (control plug, pair blend plug) pairs
    links = (
        cmds.listConnections(
            control,
            source=True,
            destination=False,
            type="pairBlend",
            connections=True,
            plugs=True,
        )
        or []
    )
    pair_blends = set()
    for plug, source in zip(links[0::2], links[1::2]):
        original = _pair_blend_input(source)
        cmds.disconnectAttr(source, plug)
        if original:
            cmds.connectAttr(original, plug, force=True)
        pair_blends.add(source.split(".", 1)[0])
    for node in pair_blends:
        if not cmds.listConnections(node, source=False, destination=True):
            cmds.delete(node)


def _cleanup(group, data, restore_values):
    for constraint in data.get("constraints", []):
        if cmds.objExists(constraint):
            cmds.delete(constraint)
    for control in data.get("constrained", []):
        if not cmds.objExists(control):
            continue
        _restore_pair_blends(control)
        attribute.delete_attrs(
            control, cmds.listAttr(control, string="blendParent*") or []
        )
    if restore_values:
        for plug, value in data.get("values", {}).items():
            if cmds.objExists(plug) and not attribute.has_input(plug):
                try:
                    cmds.setAttr(plug, value)
                except RuntimeError:
                    pass
    if cmds.objExists(group):
        cmds.delete(group)


def bake(pivot):
    """Key the controls where the temp pivot puts them, then remove it.

    The controls are keyed on the temp pivot frames plus the frames where
    the locator has keys.

    Args:
        pivot (str): The temp pivot locator.

    Returns:
        list: The baked controls.
    """
    group = _group_of(pivot)
    data = _read(group)
    controls = [c for c in data.get("constrained", []) if cmds.objExists(c)]
    if not controls:
        raise RuntimeError("The temp pivot is not active")
    frames = set(data["frames"])
    frames.update(cmds.keyframe(pivot, query=True, timeChange=True) or [])
    frames = sorted(frames)
    with utils.undo_chunk("mgearTempPivotBake"):
        recorded = anim_utils.record_world_matrices(
            controls, frames=frames, status="Temp pivot"
        )
        _cleanup(group, data, restore_values=False)
        anim_utils.key_world_matrices(controls, recorded, status="Baking")
    return controls


def cancel(pivot=None):
    """Remove the temp pivot, leaving the controls as they were.

    Args:
        pivot (str, optional): The temp pivot locator. Defaults to the one
            in the scene; a temp pivot group without locator is removed too.
    """
    pivot = pivot or find()
    group = _group_of(pivot) if pivot else _group()
    if not group:
        return
    with utils.undo_chunk("mgearTempPivotCancel"):
        _cleanup(group, _read(group), restore_values=True)
