"""Proxy joint chains for chain springs (Maya).

Builds, for a :mod:`chain` tree of controls:

- ``sprg_root`` transforms mirroring the control hierarchy, receiving the
  control animation (the target pose is the pure animation, never the
  simulated parents);
- pose holders next to the roots, holding a stored or keyable pose;
- a target joint chain following the roots (or the pose holders);
- a sim joint chain, driven by a solver attached per section;
- parent constraints from the target and sim joints to the controls,
  their weights blended by an intensity plug.

No solver code here: :func:`build` takes an ``attach`` callable, so the
proxies can be built and tested without any solver plug-in.
"""

import maya.api.OpenMaya as om2
from maya import cmds

from mgear.core import anim_utils
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


def _build_poses(roots, prefix):
    """Create the pose holders, next to the spring roots.

    A pose holder takes its root's translation and keeps a static, or
    keyable, rotation: the stored target pose.

    Args:
        roots (dict): ``{control: spring root}``.
        prefix (str): Name prefix.

    Returns:
        dict: ``{control: pose holder long name}``.
    """
    poses = {}
    for control, root in roots.items():
        parent = cmds.listRelatives(root, parent=True, fullPath=True)
        pose = create_dag_node(
            cmds.nodeType(root),
            "{}_{}_sprg_pose".format(prefix, node_remap.flat_name(control)),
            parent[0] if parent else None,
        )
        transform.copy_local_transform(root, pose)
        cmds.connectAttr(root + ".translate", pose + ".translate")
        poses[control] = pose
    return poses


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
        pose_weight_plug (str): 0-1 plug blending the target joints
            between the animation (0) and the pose holders (1).
        policy (str, optional): Branch-root policy, see :mod:`chain`.
        primary (int, optional): Branch followed with the primary policy.
        tip_length (float, optional): Virtual tip length factor.
        attach (callable, optional): ``attach(section, sim_bone, sim_end,
            target_bone)`` called for each section to drive the sim bone.

    Returns:
        dict: ``group`` (the proxy group), ``roots`` and ``poses``
        (control: node), ``target`` and
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
    poses = _build_poses(roots, prefix)
    target = _build_joints(
        prefix + "_target", specs, positions, tips, group, up_vectors
    )
    sim = _build_joints(prefix + "_sim", specs, positions, tips, group, up_vectors)
    for joint in list(target.values()) + list(sim.values()):
        cmds.setAttr(joint + ".drawStyle", 2)

    # one reverse node per weight plug, shared by every constraint
    reverse = cmds.createNode("reverse", name=prefix + "_sprg_rev")
    cmds.connectAttr(pose_weight_plug, reverse + ".inputX")
    cmds.connectAttr(intensity_plug, reverse + ".inputY")
    pose_weights = (reverse + ".outputX", pose_weight_plug)
    intensity_weights = (reverse + ".outputY", intensity_plug)

    # target pose: the joints follow the animated roots or the poses. The
    # sim joints take the target translation, so animated lengths too
    for spec in specs:
        if spec.key[0] == "tip":
            continue
        constraint = cmds.parentConstraint(
            [roots[spec.control], poses[spec.control]],
            target[spec.key],
            maintainOffset=True,
        )[0]
        _connect_weights(constraint, 1, *pose_weights)
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
        _connect_weights(constraint, len(keys), *intensity_weights)
        constraints[control] = constraint
    return {
        "group": group,
        "roots": roots,
        "poses": poses,
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
