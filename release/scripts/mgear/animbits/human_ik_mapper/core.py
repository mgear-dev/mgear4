"""HumanIK Mapper core: map mGear controls to a HumanIK character.

Qt-free. The mapping always comes from the scene (the HumanIK character
connections and the ``sub_ik`` links), so scripts and the UI never
disagree.

The HumanIK MEL procs are used without the HumanIK window: characters are
created with ``hikCreateCharacter``, locked with ``hikCharacterLock``
(without its UI validation) and driven with ``hikSetCharacterInput``.
"""

import json

import mgear
import mgear.pymaya as pm
from mgear.core import anim_utils
from mgear.core import node_remap
from mgear.core import utils

from maya import cmds
from maya import mel

from . import constants

HIK_PLUGIN = "mayaHIK"
# (MEL script, a procedure it defines): sourced when the procedure is missing
_HIK_SCRIPTS = (
    ("hikGlobalUtils", "hikCreateCharacter"),
    ("hikSkeletonUtils", "hikReadStancePoseTRSOffsets"),
    ("hikDefinitionUtils", "setCharacterObject"),
    ("hikDefinitionOperations", "hikCharacterLock"),
    ("hikInputSourceUtils", "hikSetCharacterInput"),
    ("hikBakeOperation", "hikBakeCharacterPre"),
)
# body parts HumanIK needs to solve a character
SOLVER_PARTS = ("head", "spine", "left_arm", "right_arm", "left_leg", "right_leg")
_SRT = ("translate", "rotate", "scale")


class HumanIKMapperError(RuntimeError):
    """An expected HumanIK Mapper error, shown to the user as a warning."""


class LockedChannelsError(HumanIKMapperError):
    """Controls have transform channels HumanIK or the bake can't drive."""

    def __init__(self, controls):
        """Initialize the error.

        Args:
            controls (list): The controls with locked or connected channels.
        """
        super(LockedChannelsError, self).__init__(
            "Locked or connected transform channels on: {}".format(", ".join(controls))
        )
        self.controls = list(controls)


def ensure_hik():
    """Load the HumanIK plug-in and source the MEL scripts the tool uses.

    Raises:
        RuntimeError: If the plug-in can not be loaded.
    """
    utils.ensure_plugin(HIK_PLUGIN)
    for script, proc in _HIK_SCRIPTS:
        if not mel.eval('exists "{}"'.format(proc)):
            mel.eval("source {}".format(script))


def refresh_hik_ui():
    """Refresh Maya's HumanIK window, if it is open."""
    if cmds.about(batch=True):
        return
    if not mel.eval('exists "hikUpdateCharacterList"'):
        return
    try:
        mel.eval("hikUpdateCharacterList; hikUpdateContextualUI;")
    except RuntimeError:
        pass


# Controls --------------------------------------------------------------


def _channel_plugs(control, channels=_SRT):
    return [
        "{}.{}{}".format(control, channel, axis)
        for channel in channels
        for axis in "XYZ"
    ]


def _settable(plug):
    return cmds.getAttr(plug, settable=True)


def get_locked_controls(controls):
    """Return the controls with a locked or connected transform channel.

    HumanIK and the bake need settable channels.

    Args:
        controls (list): Control names.

    Returns:
        list: The controls with a channel that is not settable.
    """
    return [
        control
        for control in controls
        if not all(_settable(plug) for plug in _channel_plugs(control))
    ]


def unlock_controls(controls):
    """Unlock and make keyable the transform channels of controls.

    Args:
        controls (list): Control names.
    """
    with utils.undo_chunk("hikMapperUnlockControls"):
        for control in controls:
            for plug in _channel_plugs(control):
                cmds.setAttr(plug, lock=False, keyable=True)


def check_controls(controls, unlock_channels=False):
    """Make sure HumanIK can drive the controls.

    Args:
        controls (list): Control names.
        unlock_channels (bool, optional): Unlock the locked channels instead
            of raising.

    Raises:
        LockedChannelsError: If a control has locked or connected channels
            and ``unlock_channels`` is False.
    """
    locked = get_locked_controls(controls)
    if not locked:
        return
    if not unlock_channels:
        raise LockedChannelsError(locked)
    unlock_controls(locked)


def opposite_control(control):
    """Return the mirror control of a control.

    Args:
        control (str): Control name.

    Returns:
        str: The opposite control, or None (missing, or a center control).
    """
    from mgear.rigbits.mirror_controls import MirrorController

    node = pm.PyNode(control)
    opposite = MirrorController.get_opposite_control(node)
    if not opposite or opposite.name() == node.name():
        return None
    return opposite.name()


# Character -------------------------------------------------------------


def list_characters():
    """Return the HumanIK characters in the scene.

    Returns:
        list: ``HIKCharacterNode`` names.
    """
    return cmds.ls(type="HIKCharacterNode") or []


def _is_mapper_character(node):
    return cmds.attributeQuery(constants.CHARACTER_TAG, node=node, exists=True)


def get_character():
    """Return the HumanIK character of the mGear rig.

    Returns:
        str: The character tagged by :func:`initialize_character` (the
        first one when several rigs are referenced), else a character
        named ``MGearIKHuman`` (older scenes), else None.
    """
    characters = list_characters()
    for node in characters:
        if _is_mapper_character(node):
            return node
    return constants.CHAR_NAME if constants.CHAR_NAME in characters else None


def initialize_character(reference=None, unlock_channels=False):
    """Create the mGear HumanIK character, or reuse the existing one.

    Args:
        reference (str, optional): Control mapped as the Reference bone.
        unlock_channels (bool, optional): See :func:`check_controls`.

    Returns:
        str: The character.
    """
    ensure_hik()
    with utils.undo_chunk("hikMapperInitialize"):
        character = get_character()
        if not character:
            character = utils.mel_call("hikCreateCharacter", constants.CHAR_NAME)
        if not _is_mapper_character(character):
            cmds.addAttr(
                character, longName=constants.CHARACTER_TAG, attributeType="bool"
            )
        utils.mel_call("hikSetCurrentCharacter", character)
        if reference:
            map_bones(
                character,
                [(constants.REFERENCE, reference)],
                unlock_channels=unlock_channels,
            )
    refresh_hik_ui()
    return character


def require_character(character=None):
    """Return the given or current character, or raise.

    Args:
        character (str, optional): HumanIK character.

    Returns:
        str: The character.

    Raises:
        HumanIKMapperError: If there is no character.
    """
    character = character or get_character()
    if not character:
        raise HumanIKMapperError(
            "No HumanIK character: select the reference control and Initialize"
        )
    ensure_hik()
    return character


def is_locked(character):
    """Return True if the character definition is locked.

    Args:
        character (str): HumanIK character.

    Returns:
        bool: The lock state.
    """
    return bool(cmds.getAttr(character + ".InputCharacterizationLock"))


def lock(character):
    """Lock the character definition, saving the current pose as stance.

    A locked definition can be a source or be driven by one. Maya's
    validation, which needs the HumanIK window, is skipped.

    Args:
        character (str): HumanIK character.
    """
    if is_locked(character):
        return
    utils.mel_call("hikReadStancePoseTRSOffsets", character)
    utils.mel_call("hikCharacterLock", character, True, False)


def unlock(character):
    """Unlock the character definition so its mapping can be edited.

    The character's source is removed first.

    Args:
        character (str): HumanIK character.
    """
    if not is_locked(character):
        return
    if get_source(character):
        set_source(character, None)
    utils.mel_call("hikCharacterLock", character, False, False)


# Mapping ---------------------------------------------------------------


def _sub_ik_plug(node):
    return "{}.{}".format(node, constants.SUB_IK_ATTR)


def get_bone_target(character, bone):
    """Return the control mapped to a HumanIK bone.

    Args:
        character (str): HumanIK character.
        bone (str): HumanIK bone name.

    Returns:
        str: The control, or None.
    """
    plug = "{}.{}".format(character, bone)
    targets = cmds.listConnections(plug, source=True, destination=False)
    return targets[0] if targets else None


def get_sub_iks(control):
    """Return the Sub IK controls linked to a mapped control.

    Args:
        control (str): Mapped control.

    Returns:
        list: Sub IK controls.
    """
    if not cmds.attributeQuery(constants.SUB_IK_ATTR, node=control, exists=True):
        return []
    plug = _sub_ik_plug(control)
    return cmds.listConnections(plug, source=False, destination=True) or []


def get_mapping(character=None):
    """Return the mapping of a HumanIK character, read from the scene.

    Each mapped control is connected from its ``Character`` attribute to
    the character's bone attribute.

    Args:
        character (str, optional): HumanIK character. Default: the current
            one.

    Returns:
        dict: ``{bone: {"target": control, "sub_ik": [controls]}}`` for the
        mapped bones, in HumanIK node order. Empty without a character.
    """
    character = character or get_character()
    if not character:
        return {}
    connections = (
        cmds.listConnections(
            character, source=True, destination=False, connections=True, plugs=True
        )
        or []
    )
    targets = {}
    for destination, source in zip(connections[::2], connections[1::2]):
        if source.rsplit(".", 1)[-1] == "Character":
            targets[destination.split(".", 1)[1]] = source.rsplit(".", 1)[0]
    ensure_hik()
    bones = sorted(targets, key=cmds.hikGetNodeIdFromName)
    return {
        bone: {"target": targets[bone], "sub_ik": get_sub_iks(targets[bone])}
        for bone in bones
    }


def body_part_status(mapping, bones):
    """Return how complete a body part is mapped.

    Args:
        mapping (dict): Mapping from :func:`get_mapping`.
        bones (tuple): The body part's HumanIK bones.

    Returns:
        str: :data:`constants.STATUS_EMPTY`, ``STATUS_PARTIAL`` or
        ``STATUS_COMPLETE``. A part is complete when the bones HumanIK
        requires are mapped, or when any bone is mapped for parts without
        required bones (fingers, rolls).
    """
    if not any(bone in mapping for bone in bones):
        return constants.STATUS_EMPTY
    required = [bone for bone in bones if constants.is_required(bone)]
    if all(bone in mapping for bone in required):
        return constants.STATUS_COMPLETE
    return constants.STATUS_PARTIAL


def incomplete_parts(mapping):
    """Return the body parts HumanIK needs that are not fully mapped.

    HumanIK does not solve a character whose definition misses them.

    Args:
        mapping (dict): Mapping from :func:`get_mapping`.

    Returns:
        list: Body part keys of :data:`constants.BODY_PART_BONES`.
    """
    return [
        key
        for key in SOLVER_PARTS
        if body_part_status(mapping, constants.BODY_PART_BONES[key])
        != constants.STATUS_COMPLETE
    ]


def pair_selection(bones, controls, mirror=False):
    """Pair HumanIK bones with controls in order, without mapping them.

    Args:
        bones (list): HumanIK bones, in selection order.
        controls (list): Controls, in selection order.
        mirror (bool, optional): Also pair the opposite side bones with
            the opposite controls.

    Returns:
        tuple: ``(pairs, report)``. ``pairs`` is a list of
        ``(bone, control)``. ``report`` is a dict with the lists
        ``unpaired_bones`` (no control selected for them),
        ``unused_controls`` (more controls than bones) and
        ``missing_mirror`` (opposite bones without opposite control).
    """
    count = min(len(bones), len(controls))
    pairs = list(zip(bones[:count], controls[:count]))
    report = {
        "unpaired_bones": list(bones[count:]),
        "unused_controls": list(controls[count:]),
        "missing_mirror": [],
    }
    if mirror:
        for bone, control in list(pairs):
            other_bone = constants.mirror_bone(bone)
            if not other_bone:
                continue
            other_control = opposite_control(control)
            if other_control:
                pairs.append((other_bone, other_control))
            else:
                report["missing_mirror"].append(other_bone)
        report["unpaired_bones"].extend(
            filter(None, map(constants.mirror_bone, bones[count:]))
        )
    return pairs, report


def map_bones(character, pairs, unlock_channels=False):
    """Map controls to HumanIK bones, in one undo chunk.

    The definition is unlocked first if needed. Empty controls are skipped.

    Args:
        character (str): HumanIK character.
        pairs (list): ``(bone, control)`` tuples.
        unlock_channels (bool, optional): See :func:`check_controls`.

    Returns:
        int: The number of mapped bones.

    Raises:
        LockedChannelsError: See :func:`check_controls`.
    """
    ensure_hik()
    pairs = [(bone, control) for bone, control in pairs if control]
    check_controls([control for _, control in pairs], unlock_channels)
    with utils.undo_chunk("hikMapperMap"):
        unlock(character)
        for bone, control in pairs:
            node_id = cmds.hikGetNodeIdFromName(bone)
            utils.mel_call("setCharacterObject", control, character, node_id, 0)
    refresh_hik_ui()
    return len(pairs)


def unmap_bones(character, bones):
    """Remove the controls mapped to HumanIK bones.

    Args:
        character (str): HumanIK character.
        bones (list): HumanIK bone names.
    """
    ensure_hik()
    with utils.undo_chunk("hikMapperUnmap"):
        unlock(character)
        for bone in bones:
            node_id = cmds.hikGetNodeIdFromName(bone)
            utils.mel_call("hikRemoveSkFromCharacter", character, node_id)
    refresh_hik_ui()


def mapped_controls(mapping):
    """Return every mapped and Sub IK control of a mapping.

    Args:
        mapping (dict): Mapping from :func:`get_mapping`.

    Returns:
        list: Unique control names, in mapping order.
    """
    return list(
        dict.fromkeys(
            control
            for entry in mapping.values()
            for control in [entry["target"]] + list(entry["sub_ik"])
        )
    )


# Sub IK ----------------------------------------------------------------


def _ensure_message(node):
    if not cmds.attributeQuery(constants.SUB_IK_ATTR, node=node, exists=True):
        cmds.addAttr(node, longName=constants.SUB_IK_ATTR, attributeType="message")


def set_sub_ik(target, controls, mirror=False, unlock_channels=False):
    """Link controls as Sub IK of a mapped control.

    Sub IK controls follow the mapped control during the bake.

    Args:
        target (str): Mapped control.
        controls (list): Sub IK controls.
        mirror (bool, optional): Also link the opposite controls to the
            opposite target.
        unlock_channels (bool, optional): See :func:`check_controls`.

    Returns:
        list: The controls without opposite control (mirror).

    Raises:
        LockedChannelsError: See :func:`check_controls`.
    """
    links = [(target, list(controls))]
    missing = []
    if mirror:
        other_target = opposite_control(target)
        if other_target:
            others = [opposite_control(control) for control in controls]
            missing = [c for c, o in zip(controls, others) if not o]
            links.append((other_target, [o for o in others if o]))
        else:
            missing = [target]
    check_controls([c for _, linked in links for c in linked], unlock_channels)
    with utils.undo_chunk("hikMapperSetSubIk"):
        for link_target, link_controls in links:
            _ensure_message(link_target)
            source = _sub_ik_plug(link_target)
            for control in link_controls:
                _ensure_message(control)
                destination = _sub_ik_plug(control)
                if not cmds.isConnected(source, destination):
                    cmds.connectAttr(source, destination, force=True)
    return missing


def _mapper_constraints(control):
    constraints = cmds.listRelatives(control, type="parentConstraint") or []
    return [
        constraint
        for constraint in constraints
        if cmds.attributeQuery(
            constants.SUB_IK_CONSTRAINT_TAG, node=constraint, exists=True
        )
    ]


def clear_sub_ik(target):
    """Unlink the Sub IK controls of a mapped control.

    The constraints the mapper created on them are deleted too.

    Args:
        target (str): Mapped control.

    Returns:
        list: The unlinked controls.
    """
    controls = get_sub_iks(target)
    source = _sub_ik_plug(target)
    with utils.undo_chunk("hikMapperClearSubIk"):
        for control in controls:
            cmds.disconnectAttr(source, _sub_ik_plug(control))
            constraints = _mapper_constraints(control)
            if constraints:
                cmds.delete(constraints)
    return controls


def _settable_axes(control, channel):
    return [
        axis.lower()
        for axis in "XYZ"
        if _settable("{}.{}{}".format(control, channel, axis))
    ]


def bind_sub_iks(mapping):
    """Constrain the free channels of each Sub IK control to its control.

    Args:
        mapping (dict): Mapping from :func:`get_mapping`.

    Returns:
        tuple: ``(constraints, plugs)``: the created parent constraints,
        tagged as mapper constraints, and the constrained plugs to bake.
    """
    constraints = []
    plugs = []
    for entry in mapping.values():
        for control in entry["sub_ik"]:
            translate = _settable_axes(control, "translate")
            rotate = _settable_axes(control, "rotate")
            if not translate and not rotate:
                continue
            plugs.extend("{}.translate{}".format(control, a.upper()) for a in translate)
            plugs.extend("{}.rotate{}".format(control, a.upper()) for a in rotate)
            if _mapper_constraints(control):
                continue
            skip = {
                "skipTranslate": [a for a in "xyz" if a not in translate] or "none",
                "skipRotate": [a for a in "xyz" if a not in rotate] or "none",
            }
            constraint = cmds.parentConstraint(
                entry["target"], control, maintainOffset=True, **skip
            )[0]
            cmds.addAttr(
                constraint,
                longName=constants.SUB_IK_CONSTRAINT_TAG,
                attributeType="bool",
            )
            constraints.append(constraint)
    return constraints, plugs


def unbind_sub_iks(mapping):
    """Delete the mapper constraints on the Sub IK controls.

    Args:
        mapping (dict): Mapping from :func:`get_mapping`.
    """
    constraints = [
        constraint
        for entry in mapping.values()
        for control in entry["sub_ik"]
        for constraint in _mapper_constraints(control)
    ]
    if constraints:
        cmds.delete(constraints)


# Source and bake -------------------------------------------------------


def list_sources(character=None):
    """Return the HumanIK characters that can drive a character.

    Args:
        character (str, optional): The driven character.

    Returns:
        list: The other HumanIK characters in the scene.
    """
    character = character or get_character()
    return [node for node in list_characters() if node != character]


def get_source(character):
    """Return the character driving a character.

    Args:
        character (str): HumanIK character.

    Returns:
        str: The source character, or None.
    """
    ensure_hik()
    source = utils.mel_call("hikGetCharacterInputString", character) or ""
    return source if cmds.objExists(source) and source != character else None


def _set_input_proc():
    if mel.eval('exists "hikSetCharacterInput"'):
        return "hikSetCharacterInput"
    return "mayaHIKsetCharacterInput"


def set_source(character, source, mapping=None, refresh_ui=True):
    """Drive a HumanIK character with another one.

    Works without Maya's HumanIK window. Both definitions are locked. A
    warning tells when the character misses bones HumanIK needs.

    Args:
        character (str): The driven character.
        source (str): The source character, or None to remove the source.
        mapping (dict, optional): The character's mapping, when known.
        refresh_ui (bool, optional): Refresh Maya's HumanIK window.
    """
    ensure_hik()
    if source:
        missing = incomplete_parts(mapping or get_mapping(character))
        if missing:
            cmds.warning(
                "HumanIK Mapper: {} is not fully mapped ({}), the source may "
                "not drive it".format(character, ", ".join(missing))
            )
        lock(source)
        lock(character)
    utils.mel_call(_set_input_proc(), character, source or "")
    if refresh_ui:
        refresh_hik_ui()


def _unique_layer(name):
    layer = name
    index = 1
    while cmds.objExists(layer):
        layer = "{}{}".format(name, index)
        index += 1
    return layer


def bake(
    character=None,
    start=None,
    end=None,
    layer=None,
    pre_roll=0,
    mapping=None,
    unlock_channels=False,
):
    """Bake the HumanIK source onto the mapped controls.

    Sub IK controls follow their mapped control and are baked too. The
    HumanIK state and the temporary constraints are always restored.

    Args:
        character (str, optional): HumanIK character. Default: the current
            one.
        start (float, optional): First frame. Default: playback start.
        end (float, optional): Last frame. Default: playback end.
        layer (str, optional): Bake into a new override animation layer
            with this name, instead of the base layer.
        pre_roll (int, optional): Frames evaluated before ``start``, without
            keys, see :func:`mgear.core.anim_utils.bake_attributes`.
        mapping (dict, optional): The character's mapping, when known.
        unlock_channels (bool, optional): See :func:`check_controls`.

    Returns:
        str: The animation layer, or None for the base layer.

    Raises:
        HumanIKMapperError: If nothing is mapped.
        LockedChannelsError: See :func:`check_controls`.
    """
    character = require_character(character)
    mapping = mapping or get_mapping(character)
    if not mapping:
        raise HumanIKMapperError("{} has no mapped controls".format(character))
    check_controls(mapped_controls(mapping), unlock_channels)
    if layer:
        layer = _unique_layer(layer)
    with utils.undo_chunk("hikMapperBake"), utils.keep_selection():
        constraints, sub_ik_plugs = bind_sub_iks(mapping)
        try:
            # selects the plugs HumanIK drives
            utils.mel_call("hikBakeCharacterPre", character)
            anim_utils.bake_attributes(
                (cmds.ls(selection=True) or []) + sub_ik_plugs,
                start=start,
                end=end,
                preroll=pre_roll,
                destination_layer=layer,
            )
        finally:
            utils.mel_call("hikBakeCharacterPost", character)
            existing = cmds.ls(constraints)
            if existing:
                cmds.delete(existing)
    mgear.log("HumanIK Mapper: baked {}".format(character))
    return layer


# Mapping files ---------------------------------------------------------


def export_mapping(path, character=None):
    """Write the mapping to a ``.hikm`` file, without namespaces.

    Args:
        path (str): File path.
        character (str, optional): HumanIK character. Default: the current
            one.

    Returns:
        dict: The written data.
    """
    character = require_character(character)
    data = {
        "version": constants.FILE_VERSION,
        "character": node_remap.short_name(character),
        "mapping": {
            bone: {
                "target": node_remap.short_name(entry["target"]),
                "sub_ik": [node_remap.short_name(c) for c in entry["sub_ik"]],
            }
            for bone, entry in get_mapping(character).items()
        },
    }
    with open(path, "w") as stream:
        json.dump(data, stream, indent=4)
    return data


def load_mapping_file(path):
    """Read a ``.hikm`` file of any version.

    Args:
        path (str): File path.

    Returns:
        dict: ``{bone: {"target": name, "sub_ik": [names]}}``.
    """
    with open(path, "r") as stream:
        data = json.load(stream)
    if "version" not in data:
        # version 1: the bone dict itself
        return data
    return data.get("mapping", {})


def _resolve(name, namespace, report):
    hits = node_remap.find_node_candidates(name, namespace=namespace)
    if len(hits) == 1:
        return cmds.ls(hits[0])[0]
    report["ambiguous" if hits else "missing"].append(name)
    return None


def resolve_mapping(file_mapping, namespace=None):
    """Find the scene controls of a mapping read from a file.

    Args:
        file_mapping (dict): Mapping from :func:`load_mapping_file`.
        namespace (str, optional): Namespace of the controls, e.g.
            ``"chr"``. Default: any namespace, when the name is unique.

    Returns:
        tuple: ``(mapping, report)``. ``mapping`` has the found controls
        only. ``report`` lists the ``missing`` and ``ambiguous`` names.
    """
    report = {"missing": [], "ambiguous": []}
    mapping = {}
    for bone, entry in file_mapping.items():
        target = _resolve(entry["target"], namespace, report)
        if not target:
            continue
        sub_iks = [_resolve(name, namespace, report) for name in entry["sub_ik"]]
        mapping[bone] = {"target": target, "sub_ik": [c for c in sub_iks if c]}
    return mapping, report


def apply_mapping(mapping, character=None, unlock_channels=False):
    """Map the controls and Sub IK links of a resolved mapping.

    The character is created when needed.

    Args:
        mapping (dict): Mapping from :func:`resolve_mapping`.
        character (str, optional): HumanIK character. Default: the current
            one, or a new one.
        unlock_channels (bool, optional): See :func:`check_controls`.

    Returns:
        str: The character.

    Raises:
        LockedChannelsError: See :func:`check_controls`.
    """
    check_controls(mapped_controls(mapping), unlock_channels)
    with utils.undo_chunk("hikMapperApplyMapping"):
        character = character or get_character() or initialize_character()
        map_bones(
            character, [(bone, entry["target"]) for bone, entry in mapping.items()]
        )
        for entry in mapping.values():
            if entry["sub_ik"]:
                set_sub_ik(entry["target"], entry["sub_ik"])
    return character


def import_mapping(path, namespace=None, character=None, unlock_channels=False):
    """Read a ``.hikm`` file and map its controls.

    Missing and ambiguous controls are skipped with a warning.

    Args:
        path (str): File path.
        namespace (str, optional): Namespace of the controls.
        character (str, optional): HumanIK character.
        unlock_channels (bool, optional): See :func:`check_controls`.

    Returns:
        tuple: ``(character, report)``, see :func:`resolve_mapping`.
    """
    mapping, report = resolve_mapping(load_mapping_file(path), namespace)
    warn_report(report)
    character = apply_mapping(mapping, character, unlock_channels)
    return character, report


def warn_report(report):
    """Show a warning for the missing and ambiguous names of a report.

    Args:
        report (dict): Report from :func:`resolve_mapping`.
    """
    for key in ("missing", "ambiguous"):
        if report.get(key):
            cmds.warning(
                "HumanIK Mapper: {} controls skipped: {}".format(
                    key, ", ".join(report[key])
                )
            )
