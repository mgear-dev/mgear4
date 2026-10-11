"""Gimmick joints: blend and support helper joints for deformation.

A blend joint follows a source joint with a part of its rotation, driven by a
``pairBlend`` node. Support joints are children of a blend joint, usually
driven later by SDK or RBF. This module creates, finds, mirrors, flips,
deletes, exports and imports them. No Qt.

Naming is the one of the mGear Rigbits commands: ``blend_<source>`` and
``blendSupport_<index>_<source>``. Joints made by older mGear versions have
no ``gimmickType`` tag and are recognised by their name and connections.

Example:
    >>> from mgear.rigbits.gimmick_tool import core
    >>> blend = core.create_blend_joint("arm_L0_1_jnt", blend=0.5)
    >>> core.create_support_joint(blend)
    >>> core.mirror_gimmick_joints(direction=core.LEFT_TO_RIGHT)
    >>> core.export_file("C:/rig/data/hero.gst")
"""

import json
import math
import re
import string as py_string

from maya import cmds
import maya.api.OpenMaya as om2

from mgear.core import config_io
from mgear.core import dag
from mgear.core import node_remap
from mgear.core import string

from . import FILE_EXT

BLEND = "Blend"
SUPPORT = "Support"
KINDS = (BLEND, SUPPORT)

LEFT = "Left"
RIGHT = "Right"
CENTER = "Center"
SIDES = (LEFT, RIGHT, CENTER)

LEFT_TO_RIGHT = "L>R"
RIGHT_TO_LEFT = "R>L"

TYPE_ATTR = "gimmickType"
BLEND_PREFIX = "blend_"
SUPPORT_PREFIX = "blendSupport_"
DEFORMERS_SET = "rig_deformers_grp"
RIG_SETS = "rig_sets_grp"
JOINT_RADIUS = 1.5
JOINT_COLOR = 17

FILE_FILTER = "mGear Gimmick Joints (*{})".format(FILE_EXT)
FILE_TYPE = "gimmick_joints"
SCHEMA_VERSION = 1
ITEMS_KEY = "joints"

_SUPPORT_INDEX = re.compile(r"^{}(\d+)_".format(SUPPORT_PREFIX))
_GENERIC_SIDE = re.compile(r"(?:^|_)([LRlr])\d*(?=_|$|\.)")
AXES = "XYZ"

# rig root UUID to its naming rules (with the compiled name pattern)
_RULES_CACHE = {}


# Nodes -----------------------------------------------------------------------


def _long_name(node):
    """Return the full path of an existing node.

    Args:
        node (str): Node name or path.

    Returns:
        str: Full DAG path, None if the node doesn't exist or isn't unique.
    """
    found = cmds.ls(node, long=True)
    if len(found) != 1:
        return None
    return found[0]


def _is_joint(node):
    """Return True if the node exists and is a joint.

    Args:
        node (str): Node name.

    Returns:
        bool: True for an existing joint.
    """
    return bool(node) and bool(cmds.ls(node, type="joint"))


def _display_name(node):
    """Return the shortest unique name of a node.

    Args:
        node (str): Node name or path.

    Returns:
        str: Shortest unique name.
    """
    return (cmds.ls(node) or [node])[0]


def _parent(node):
    """Return the parent of a DAG node.

    Args:
        node (str): Node name.

    Returns:
        str: Full path of the parent, None for a world child.
    """
    parents = cmds.listRelatives(node, parent=True, fullPath=True)
    return parents[0] if parents else None


def _new_joint(name, parent):
    """Create a joint with an identity local transform under a parent.

    ``cmds.parent`` is used so Maya connects the parent scale to the joint
    inverse scale, as it does for joints made with the joint tool.

    Args:
        name (str): Joint name.
        parent (str): Parent node, None for world.

    Returns:
        str: Full path of the new joint.
    """
    jnt = cmds.createNode("joint", name=name, skipSelect=True)
    uuid = cmds.ls(jnt, uuid=True)[0]
    if parent:
        cmds.parent(cmds.ls(uuid, long=True)[0], parent, relative=True)
    jnt = cmds.ls(uuid, long=True)[0]
    if node_remap.leaf_name(jnt) != name:
        cmds.rename(jnt, name)
    return cmds.ls(uuid, long=True)[0]


def _set_display(jnt, radius=JOINT_RADIUS, color=JOINT_COLOR):
    """Set the radius and override color of a gimmick joint.

    Args:
        jnt (str): Joint name.
        radius (float, optional): Joint radius.
        color (int, optional): Override color index.
    """
    cmds.setAttr(jnt + ".radius", radius)
    cmds.setAttr(jnt + ".overrideEnabled", True)
    cmds.setAttr(jnt + ".overrideColor", color)


def _copy_display(source, target):
    """Copy the radius and override color of a joint to another.

    Args:
        source (str): Joint to copy from.
        target (str): Joint to copy to.
    """
    _set_display(
        target,
        radius=cmds.getAttr(source + ".radius"),
        color=cmds.getAttr(source + ".overrideColor"),
    )


def _tag(jnt, kind):
    """Add the gimmick type tag to a joint.

    Args:
        jnt (str): Joint name.
        kind (str): ``BLEND`` or ``SUPPORT``.
    """
    if not cmds.attributeQuery(TYPE_ATTR, node=jnt, exists=True):
        cmds.addAttr(
            jnt,
            longName=TYPE_ATTR,
            attributeType="enum",
            enumName=":".join(KINDS),
            keyable=False,
        )
    cmds.setAttr("{}.{}".format(jnt, TYPE_ATTR), KINDS.index(kind))


def _get_tag(jnt):
    """Return the gimmick type tag of a joint.

    Args:
        jnt (str): Joint name.

    Returns:
        str: ``BLEND``, ``SUPPORT`` or None if the joint has no tag.
    """
    if not cmds.attributeQuery(TYPE_ATTR, node=jnt, exists=True):
        return None
    index = cmds.getAttr("{}.{}".format(jnt, TYPE_ATTR))
    if 0 <= index < len(KINDS):
        return KINDS[index]
    return None


def add_to_deformers_set(nodes):
    """Add nodes to the rig deformers set, creating it when missing.

    A new set goes into the rig sets group when that group exists.

    Args:
        nodes (list of str): Nodes to add.
    """
    if not nodes:
        return
    if not cmds.ls(DEFORMERS_SET, type="objectSet"):
        cmds.sets(name=DEFORMERS_SET, empty=True)
        if cmds.ls(RIG_SETS, type="objectSet"):
            cmds.sets(DEFORMERS_SET, add=RIG_SETS)
    cmds.sets(nodes, add=DEFORMERS_SET)


# Naming rules ----------------------------------------------------------------


def get_naming_rules(node):
    """Return the joint naming rules of the rig a node belongs to.

    The rules are cached per rig top node, so the guide data of a rig is
    parsed once.

    Args:
        node (str): Node name.

    Returns:
        dict: ``rule``, ``left``, ``right``, ``center``, ``ext`` and
            ``pattern`` (compiled name regex, or None) keys, or None when the
            node is not in a Shifter rig with guide data.
    """
    from mgear.shifter import naming

    root = dag.find_rig_root_path(node)
    if not root or not cmds.attributeQuery("guide_data", node=root, exists=True):
        return None
    key = cmds.ls(root, uuid=True)[0]
    if key in _RULES_CACHE:
        return _RULES_CACHE[key]
    try:
        data = json.loads(cmds.getAttr(root + ".guide_data"))
        params = data["guide_root"]["param_values"]
    except (ValueError, KeyError, TypeError):
        params = None
    rules = None
    if params is not None:
        rules = {
            "rule": params.get("joint_name_rule", naming.DEFAULT_NAMING_RULE),
            "left": params.get(
                "side_joint_left_name", naming.DEFAULT_JOINT_SIDE_L_NAME
            ),
            "right": params.get(
                "side_joint_right_name", naming.DEFAULT_JOINT_SIDE_R_NAME
            ),
            "center": params.get(
                "side_joint_center_name", naming.DEFAULT_JOINT_SIDE_C_NAME
            ),
            "ext": params.get("joint_name_ext", naming.DEFAULT_JOINT_EXT_NAME),
        }
        rules["pattern"] = _rule_pattern(rules)
    _RULES_CACHE[key] = rules
    return rules


def _rule_pattern(rules):
    """Return the regex matching joint names of a naming rule.

    Args:
        rules (dict): Naming rules from :func:`get_naming_rules`.

    Returns:
        re.Pattern: Pattern with a ``side`` group, or None if the rule has
            no side token.
    """
    fields = {
        "component": "(?:.*?)",
        "side": "(?P<side>{})".format(
            "|".join(
                re.escape(rules[s]) for s in ("left", "right", "center") if rules[s]
            )
        ),
        "index": r"(?:\d*)",
        "description": "(?:.*?)",
        "extension": re.escape(rules["ext"]),
    }
    pattern = ""
    has_side = False
    try:
        parsed = list(py_string.Formatter().parse(rules["rule"]))
    except ValueError:
        return None
    for literal, field, _spec, _conv in parsed:
        pattern += re.escape(literal)
        if field is None:
            continue
        if field not in fields:
            return None
        has_side = has_side or field == "side"
        pattern += fields[field]
    if not has_side:
        return None
    return re.compile("^{}$".format(pattern))


def _rule_match(name, rules):
    """Match a joint name against naming rules.

    Args:
        name (str): Joint short name.
        rules (dict): Naming rules, or None.

    Returns:
        re.Match: The match with a ``side`` group, or None.
    """
    if not rules or not rules["pattern"]:
        return None
    return rules["pattern"].match(name)


def get_side(joint):
    """Return the side of a joint from its name.

    The naming rules of the joint's rig are used first, then the generic
    side tokens (``L0_``, ``_L_``, ``_L`` ...).

    Args:
        joint (str): Joint name.

    Returns:
        str: ``LEFT``, ``RIGHT`` or ``CENTER``.
    """
    name = node_remap.short_name(joint)
    rules = get_naming_rules(joint) if cmds.objExists(joint) else None
    match = _rule_match(name, rules)
    if match:
        token = match.group("side")
        if token == rules["left"]:
            return LEFT
        if token == rules["right"]:
            return RIGHT
        return CENTER
    found = _GENERIC_SIDE.search(name)
    if not found:
        return CENTER
    return LEFT if found.group(1).upper() == "L" else RIGHT


def get_mirror_name(name, joint=None):
    """Return a name with its side swapped.

    Args:
        name (str): Name to swap, i.e. ``arm_L0_1_jnt``.
        joint (str, optional): Joint whose rig naming rules apply. Defaults
            to ``name`` when it is an existing node.

    Returns:
        str: The swapped name, the same name for center names.
    """
    namespace, _, short = node_remap.leaf_name(name).rpartition(":")
    joint = joint or (name if cmds.objExists(name) else None)
    rules = get_naming_rules(joint) if joint else None
    match = _rule_match(short, rules)
    if match:
        token = match.group("side")
        swap = {rules["left"]: rules["right"], rules["right"]: rules["left"]}
        if token in swap:
            short = (
                short[: match.start("side")] + swap[token] + short[match.end("side") :]
            )
    else:
        short = string.convertRLName(short)
    return "{}:{}".format(namespace, short) if namespace else short


# Recognition -----------------------------------------------------------------


def _pair_blend(jnt):
    """Return the pairBlend node driving the rotation of a joint.

    Args:
        jnt (str): Joint name.

    Returns:
        str: pairBlend node, or None.
    """
    nodes = cmds.listConnections(
        jnt + ".rotateX", source=True, destination=False, type="pairBlend"
    )
    return nodes[0] if nodes else None


def get_source_joint(blend_joint):
    """Return the source joint of a blend joint.

    The source is read from the pairBlend connection, so renaming can't make
    it stale.

    Args:
        blend_joint (str): Blend joint name.

    Returns:
        str: Shortest unique name of the source joint, or None.
    """
    pair_blend = _pair_blend(blend_joint)
    if not pair_blend:
        return None
    sources = cmds.listConnections(
        pair_blend + ".inRotate1", source=True, destination=False, type="joint"
    )
    return _display_name(sources[0]) if sources else None


def get_blend_value(blend_joint):
    """Return the blend weight of a blend joint.

    Args:
        blend_joint (str): Blend joint name.

    Returns:
        float: pairBlend weight, None if the joint has no pairBlend.
    """
    pair_blend = _pair_blend(blend_joint)
    return cmds.getAttr(pair_blend + ".weight") if pair_blend else None


def get_kind(node):
    """Return the gimmick kind of a node.

    Tagged joints use their tag. Untagged joints made by older mGear
    versions are a blend joint when named ``blend_*`` with their rotation
    coming from a pairBlend fed by a joint, and a support joint when named
    ``blendSupport_*`` under a blend joint.

    Args:
        node (str): Node name.

    Returns:
        str: ``BLEND``, ``SUPPORT`` or None.
    """
    if not _is_joint(node):
        return None
    tag = _get_tag(node)
    if tag:
        return tag
    name = node_remap.short_name(node)
    if name.startswith(SUPPORT_PREFIX):
        parent = _parent(node)
        return SUPPORT if parent and get_kind(parent) == BLEND else None
    if name.startswith(BLEND_PREFIX) and get_source_joint(node):
        return BLEND
    return None


def is_blend_joint(node):
    """Return True if a node is a gimmick blend joint.

    Args:
        node (str): Node name.

    Returns:
        bool: True for a blend joint, tagged or made by older mGear versions.
    """
    return get_kind(node) == BLEND


def is_support_joint(node):
    """Return True if a node is a gimmick support joint.

    Args:
        node (str): Node name.

    Returns:
        bool: True for a support joint, tagged or made by older mGear
            versions.
    """
    return get_kind(node) == SUPPORT


def get_support_joints(blend_joint):
    """Return the support joints of a blend joint.

    Args:
        blend_joint (str): Blend joint name.

    Returns:
        list of str: Support joints, children of the blend joint.
    """
    children = (
        cmds.listRelatives(blend_joint, children=True, type="joint", fullPath=True)
        or []
    )
    return [_display_name(c) for c in children if is_support_joint(c)]


def get_gimmick_side(node):
    """Return the side of a gimmick joint, from its source joint.

    Args:
        node (str): Blend or support joint.

    Returns:
        str: ``LEFT``, ``RIGHT`` or ``CENTER``.
    """
    blend = node if is_blend_joint(node) else _parent(node)
    source = get_source_joint(blend) if blend else None
    return get_side(source or node)


def _candidates():
    """Return the joints that can be gimmick joints.

    Tagged joints, and joints named like the gimmick joints of older mGear
    versions, in any namespace. Much faster than testing every joint.

    Returns:
        list of str: Full paths, sorted.
    """
    tagged = (
        cmds.ls("*." + TYPE_ATTR, objectsOnly=True, recursive=True, long=True) or []
    )
    named = (
        cmds.ls(
            BLEND_PREFIX + "*",
            SUPPORT_PREFIX + "*",
            type="joint",
            recursive=True,
            long=True,
        )
        or []
    )
    return sorted(set(cmds.ls(tagged, type="joint", long=True)) | set(named))


def list_gimmick_joints(kind=None, side=None):
    """Return the gimmick joints of the scene.

    Args:
        kind (str, optional): ``BLEND`` or ``SUPPORT``. Default is both.
        side (str or list of str, optional): ``LEFT``, ``RIGHT`` and/or
            ``CENTER``. Default is all sides.

    Returns:
        list of str: Gimmick joints, shortest unique names.
    """
    if isinstance(side, str):
        side = [side]
    result = []
    for jnt in _candidates():
        jnt_kind = get_kind(jnt)
        if not jnt_kind or (kind and jnt_kind != kind):
            continue
        if side and get_gimmick_side(jnt) not in side:
            continue
        result.append(_display_name(jnt))
    return result


def find_blend_joint(source):
    """Return the blend joint of a source joint.

    Args:
        source (str): Source joint name.

    Returns:
        str: The blend joint driven by ``source``, or None.
    """
    source = _long_name(source)
    if not source:
        return None
    pair_blends = set(
        cmds.listConnections(
            source + ".rotate", source=False, destination=True, type="pairBlend"
        )
        or []
    )
    for pair_blend in pair_blends:
        for jnt in (
            cmds.listConnections(
                pair_blend + ".outRotateX",
                source=False,
                destination=True,
                type="joint",
            )
            or []
        ):
            if is_blend_joint(jnt) and _long_name(get_source_joint(jnt)) == source:
                return _display_name(jnt)
    return None


# Creation --------------------------------------------------------------------


def _support_index(name):
    """Return the index of a support joint name.

    Args:
        name (str): Support joint name, i.e. ``blendSupport_2_arm_L0_1_jnt``.

    Returns:
        int: The index, None if the name has none.
    """
    match = _SUPPORT_INDEX.match(node_remap.short_name(name))
    return int(match.group(1)) if match else None


def _custom_name(blend_joint):
    """Return the custom name of a blend joint made with ``name``.

    Args:
        blend_joint (str): Blend joint name.

    Returns:
        str: The name after ``blend_``, None when it is the source name.
    """
    suffix = _support_base_name(blend_joint)
    source = get_source_joint(blend_joint)
    if source and suffix == node_remap.short_name(source):
        return None
    return suffix


def _support_base_name(blend_joint):
    """Return the name part after the index of a blend joint's supports.

    Args:
        blend_joint (str): Blend joint name.

    Returns:
        str: ``arm_L0_1_jnt`` for ``blend_arm_L0_1_jnt``.
    """
    short = node_remap.short_name(blend_joint)
    if short.startswith(BLEND_PREFIX):
        return short[len(BLEND_PREFIX) :]
    source = get_source_joint(blend_joint)
    return node_remap.short_name(source) if source else short


def _build_blend_joint(source, blend, comp_scale, name):
    """Build a blend joint, without checking the source.

    Args:
        source (str): Source joint.
        blend (float): Rotation blend, 0 to 1.
        comp_scale (bool): Segment scale compensate of the joint.
        name (str): Name after the ``blend_`` prefix, None for the source
            name.

    Returns:
        str: The blend joint.
    """
    source = _long_name(source)
    jnt_name = BLEND_PREFIX + (name or node_remap.short_name(source))
    jnt = _new_joint(jnt_name, _parent(source))
    for attr in ("jointOrient", "rotateAxis"):
        cmds.setAttr(
            "{}.{}".format(jnt, attr), *cmds.getAttr("{}.{}".format(source, attr))[0]
        )
    cmds.setAttr(jnt + ".rotateOrder", cmds.getAttr(source + ".rotateOrder"))
    cmds.setAttr(jnt + ".segmentScaleCompensate", comp_scale)

    pair_blend = cmds.createNode(
        "pairBlend", name=node_remap.leaf_name(jnt) + "_pairBlend", skipSelect=True
    )
    cmds.setAttr(pair_blend + ".rotInterpolation", 1)
    cmds.setAttr(pair_blend + ".weight", blend)
    cmds.connectAttr(source + ".translate", pair_blend + ".inTranslate1")
    cmds.connectAttr(source + ".translate", pair_blend + ".inTranslate2")
    cmds.connectAttr(source + ".rotate", pair_blend + ".inRotate1")
    for axis in AXES:
        cmds.connectAttr(
            "{}.outRotate{}".format(pair_blend, axis), "{}.rotate{}".format(jnt, axis)
        )
        cmds.connectAttr(
            "{}.outTranslate{}".format(pair_blend, axis),
            "{}.translate{}".format(jnt, axis),
        )
    cmds.connectAttr(source + ".scale", jnt + ".scale")

    _set_display(jnt)
    _tag(jnt, BLEND)
    add_to_deformers_set([jnt])
    return _display_name(jnt)


def create_blend_joint(source, blend=0.5, comp_scale=True, name=None):
    """Create a blend joint for a source joint.

    The blend joint is named ``blend_<source>`` (or ``blend_<name>``), sits
    under the source's parent with the source's world matrix at rest, and
    gets ``blend`` of the source rotation and all of its translation through
    a pairBlend. The source scale is connected directly.

    Args:
        source (str): Source joint.
        blend (float, optional): Rotation blend, 0 to 1.
        comp_scale (bool, optional): Segment scale compensate of the joint.
        name (str, optional): Name after the ``blend_`` prefix. Default is
            the source name.

    Returns:
        str: The blend joint (the existing one when ``source`` already has
            one), or None if ``source`` is not a joint.
    """
    if not _is_joint(source):
        cmds.warning(
            "Blended Joint can't be added to: {}. It is not a joint".format(source)
        )
        return None
    existing = find_blend_joint(source)
    if existing:
        cmds.warning("{} already has the blend joint {}".format(source, existing))
        return existing
    return _build_blend_joint(source, blend, comp_scale, name)


def create_support_joint(blend_joint, index=None):
    """Create a support joint under a blend joint.

    The support joint is named ``blendSupport_<index>_<source>``, where
    ``index`` is the lowest index not used by the blend joint's supports, and
    has an identity local transform.

    Args:
        blend_joint (str): Blend joint.
        index (int, optional): Index to use when it is free.

    Returns:
        str: The support joint, or None if ``blend_joint`` is not a blend
            joint.
    """
    if not is_blend_joint(blend_joint):
        cmds.warning(
            "Support Joint can't be added to: {}. It is not a blend "
            "joint".format(blend_joint)
        )
        return None
    used = {_support_index(j) for j in get_support_joints(blend_joint)}
    if index is None or index in used:
        index = 0
        while index in used:
            index += 1
    name = "{}{}_{}".format(SUPPORT_PREFIX, index, _support_base_name(blend_joint))
    jnt = _new_joint(name, _long_name(blend_joint))
    _set_display(jnt)
    _tag(jnt, SUPPORT)
    add_to_deformers_set([jnt])
    return _display_name(jnt)


# Transforms ------------------------------------------------------------------


def _world_matrix(node):
    """Return the world matrix of a node.

    Args:
        node (str): Node name.

    Returns:
        om2.MMatrix: World matrix.
    """
    return om2.MMatrix(cmds.xform(node, query=True, matrix=True, worldSpace=True))


def mirror_matrix(matrix):
    """Mirror a world matrix across the YZ plane with mirror behavior.

    Like ``mirrorJoint -mirrorBehavior``, all axes are flipped so the result
    has no negative scale.

    Args:
        matrix (om2.MMatrix): World matrix.

    Returns:
        om2.MMatrix: Mirrored world matrix.
    """
    reflect = om2.MMatrix((-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))
    behavior = om2.MMatrix((-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1))
    return behavior * matrix * reflect


def set_joint_world_matrix(jnt, matrix):
    """Place a joint at a world matrix, keeping its rotate channels.

    The rotation not covered by the joint's rotate values goes into its
    joint orient, so SDK or RBF on rotate keep working.

    Args:
        jnt (str): Joint name.
        matrix (om2.MMatrix): World matrix.
    """
    parent = _parent(jnt)
    local = matrix * _world_matrix(parent).inverse() if parent else matrix
    xform = om2.MTransformationMatrix(local)
    rotate = [math.radians(v) for v in cmds.getAttr(jnt + ".rotate")[0]]
    order = cmds.getAttr(jnt + ".rotateOrder")
    rot_matrix = om2.MEulerRotation(rotate, order).asMatrix()
    orient_matrix = rot_matrix.inverse() * xform.asRotateMatrix()
    orient = om2.MTransformationMatrix(orient_matrix).rotation()
    cmds.setAttr(jnt + ".translate", *xform.translation(om2.MSpace.kTransform))
    cmds.setAttr(jnt + ".jointOrient", *[math.degrees(v) for v in orient])
    cmds.setAttr(jnt + ".scale", *xform.scale(om2.MSpace.kTransform))


# Editing ---------------------------------------------------------------------


def _blends_from(joints):
    """Return the blend joints of a list of gimmick joints.

    Support joints give their blend joint.

    Args:
        joints (list of str): Gimmick joints.

    Returns:
        list of str: Blend joints, without duplicates.
    """
    blends = []
    for jnt in joints:
        kind = get_kind(jnt)
        if kind == SUPPORT:
            jnt = _display_name(_parent(jnt))
        elif kind != BLEND:
            continue
        if jnt not in blends:
            blends.append(jnt)
    return blends


def mirror_gimmick_joints(joints=None, direction=LEFT_TO_RIGHT, replace=False):
    """Mirror blend joints and their support joints to the other side.

    Each mirrored blend joint is created for the mirrored source joint with
    the same blend and comp scale. Each support joint keeps its index and
    gets the mirrored world matrix of its source support. The source side
    is not modified.

    Args:
        joints (list of str, optional): Gimmick joints to mirror. Default is
            all the gimmick joints of the side the direction mirrors from.
        direction (str, optional): ``LEFT_TO_RIGHT`` or ``RIGHT_TO_LEFT``.
        replace (bool, optional): Rebuild mirrored blend joints that already
            exist. If False they are kept as they are.

    Returns:
        list of str: Created blend and support joints.
    """
    from_side = LEFT if direction == LEFT_TO_RIGHT else RIGHT
    if joints is None:
        joints = list_gimmick_joints(kind=BLEND, side=from_side)
    created = []
    for blend in _blends_from(joints):
        source = get_source_joint(blend)
        if not source or get_side(source) != from_side:
            continue
        target_source = get_mirror_name(source)
        if target_source == source or not _is_joint(target_source):
            cmds.warning(
                "No mirror joint found for {} ({}). Skipped".format(blend, source)
            )
            continue
        existing = find_blend_joint(target_source)
        if existing:
            if not replace:
                continue
            delete_gimmick_joints([existing])

        custom = _custom_name(blend)
        new_blend = _build_blend_joint(
            target_source,
            get_blend_value(blend),
            cmds.getAttr(blend + ".segmentScaleCompensate"),
            get_mirror_name(custom, joint=source) if custom else None,
        )
        _copy_display(blend, new_blend)
        created.append(new_blend)

        for support in get_support_joints(blend):
            new_support = create_support_joint(new_blend, index=_support_index(support))
            cmds.setAttr(
                new_support + ".rotateOrder", cmds.getAttr(support + ".rotateOrder")
            )
            cmds.setAttr(new_support + ".rotate", *cmds.getAttr(support + ".rotate")[0])
            set_joint_world_matrix(new_support, mirror_matrix(_world_matrix(support)))
            _copy_display(support, new_support)
            created.append(new_support)
    return created


def flip_orientation(joints, axis="Y"):
    """Add 180 degrees to the joint orient of support joints on one axis.

    Args:
        joints (list of str): Support joints. Other joints are skipped.
        axis (str, optional): ``X``, ``Y`` or ``Z``.

    Returns:
        list of str: Flipped joints.
    """
    axis = axis.upper()
    flipped = []
    for jnt in joints:
        if not is_support_joint(jnt):
            cmds.warning("{} is not a support joint. Skipped".format(jnt))
            continue
        plug = "{}.jointOrient{}".format(jnt, axis)
        value = cmds.getAttr(plug) + 180.0
        if value > 360.0:
            value -= 360.0
        elif value < -360.0:
            value += 360.0
        cmds.setAttr(plug, value)
        flipped.append(jnt)
    return flipped


def delete_gimmick_joints(joints):
    """Delete gimmick joints with their pairBlend nodes.

    A blend joint is deleted with its support joints.

    Args:
        joints (list of str): Gimmick joints. Other nodes are ignored.

    Returns:
        list of str: Deleted joints.
    """
    to_delete = []
    deleted = []
    for jnt in joints:
        if not cmds.objExists(jnt):
            continue
        kind = get_kind(jnt)
        if not kind:
            continue
        deleted.append(jnt)
        if kind == BLEND:
            deleted.extend(get_support_joints(jnt))
            pair_blend = _pair_blend(jnt)
            if pair_blend:
                to_delete.append(pair_blend)
        to_delete.append(_long_name(jnt) or jnt)
    to_delete = [n for n in dict.fromkeys(to_delete) if cmds.objExists(n)]
    if to_delete:
        cmds.delete(to_delete)
    return list(dict.fromkeys(deleted))


# File IO ---------------------------------------------------------------------


def _blend_item(jnt):
    """Return the file item of a blend joint.

    Args:
        jnt (str): Blend joint.

    Returns:
        dict: Serializable data.
    """
    source = get_source_joint(jnt)
    return {
        "name": node_remap.leaf_name(jnt),
        "kind": BLEND,
        "source": node_remap.leaf_name(source) if source else None,
        "custom_name": _custom_name(jnt),
        "weight": get_blend_value(jnt),
        "comp_scale": cmds.getAttr(jnt + ".segmentScaleCompensate"),
        "radius": cmds.getAttr(jnt + ".radius"),
        "color": cmds.getAttr(jnt + ".overrideColor"),
    }


def _support_item(jnt):
    """Return the file item of a support joint.

    Args:
        jnt (str): Support joint.

    Returns:
        dict: Serializable data.
    """
    item = {
        "name": node_remap.leaf_name(jnt),
        "kind": SUPPORT,
        "blend": node_remap.leaf_name(_parent(jnt)),
        "radius": cmds.getAttr(jnt + ".radius"),
        "color": cmds.getAttr(jnt + ".overrideColor"),
        "rotateOrder": cmds.getAttr(jnt + ".rotateOrder"),
    }
    for attr in ("translate", "rotate", "jointOrient", "scale"):
        item[attr] = list(cmds.getAttr("{}.{}".format(jnt, attr))[0])
    return item


def export_file(path, joints=None):
    """Export gimmick joints to a ``.gst`` file.

    Args:
        path (str): File path. ``.gst`` is added when it has no extension.
        joints (list of str, optional): Gimmick joints. The supports of the
            given blend joints are included. Default is all of them.

    Returns:
        str: The written file path, or None when there was nothing to export.
    """
    if joints is None:
        joints = list_gimmick_joints()
    blends = []
    supports = []
    for jnt in joints:
        kind = get_kind(jnt)
        if kind == BLEND:
            blends.append(jnt)
            supports.extend(get_support_joints(jnt))
        elif kind == SUPPORT:
            supports.append(jnt)
    if not blends and not supports:
        cmds.warning("No gimmick joints to export")
        return None
    items = [_blend_item(j) for j in dict.fromkeys(blends)]
    items += [_support_item(j) for j in dict.fromkeys(supports)]
    path = config_io.file_path(path, FILE_EXT)
    config_io.write_file(path, FILE_TYPE, SCHEMA_VERSION, ITEMS_KEY, items)
    return path


def _legacy_display(info):
    """Return the display values of an item of the old Gimmick Setup Tool.

    Args:
        info (dict): Old file joint data.

    Returns:
        dict: ``radius`` and ``color`` (an RGB color falls back to the
            default color index).
    """
    color = info.get("jointColor")
    return {
        "radius": info.get("jointSize", JOINT_RADIUS),
        "color": color if isinstance(color, int) else JOINT_COLOR,
    }


def _convert_legacy(data):
    """Convert a file of the old Gimmick Setup Tool to file items.

    Args:
        data (dict): Old file data with ``Blend`` and ``Support`` dicts.

    Returns:
        list of dict: File items. Support items have a ``world_matrix``.
    """
    items = []
    blend_names = {}
    for name, info in data.get(BLEND, {}).items():
        drive = info.get("drive")
        if not drive:
            continue
        blend_names[name] = BLEND_PREFIX + node_remap.short_name(drive)
        item = {
            "name": blend_names[name],
            "kind": BLEND,
            "source": drive,
            "custom_name": None,
            "weight": info.get("weightValue", 0.5),
            "comp_scale": True,
        }
        item.update(_legacy_display(info))
        items.append(item)
    for info in data.get(SUPPORT, {}).values():
        blend = blend_names.get(info.get("parent"))
        if not blend:
            continue
        xform = om2.MTransformationMatrix()
        xform.setTranslation(
            om2.MVector(info.get("translate", (0, 0, 0))), om2.MSpace.kWorld
        )
        xform.setRotation(om2.MQuaternion(info.get("rotate", (0, 0, 0, 1))))
        item = {
            "name": None,
            "kind": SUPPORT,
            "blend": blend,
            "world_matrix": [xform.asMatrix()[i] for i in range(16)],
        }
        item.update(_legacy_display(info))
        items.append(item)
    return items


def load_file(path):
    """Load the items of a ``.gst`` file.

    Files of the old Gimmick Setup Tool (no header) are converted.

    Args:
        path (str): File path.

    Returns:
        list of dict: File items.

    Raises:
        ValueError: If the file is not a gimmick joints file.
    """
    try:
        return config_io.load_file(path, FILE_TYPE, "gimmick joints")[ITEMS_KEY]
    except ValueError:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and "type" not in data and BLEND in data:
            return _convert_legacy(data)
        raise


def _apply_item_display(jnt, item):
    """Set the radius and color of an imported joint from its file item.

    Args:
        jnt (str): Joint name.
        item (dict): File item.
    """
    _set_display(
        jnt,
        radius=item.get("radius", JOINT_RADIUS),
        color=item.get("color", JOINT_COLOR),
    )


def _import_blend(item, replace):
    """Create the blend joint of a file item.

    Args:
        item (dict): Blend item.
        replace (bool): Rebuild an existing blend joint.

    Returns:
        tuple: The blend joint (None when the source is missing) and True
            when it was created.
    """
    source = item.get("source")
    if not _is_joint(source):
        cmds.warning("Source joint {} not found. Skipped".format(source))
        return None, False
    existing = find_blend_joint(source)
    if existing:
        if not replace:
            cmds.warning("{} already exists. Skipped".format(existing))
            return existing, False
        delete_gimmick_joints([existing])
    jnt = _build_blend_joint(
        source,
        item.get("weight", 0.5),
        item.get("comp_scale", True),
        item.get("custom_name"),
    )
    _apply_item_display(jnt, item)
    return jnt, True


def _import_support(item, blends, replace):
    """Create the support joint of a file item.

    Args:
        item (dict): Support item.
        blends (dict): Blend item name to created blend joint.
        replace (bool): Rebuild an existing support joint.

    Returns:
        str: The support joint, None when skipped.
    """
    blend = blends.get(item["blend"]) or item["blend"]
    if not is_blend_joint(blend):
        cmds.warning("Blend joint {} not found. Skipped".format(item["blend"]))
        return None
    name = item.get("name")
    index = None
    if name:
        index = _support_index(name)
        for support in get_support_joints(blend):
            if node_remap.leaf_name(support) == name:
                if not replace:
                    cmds.warning("{} already exists. Skipped".format(support))
                    return None
                delete_gimmick_joints([support])
    jnt = create_support_joint(blend, index=index)
    if "world_matrix" in item:
        set_joint_world_matrix(jnt, om2.MMatrix(item["world_matrix"]))
    else:
        cmds.setAttr(jnt + ".rotateOrder", item.get("rotateOrder", 0))
        for attr in ("translate", "rotate", "jointOrient", "scale"):
            if attr in item:
                cmds.setAttr("{}.{}".format(jnt, attr), *item[attr])
    _apply_item_display(jnt, item)
    return jnt


def import_file(path, replace=True):
    """Import gimmick joints from a ``.gst`` file.

    Blend joints are created first, then support joints. Items whose source
    or blend joint is missing are skipped with a warning.

    Args:
        path (str): File path.
        replace (bool, optional): Rebuild existing gimmick joints of the same
            name. If False they are kept.

    Returns:
        list of str: Created joints.

    Raises:
        ValueError: If the file is not a gimmick joints file.
    """
    items = load_file(path)
    created = []
    blends = {}
    for item in items:
        if item.get("kind") != BLEND:
            continue
        jnt, is_new = _import_blend(item, replace)
        if jnt:
            blends[item["name"]] = jnt
        if is_new:
            created.append(jnt)
    for item in items:
        if item.get("kind") != SUPPORT:
            continue
        jnt = _import_support(item, blends, replace)
        if jnt:
            created.append(jnt)
    return created
