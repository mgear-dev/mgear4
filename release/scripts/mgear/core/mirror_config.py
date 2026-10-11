"""Mirror config: set up the mirror pose inversion flags of controls.

The mirror pose (anim_utils.mirror_controls) copies the channel values of a
control to its mirror control, and inverts a channel when the source control
has its inv attribute on (invTx ... invSz). This module finds the right
translate and rotate flags from the rest frames of the controls, applies
them, verifies them and saves them in .smc files.

The flags come from the frames the channels act in, not from the control's
own orientation: translate channels act in the parent frame, rotate channels
in the parent frame too (jointOrient frame for joints). For a control and
its mirror control, the relation ``C = F_source · M · F_target⁻¹`` (M = world
X mirror) must be a signed diagonal. Its signs give the flags. A parent with
negative scale is part of the frames, so it is handled.
"""

import math

from maya import cmds
import maya.api.OpenMaya as om2

import mgear
from mgear.core import anim_utils
from mgear.core import attribute
from mgear.core import config_io
from mgear.core import utils
from mgear.core.node_remap import short_name

FILE_EXTENSION = ".smc"
FILE_FILTER = "mGear Mirror Config (*{})".format(FILE_EXTENSION)
FILE_TYPE = "mirror_config"
SCHEMA_VERSION = 1

INV_ATTRS = attribute.MIRROR_CONFIG_CHANNELS
TRANSLATE_ATTRS = INV_ATTRS[:3]
ROTATE_ATTRS = INV_ATTRS[3:6]
SCALE_ATTRS = INV_ATTRS[6:]

STATUS_OK = "ok"
STATUS_CHANGED = "changed"
STATUS_MISSING = "missing"
STATUS_NOT_MIRRORABLE = "not_mirrorable"
STATUS_NO_PAIR = "no_pair"
STATUSES = (
    STATUS_OK,
    STATUS_CHANGED,
    STATUS_MISSING,
    STATUS_NOT_MIRRORABLE,
    STATUS_NO_PAIR,
)

DEFAULT_TOLERANCE = 1.0
# largest verify translation error of a correct mirror, in scene units
TRANSLATION_TOLERANCE = 1e-3

# test pose of verify, added to the default values (UI units)
VERIFY_POSE = {
    "translateX": 1.3,
    "translateY": -0.7,
    "translateZ": 0.9,
    "rotateX": 17.0,
    "rotateY": -23.0,
    "rotateZ": 31.0,
}

# world X mirror, row vector matrices (Maya convention)
_MIRROR = om2.MMatrix(
    ((-1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0, 0, 0, 1))
)


# =============================================================================
# controls
# =============================================================================


def _long_transforms(nodes):
    """Get the full paths of the transforms in nodes, without duplicates."""
    names = [str(n) for n in nodes]
    if not names:
        return []
    return list(dict.fromkeys(cmds.ls(names, long=True, type="transform") or []))


def _inv_attr_nodes(roots):
    """Get the transforms under the roots that have any inv attribute."""
    patterns = ["*.{}".format(attr) for attr in INV_ATTRS]
    nodes = cmds.ls(patterns, objectsOnly=True, recursive=True, long=True) or []
    prefixes = tuple(root + "|" for root in roots)
    return [n for n in _long_transforms(nodes) if n.startswith(prefixes)]


def _rig_set_controls(roots):
    """Get the transforms in the controllers sets of the rigs."""
    controls = []
    for root in roots:
        controls.extend(anim_utils.get_rig_controls(root))
    return _long_transforms(controls)


def get_controls(nodes, mode="rig"):
    """Get the controls to set up.

    Args:
        nodes (list): In "rig" mode, any nodes of the rigs. In "selection"
            mode, the controls.
        mode (str, optional): "rig": the members of the controllers set of
            each rig and the transforms under each rig root with inv
            attributes. "selection": only the transforms in nodes.

    Returns:
        list: Control full paths.
    """
    if mode == "selection":
        return _long_transforms(nodes)
    roots = anim_utils.get_rig_roots(nodes)
    if not roots:
        mgear.log(
            "Mirror Config: no rig found, using the given nodes",
            mgear.sev_warning,
        )
        return _long_transforms(nodes)
    return list(dict.fromkeys(_rig_set_controls(roots) + _inv_attr_nodes(roots)))


def current_flags(node):
    """Get the inv attribute values of a control.

    Args:
        node (str): Control.

    Returns:
        dict: inv attribute name to bool, None for missing attributes.
    """
    fn = utils.get_dependency_node(node)
    return {
        attr: fn.findPlug(attr, False).asBool() if fn.hasAttribute(attr) else None
        for attr in INV_ATTRS
    }


def find_missing(nodes):
    """Get the controllers set members without all the inv attributes.

    Args:
        nodes (list): Any nodes of the rigs.

    Returns:
        list: Control full paths.
    """
    controls = _rig_set_controls(anim_utils.get_rig_roots(nodes))
    return [c for c in controls if None in current_flags(c).values()]


def create_missing(controls):
    """Add the inv attributes that the controls don't have, in one undo.

    Args:
        controls (list): Controls.

    Returns:
        list: Full paths of the controls that got new attributes.
    """
    changed = []
    with utils.undo_chunk("mgearCreateMirrorConfig"):
        for node in _long_transforms(controls):
            if attribute.add_mirror_config_channels(node):
                changed.append(node)
    return changed


def _pose_nodes(controls):
    """Get the controls to reset for a reliable rest pose.

    All the controls of the rigs of the controls, and the controls. The rig
    roots are looked up from one control per namespace and top node.
    """
    samples = {}
    for node in controls:
        leaf = node.split("|")[-1]
        samples.setdefault((anim_utils.getNamespace(leaf), node.split("|")[1]), node)
    roots = anim_utils.get_rig_roots(samples.values())
    return _rig_set_controls(roots) + list(controls)


# =============================================================================
# math
# =============================================================================


def _matrix_plug(node, attr):
    """Get the value of the first element of a matrix array attribute."""
    plug = utils.get_plug(node, attr).elementByLogicalIndex(0)
    return om2.MFnMatrixData(plug.asMObject()).matrix()


def _normalized(matrix):
    """Get the 3x3 part of a matrix with unit rows. Row signs are kept."""
    rows = []
    for r in range(3):
        row = [matrix.getElement(r, c) for c in range(3)]
        length = math.sqrt(sum(v * v for v in row)) or 1.0
        rows.append([v / length for v in row] + [0.0])
    rows.append([0.0, 0.0, 0.0, 1.0])
    return om2.MMatrix(rows)


def channel_frames(node):
    """Get the frames the translate and rotate channels of a node act in.

    Translate channels act in the parent frame. Rotate channels act in the
    parent frame too (rotateAxis is applied before the rotation), or in the
    jointOrient frame for joints.

    Args:
        node (str): Transform or joint.

    Returns:
        tuple: Translate frame and rotate frame (MMatrix, unit rows).
    """
    parent = _matrix_plug(node, "parentMatrix")
    rotate = parent
    if cmds.objectType(node, isAType="joint"):
        orient = cmds.getAttr("{}.jointOrient".format(node))[0]
        euler = om2.MEulerRotation(*[math.radians(v) for v in orient])
        rotate = euler.asMatrix() * parent
    return _normalized(parent), _normalized(rotate)


def _snap(relation):
    """Snap a frame relation to a signed diagonal.

    Args:
        relation (MMatrix): Relation between two frames, unit rows.

    Returns:
        tuple: The three signs (1 or -1) and the angle in degrees between
            the relation and the signed diagonal.
    """
    signs = tuple(-1 if relation.getElement(i, i) < 0 else 1 for i in range(3))
    diagonal = om2.MMatrix(
        (
            (signs[0], 0.0, 0.0, 0.0),
            (0.0, signs[1], 0.0, 0.0),
            (0.0, 0.0, signs[2], 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return signs, _rotation_angle(diagonal * relation)


def _rotation_angle(matrix):
    """Get the rotation angle of a 3x3 matrix in degrees, 180 if improper."""
    if matrix.det3x3() < 0:
        return 180.0
    trace = sum(matrix.getElement(i, i) for i in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def mirror_flags(source_frames, target_frames):
    """Get the inv flags of a control from its frames and its target's.

    Args:
        source_frames (tuple): Translate and rotate frames of the control.
            See channel_frames.
        target_frames (tuple): Same for its mirror control (the control
            itself for center controls).

    Returns:
        tuple: Dict of inv attribute name to bool, and the error angle in
            degrees. Scale flags are always off.
    """
    t_signs, t_error = _snap(source_frames[0] * _MIRROR * target_frames[0].inverse())
    r_signs, r_error = _snap(source_frames[1] * _MIRROR * target_frames[1].inverse())
    det = r_signs[0] * r_signs[1] * r_signs[2]
    flags = {}
    for attr, sign in zip(TRANSLATE_ATTRS, t_signs):
        flags[attr] = sign < 0
    for attr, sign in zip(ROTATE_ATTRS, r_signs):
        flags[attr] = sign * det < 0
    for attr in SCALE_ATTRS:
        flags[attr] = False
    return flags, max(t_error, r_error)


# =============================================================================
# analysis
# =============================================================================


def analyze(nodes, mode="rig", tolerance=DEFAULT_TOLERANCE):
    """Propose the inv flags of controls from their rest frames.

    The frames are read with the rigs at their default pose. The scene's
    pose and undo queue are not changed.

    Args:
        nodes (list): Nodes, see get_controls.
        mode (str, optional): "rig" or "selection", see get_controls.
        tolerance (float, optional): Largest error angle, in degrees, of a
            control that can be mirrored with channel flips.

    Returns:
        dict: ``up_axis`` and ``controls``, a list of dicts with ``node``
            (full path), ``name`` (without namespace), ``target`` (mirror
            control full path, None if not found), ``status``, ``error``
            (degrees, None without target), ``proposed`` (inv attribute to
            bool, None if not mirrorable) and ``current`` (inv attribute to
            bool, None for missing attributes).
    """
    controls = get_controls(nodes, mode)
    targets = {c: anim_utils.get_mirror_target_name(c) for c in controls}
    framed = list(dict.fromkeys(controls + [t for t in targets.values() if t]))
    frames = {}
    with anim_utils.default_pose(_pose_nodes(framed)):
        for node in framed:
            frames[node] = channel_frames(node)

    records = []
    for node in controls:
        target = targets[node]
        current = current_flags(node)
        record = {
            "node": node,
            "name": short_name(node),
            "target": target,
            "status": STATUS_NO_PAIR,
            "error": None,
            "proposed": None,
            "current": current,
        }
        records.append(record)
        if target is None:
            continue
        flags, error = mirror_flags(frames[node], frames[target])
        record["error"] = error
        if error > tolerance:
            record["status"] = STATUS_NOT_MIRRORABLE
            continue
        record["proposed"] = flags
        record["status"] = flag_status(flags, current)

    _check_pairs(records)
    return {"up_axis": cmds.upAxis(query=True, axis=True), "controls": records}


def flag_status(proposed, current):
    """Get the status of a mirrorable control.

    Args:
        proposed (dict): Proposed flags, inv attribute name to bool.
        current (dict): Current flags, see current_flags.

    Returns:
        str: STATUS_MISSING, STATUS_CHANGED or STATUS_OK.
    """
    if None in current.values():
        return STATUS_MISSING
    if any(current[a] != proposed[a] for a in INV_ATTRS):
        return STATUS_CHANGED
    return STATUS_OK


def _check_pairs(records):
    """Mark pairs with different proposals as not mirrorable.

    Both controls of a pair always get the same flags, as their frame
    relations are inverse signed diagonals. This guards against bugs.
    """
    by_node = {r["node"]: r for r in records}
    for record in records:
        other = by_node.get(record["target"])
        if not other or other is record:
            continue
        if record["proposed"] is None or other["proposed"] is None:
            continue
        if record["proposed"] != other["proposed"]:
            mgear.log(
                "Mirror Config: {} and {} got different flags".format(
                    record["name"], other["name"]
                ),
                mgear.sev_warning,
            )
            for r in (record, other):
                r["proposed"] = None
                r["status"] = STATUS_NOT_MIRRORABLE


# =============================================================================
# config
# =============================================================================


def build_config(flags):
    """Build a mirror config.

    Args:
        flags (dict): Control name or full path to a dict of inv attribute
            name to bool. The config keeps the names without namespace.

    Returns:
        dict: The config: ``type``, ``schema_version`` and ``controls``,
            control name to its nine inv values (0 or 1).
    """
    controls = {}
    for node, node_flags in flags.items():
        controls[short_name(node)] = {
            attr: int(bool(node_flags.get(attr))) for attr in INV_ATTRS
        }
    return {"type": FILE_TYPE, "schema_version": SCHEMA_VERSION, "controls": controls}


def config_from_analysis(analysis):
    """Build a mirror config with the proposed flags of an analysis.

    Args:
        analysis (dict): Result of analyze.

    Returns:
        dict: The config. Controls without proposal are left out.
    """
    return build_config(
        {
            r["node"]: r["proposed"]
            for r in analysis["controls"]
            if r["proposed"] is not None
        }
    )


def get_config(nodes, mode="rig"):
    """Build a mirror config with the current flags of controls.

    Args:
        nodes (list): Nodes, see get_controls.
        mode (str, optional): "rig" or "selection", see get_controls.

    Returns:
        dict: The config. Controls without inv attributes are left out,
            missing attributes are stored off.
    """
    flags = {}
    for node in get_controls(nodes, mode):
        current = current_flags(node)
        if any(v is not None for v in current.values()):
            flags[node] = current
    return build_config(flags)


def _set_flags(node, flags):
    """Set the inv flags of a node. Returns False if one couldn't be set."""
    complete = True
    for attr in INV_ATTRS:
        if attr not in flags:
            continue
        plug = "{}.{}".format(node, attr)
        if not cmds.objExists(plug) or not cmds.getAttr(plug, settable=True):
            complete = False
            continue
        value = bool(flags[attr])
        if cmds.getAttr(plug) != value:
            cmds.setAttr(plug, value)
    return complete


def _apply_flags(flags, create_missing):
    """Set the inv flags of nodes, in one undo. See apply_flags."""
    result = {"applied": [], "skipped": []}
    with utils.undo_chunk("mgearApplyMirrorConfig"):
        for node, node_flags in flags.items():
            if create_missing:
                attribute.add_mirror_config_channels(node)
            key = "applied" if _set_flags(node, node_flags) else "skipped"
            result[key].append(node)
    return result


def apply_flags(flags, create_missing=True):
    """Set the inv flags of controls, in one undo.

    Args:
        flags (dict): Control full path to a dict of inv attribute name to
            bool.
        create_missing (bool, optional): Add the missing inv attributes.

    Returns:
        dict: ``applied`` and ``skipped`` control lists. A control is
            skipped when one of its inv attributes is missing, locked or
            connected. The others are still set.
    """
    result = _apply_flags(flags, create_missing)
    _log_apply(result)
    return result


def apply_config(config, namespace=None, create_missing=True, nodes=None):
    """Set the inv flags of the controls of a config, in one undo.

    Args:
        config (dict): The config, see build_config and load_config.
        namespace (str, optional): Namespace of the controls.
        create_missing (bool, optional): Add the missing inv attributes.
        nodes (list, optional): Any nodes of the rigs to apply to. The
            config names are looked up among their controls (see
            get_controls), whatever their namespace. Overrides namespace.

    Returns:
        dict: ``applied``, ``not_found`` and ``skipped`` control lists.
            See apply_flags.
    """
    by_name = None
    if nodes:
        by_name = {short_name(c): c for c in get_controls(nodes)}
    flags = {}
    not_found = []
    for name, name_flags in config["controls"].items():
        if by_name is not None:
            found = [by_name[name]] if name in by_name else []
        else:
            full_name = "{}:{}".format(namespace, name) if namespace else name
            found = cmds.ls(full_name, long=True, type="transform")
        if not found:
            not_found.append(name)
        for node in found:
            flags[node] = name_flags
    result = _apply_flags(flags, create_missing)
    result["not_found"] = not_found
    _log_apply(result)
    return result


def format_apply_result(result):
    """Get a short text of the result of apply_flags or apply_config.

    Args:
        result (dict): The result.

    Returns:
        str: i.e. "applied 12, not found 1, skipped 0".
    """
    parts = ["applied {}".format(len(result["applied"]))]
    if "not_found" in result:
        parts.append("not found {}".format(len(result["not_found"])))
    parts.append("skipped {}".format(len(result["skipped"])))
    return ", ".join(parts)


def _log_apply(result):
    """Log the result of apply_flags or apply_config."""
    mgear.log("Mirror Config: {}".format(format_apply_result(result)))
    if result.get("not_found"):
        mgear.log(
            "Mirror Config: controls not found: {}".format(
                ", ".join(result["not_found"])
            ),
            mgear.sev_warning,
        )
    if result["skipped"]:
        mgear.log(
            "Mirror Config: missing, locked or connected inv attributes "
            "on: {}".format(", ".join(short_name(n) for n in result["skipped"])),
            mgear.sev_warning,
        )


def export_config(path, config):
    """Write a mirror config file.

    The file is JSON with ``type`` ("mirror_config"), ``schema_version``,
    ``maya_version``, ``scene``, ``up_axis`` and ``controls``: control name
    without namespace to its nine inv attribute values (0 or 1).

    Args:
        path (str): File path. ".smc" is added when it has no extension.
        config (dict): The config, see build_config.

    Returns:
        str: The written file path.
    """
    path = config_io.file_path(path, FILE_EXTENSION)
    config_io.write_file(
        path,
        FILE_TYPE,
        SCHEMA_VERSION,
        "controls",
        config["controls"],
        extra={"up_axis": cmds.upAxis(query=True, axis=True)},
    )
    mgear.log(
        "Mirror Config: exported {} controls to {}".format(
            len(config["controls"]), path
        )
    )
    return path


def load_config(path):
    """Read a mirror config file.

    Args:
        path (str): File path.

    Returns:
        dict: The config.

    Raises:
        ValueError: The file is not a mirror config.
    """
    return config_io.load_file(path, FILE_TYPE, "mirror config")


def import_config(path, namespace=None, create_missing=True, nodes=None):
    """Read a mirror config file and apply it.

    Args:
        path (str): File path.
        namespace (str, optional): Namespace of the controls.
        create_missing (bool, optional): Add the missing inv attributes.
        nodes (list, optional): Any nodes of the rigs to apply to. See
            apply_config.

    Returns:
        dict: See apply_config.
    """
    return apply_config(load_config(path), namespace, create_missing, nodes)


# =============================================================================
# verify
# =============================================================================


def _set_test_pose(node):
    """Add the verify test pose to the settable TR channels of a node.

    Returns:
        list: (plug, previous value) of the channels set.
    """
    posed = []
    for attr in attribute.get_unlocked_channels(
        node, ("translate", "rotate"), settable=True
    ):
        plug = "{}.{}".format(node, attr)
        value = cmds.getAttr(plug)
        cmds.setAttr(plug, value + VERIFY_POSE[attr])
        posed.append((plug, value))
    return posed


def _mirror_source(source):
    """Mirror a control like mirror_controls, without undo.

    Returns:
        list: (plug, previous value) of the channels set.
    """
    changed = []
    for target, attr, value in anim_utils._mirror_entries([source]):
        plug = "{}.{}".format(target, attr)
        try:
            previous = cmds.getAttr(plug)
            cmds.setAttr(plug, value)
        except RuntimeError:
            continue
        changed.append((plug, previous))
    return changed


def _pose_error(expected, actual):
    """Get the rotation (degrees) and translation errors of two matrices."""
    rotation = _rotation_angle(_normalized(actual) * _normalized(expected).inverse())
    translation = math.sqrt(
        sum(
            (actual.getElement(3, i) - expected.getElement(3, i)) ** 2 for i in range(3)
        )
    )
    return rotation, translation


def verify(nodes, mode="rig"):
    """Measure how well the current flags mirror a test pose.

    Each source control (L side and center controls with a mirror control)
    gets a test pose and is mirrored like anim_utils.mirror_controls. The
    world change of its target is compared with the mirror of the source's
    world change. The rigs are at their default pose during the test, and
    the scene is unchanged afterwards.

    Args:
        nodes (list): Nodes, see get_controls.
        mode (str, optional): "rig" or "selection", see get_controls.

    Returns:
        dict: Source control full path to a dict with ``target``,
            ``rotation_error`` (degrees) and ``translation_error`` (scene
            units).
    """
    controls = get_controls(nodes, mode)
    pairs = []
    for node in controls:
        if anim_utils.get_control_side(node) not in ("L", None):
            continue
        target = anim_utils.get_mirror_target_name(node)
        if target:
            pairs.append((node, target))

    posed_nodes = list(dict.fromkeys(controls + [t for _, t in pairs]))
    results = {}
    with anim_utils.default_pose(_pose_nodes(posed_nodes)):
        for source, target in pairs:
            rest_source = _matrix_plug(source, "worldMatrix")
            rest_target = _matrix_plug(target, "worldMatrix")
            changed = _set_test_pose(source)
            if not changed:
                continue
            try:
                delta = rest_source.inverse() * _matrix_plug(source, "worldMatrix")
                changed += _mirror_source(source)
                expected = rest_target * _MIRROR * delta * _MIRROR
                rotation, translation = _pose_error(
                    expected, _matrix_plug(target, "worldMatrix")
                )
                results[source] = {
                    "target": target,
                    "rotation_error": rotation,
                    "translation_error": translation,
                }
            finally:
                for plug, value in reversed(changed):
                    cmds.setAttr(plug, value)
    return results
