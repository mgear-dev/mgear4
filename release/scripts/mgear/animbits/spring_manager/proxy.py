"""Proxy joint chains for chain springs (Maya).

Builds, for a :mod:`chain` tree of controls:

- ``sprg_root`` transforms mirroring the control hierarchy, receiving the
  control animation (the target pose is the pure animation, never the
  simulated parents);
- pose holders, a chain mirroring the roots, holding a stored or keyable
  pose;
- source transforms, a chain mirroring the roots, blending in local space
  between the roots and the pose holders;
- a target joint chain following the sources;
- a sim joint chain, driven by a solver attached per section;
- parent constraints from the target and sim joints to the controls,
  their weights blended by an intensity plug.

No solver code here: :func:`build` takes an ``attach`` callable, so the
proxies can be built and tested without any solver plug-in.
"""

import maya.api.OpenMaya as om2
from maya import cmds

from mgear.core import anim_utils
from mgear.core import applyop
from mgear.core import dag
from mgear.core import node_remap
from mgear.core import transform
from mgear.core.node import create_dag_node

from . import chain
from . import constants
from .backends import constraint_skips


def control_children(node):
    """Return the child controls of a control, looking through groups.

    Args:
        node (str): Control name.

    Returns:
        list: Child control long names, in order.
    """
    return dag.get_child_controls(node)


def _position(node):
    return om2.MVector(cmds.xform(node, query=True, worldSpace=True, translation=True))


def _world_matrix(node):
    return om2.MMatrix(cmds.xform(node, query=True, worldSpace=True, matrix=True))


def tip_position(tree_node, tip_length=1.0):
    """Return the world position of the tip after a leaf control.

    Uses the first non-control child transform of the leaf. Without one,
    extends the last bone by ``tip_length`` times its length, or along the
    control X axis by ``tip_length`` for a single control chain.

    Args:
        tree_node (chain.ChainNode): Leaf node.
        tip_length (float, optional): Virtual tip length factor.

    Returns:
        om2.MVector: World position.
    """
    end = _position(tree_node.name)
    for child in (
        cmds.listRelatives(
            tree_node.name, children=True, type="transform", fullPath=True
        )
        or []
    ):
        if dag.is_curve_control(child):
            continue
        position = _position(child)
        if (position - end).length() > 1e-4:
            return position
    if tree_node.parent is not None:
        start = _position(tree_node.parent.name)
        return end + (end - start) * tip_length
    axis = om2.MVector(*list(_world_matrix(tree_node.name))[0:3]).normal()
    return end + axis * tip_length


# -----------------------------------------------------------------------------
# Building
# -----------------------------------------------------------------------------


def _build_joints(prefix, specs, positions, tips, parent, up_vectors):
    """Create a joint chain from :func:`chain.plan` joint specs.

    Joint orientation is stored in ``jointOrient``; rotate stays at 0 and
    the rotate order is xyz.

    Args:
        prefix (str): Name prefix.
        specs (list): :class:`chain.JointSpec` items, parents first.
        positions (dict): ``{control: om2.MVector}``.
        tips (dict): ``{leaf control: om2.MVector}``.
        parent (str): Parent of the chain root joint.
        up_vectors (dict): ``{control: om2.MVector}`` up hints.

    Returns:
        dict: ``{joint key: long name}``.
    """
    joints = {}
    for spec in specs:
        kind = spec.key[0]
        suffix = "_".join(str(part) for part in spec.key[2:])
        name = "{}_{}_{}{}_jnt".format(
            prefix,
            node_remap.flat_name(spec.control),
            kind,
            "_" + suffix if suffix else "",
        )
        joint_parent = joints[spec.parent] if spec.parent else parent
        joint = create_dag_node("joint", name, joint_parent)
        position = tips[spec.control] if kind == "tip" else positions[spec.control]
        if spec.aim == "tip":
            aim = tips[spec.control]
        elif spec.aim:
            aim = positions[spec.aim]
        else:
            aim = None
        if aim is not None and (aim - position).length() > 1e-6:
            matrix = transform.get_aim_matrix(position, aim, up_vectors[spec.control])
        else:
            # pivots and tips keep the parent orientation
            matrix = _world_matrix(joint_parent)
            matrix[12], matrix[13], matrix[14] = position.x, position.y, position.z
        cmds.xform(joint, worldSpace=True, matrix=list(matrix))
        cmds.makeIdentity(joint, apply=True, rotate=True, scale=True)
        cmds.setAttr(joint + ".rotateOrder", 0)
        cmds.setAttr(joint + ".segmentScaleCompensate", True)
        joints[spec.key] = joint
    return joints


def _build_roots(tree, prefix):
    """Create the spring roots mirroring the control hierarchy.

    The tree root's spring root goes under the root control's parent.
    Child roots go under their parent control's root, through an offset
    group holding the static matrix of the groups between the controls.
    Each root copies its control's local transform and receives its
    translate / rotate animation.

    Args:
        tree (chain.ChainNode): The root node.
        prefix (str): Name prefix.

    Returns:
        dict: ``{control: spring root long name}``.
    """
    roots = {}
    for node in tree.walk():
        control = node.name
        base = "{}_{}".format(prefix, node_remap.flat_name(control))
        node_type = "joint" if cmds.nodeType(control) == "joint" else "transform"
        dag_parent = cmds.listRelatives(control, parent=True, fullPath=True)
        if node.parent is None:
            parent = dag_parent[0] if dag_parent else None
        else:
            parent = create_dag_node(
                "transform", base + "_sprg_off", roots[node.parent.name]
            )
            if dag_parent:
                cmds.xform(
                    parent, worldSpace=True, matrix=list(_world_matrix(dag_parent[0]))
                )
        root = create_dag_node(node_type, base + "_sprg_root", parent)
        transform.copy_local_transform(control, root)
        anim_utils.move_animation_curves(control, root, constants.MOVED_ATTRS)
        roots[control] = root
    return roots


def _build_mirror(
    tree, roots, prefix, suffix, node_type=None, attrs=transform.LOCAL_TRANSFORM_ATTRS
):
    """Create a tree of nodes mirroring the spring roots.

    The tree root's node goes under the root control's parent. Child nodes
    go under their parent's node, through an offset group holding the
    local matrix of their root's offset group, so each node has the same
    local space as its root.

    Args:
        tree (chain.ChainNode): The root node.
        roots (dict): ``{control: spring root}``.
        prefix (str): Name prefix.
        suffix (str): Name suffix, after ``sprg_``.
        node_type (str, optional): Node type. Default: the root's type.
        attrs (tuple, optional): Local transform attributes copied from
            the roots, see :func:`transform.copy_local_transform`.

    Returns:
        dict: ``{control: node long name}``.
    """
    nodes = {}
    for node in tree.walk():
        control = node.name
        root = roots[control]
        base = "{}_{}_sprg_{}".format(prefix, node_remap.flat_name(control), suffix)
        root_parent = cmds.listRelatives(root, parent=True, fullPath=True)
        if node.parent is None:
            parent = root_parent[0] if root_parent else None
        else:
            # local matrix: the parent node may not be at its root's pose yet
            parent = create_dag_node(
                "transform", base + "_off", nodes[node.parent.name]
            )
            cmds.xform(
                parent,
                objectSpace=True,
                matrix=cmds.xform(root_parent[0], query=True, matrix=True),
            )
        mirror = create_dag_node(node_type or cmds.nodeType(root), base, parent)
        transform.copy_local_transform(root, mirror, attrs)
        nodes[control] = mirror
    return nodes


def _build_poses(tree, roots, prefix):
    """Create the pose holders, a chain mirroring the spring roots.

    A pose holder takes its root's translation and keeps a static, or
    keyable, rotation: the stored target pose. Rotating a pose holder
    carries the pose holders below it.

    Args:
        tree (chain.ChainNode): The root node.
        roots (dict): ``{control: spring root}``.
        prefix (str): Name prefix.

    Returns:
        dict: ``{control: pose holder long name}``.
    """
    poses = _build_mirror(tree, roots, prefix, "pose")
    for control, pose in poses.items():
        cmds.connectAttr(roots[control] + ".translate", pose + ".translate")
    return poses


def _build_sources(tree, roots, poses, prefix, pose_weight_plug):
    """Create the target pose sources, a chain mirroring the spring roots.

    Each source takes the blend, in local space, of its root's matrix (the
    animation) and its pose holder's matrix (the stored pose), so the bone
    lengths hold at every weight.

    Args:
        tree (chain.ChainNode): The root node.
        roots (dict): ``{control: spring root}``.
        poses (dict): ``{control: pose holder}``.
        prefix (str): Name prefix.
        pose_weight_plug (str): 0-1 plug blending the sources between the
            animation (0) and the pose holders (1).

    Returns:
        dict: ``{control: source long name}``.
    """
    sources = _build_mirror(
        tree, roots, prefix, "src", "transform", ("offsetParentMatrix",)
    )
    for control, source in sources.items():
        blend = cmds.createNode(
            "blendMatrix", name=source.split("|")[-1] + "_blendMatrix"
        )
        cmds.connectAttr(roots[control] + ".matrix", blend + ".inputMatrix")
        cmds.connectAttr(poses[control] + ".matrix", blend + ".target[0].targetMatrix")
        cmds.connectAttr(pose_weight_plug, blend + ".target[0].weight")
        applyop.connect_decomposed(blend + ".outputMatrix", source, "srth")
    return sources


def build(
    tree,
    prefix,
    intensity_plug,
    pose_weight_plug,
    policy=chain.KINEMATIC,
    primary=0,
    tip_length=1.0,
    attach=None,
):
    """Build the proxy chains of a tree and drive its controls.

    Args:
        tree (chain.ChainNode): Tree of control long names.
        prefix (str): Name prefix of the created nodes.
        intensity_plug (str): 0-1 plug blending each control between its
            target joints (0, the animation) and its sim joints (1).
        pose_weight_plug (str): 0-1 plug blending the target joints, in
            local space, between the animation (0) and the pose holders (1).
        policy (str, optional): Branch-root policy, see :mod:`chain`.
        primary (int, optional): Branch followed with the primary policy.
        tip_length (float, optional): Virtual tip length factor.
        attach (callable, optional): ``attach(section, sim_bone, sim_end,
            target_bone)`` called for each section to drive the sim bone.

    Returns:
        dict: ``group`` (the proxy group), ``roots``, ``poses`` and
        ``sources`` (control: node), ``target`` and
        ``sim`` (joint key: joint), ``sections`` (plan sections) and
        ``constraints`` (control: constraint).
    """
    specs, sections, drivers = chain.plan(tree, policy, primary)
    controls = [node.name for node in tree.walk()]
    positions = {control: _position(control) for control in controls}
    up_vectors = {
        control: om2.MVector(*list(_world_matrix(control))[4:7]) for control in controls
    }
    tips = {
        node.name: tip_position(node, tip_length)
        for node in tree.walk()
        if not node.children
    }

    # created under the root control's parent: follows the parent motion
    dag_parent = cmds.listRelatives(tree.name, parent=True, fullPath=True)
    group = create_dag_node(
        "transform",
        "{}_sprg_grp".format(prefix),
        dag_parent[0] if dag_parent else None,
    )
    roots = _build_roots(tree, prefix)
    poses = _build_poses(tree, roots, prefix)
    sources = _build_sources(tree, roots, poses, prefix, pose_weight_plug)
    target = _build_joints(
        prefix + "_target", specs, positions, tips, group, up_vectors
    )
    sim = _build_joints(prefix + "_sim", specs, positions, tips, group, up_vectors)
    for joint in list(target.values()) + list(sim.values()):
        cmds.setAttr(joint + ".drawStyle", 2)

    # one reverse node, shared by every control constraint
    reverse = cmds.createNode("reverse", name=prefix + "_sprg_rev")
    cmds.connectAttr(intensity_plug, reverse + ".inputX")

    # target pose: the joints follow the sources, blending the animation
    # and the poses. The sim joints take the target translation, so
    # animated lengths too
    for spec in specs:
        if spec.key[0] == "tip":
            continue
        cmds.parentConstraint(
            sources[spec.control], target[spec.key], maintainOffset=True
        )
        if spec.parent is not None:
            cmds.connectAttr(
                target[spec.key] + ".translate", sim[spec.key] + ".translate"
            )
    root_key = specs[0].key
    cmds.pointConstraint(roots[tree.name], sim[root_key], maintainOffset=True)
    if root_key[0] == "pivot":
        # a branching root is not simulated: it follows the animation
        cmds.orientConstraint(roots[tree.name], sim[root_key], maintainOffset=True)

    if attach:
        for section in sections:
            attach(section, sim[section.bone], sim[section.end], target[section.bone])

    constraints = {}
    for control, keys in drivers.items():
        skips = constraint_skips(control)
        constraint = cmds.parentConstraint(
            [target[key] for key in keys] + [sim[key] for key in keys],
            control,
            maintainOffset=True,
            skipTranslate=skips[0] or "none",
            skipRotate=skips[1] or "none",
        )[0]
        _connect_weights(constraint, len(keys), reverse + ".outputX", intensity_plug)
        constraints[control] = constraint
    return {
        "group": group,
        "roots": roots,
        "poses": poses,
        "sources": sources,
        "target": target,
        "sim": sim,
        "sections": sections,
        "constraints": constraints,
    }


def _connect_weights(constraint, count, first_plug, other_plug):
    """Drive constraint weights: the first targets by one plug, the others
    by another.

    Args:
        constraint (str): Parent constraint.
        count (int): Number of first targets.
        first_plug (str): Plug driving the first targets weights.
        other_plug (str): Plug driving the other targets weights.
    """
    weights = cmds.parentConstraint(constraint, query=True, weightAliasList=True)
    for alias in weights[:count]:
        cmds.connectAttr(first_plug, "{}.{}".format(constraint, alias))
    for alias in weights[count:]:
        cmds.connectAttr(other_plug, "{}.{}".format(constraint, alias))
    cmds.setAttr(constraint + ".interpType", 2)
