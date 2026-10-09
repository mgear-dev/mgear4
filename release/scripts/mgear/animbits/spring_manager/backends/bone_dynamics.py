"""Bone Dynamics backend: chain springs solved by boneDynamicsNode.

boneDynamicsNode (https://github.com/akasaki1211/boneDynamicsNode, MIT
License, Copyright (c) 2024 Hiroyuki Akasaki) is an optional third-party
plug-in, not shipped with mGear. Only the compiled plug-in is used: the
node connections below follow its documented ``bdn`` setup scripts, which
are not imported.

Each spring simulates a tree of controls through proxy joints (see
:mod:`..proxy`): one boneDynamicsNode per bone section, the target pose
coming from the target joints, the shared settings from the scene solver
node (:mod:`..solver`).
"""

import json

from maya import cmds

import mgear
from mgear.core import anim_utils
from mgear.core import attribute
from mgear.core import dag
from mgear.core import node_remap
from mgear.core import utils

from . import SpringBackend
from . import add_settings
from . import nodes_of_type
from . import remove_settings
from . import rest_values
from . import restore_rest_values
from .. import chain
from .. import colliders
from .. import constants
from .. import proxy
from .. import registry
from .. import solver

BACKEND = constants.BONE_DYNAMICS_BACKEND
PLUGIN = "boneDynamicsNode"
NODE_TYPE = "boneDynamicsNode"
VISUALIZER_TYPE = "boneDynamicsVisualizer"

# Parameters ---------------------------------------------------------------
INTENSITY = "springTotalIntensity"
DAMPING = "springDamping"
ELASTICITY = "springElasticity"
STIFFNESS = "springStiffness"
MASS = "springMass"
TIP = "Tip"
GRAVITY = "springGravity"
WIND_SCALE = "springWindScale"
ANGLE_ENABLE = "springAngleLimitEnable"
ANGLE = "springAngleLimit"
TURBULENCE_ENABLE = "springTurbulenceEnable"
TURBULENCE_STRENGTH = "springTurbulenceStrength"
TURBULENCE_SEED = "springTurbulenceSeed"
TURBULENCE_SEED_PER_BONE = "springTurbulenceSeedPerBone"
FORCE_FUNCTION = "springElasticForceFunction"
RADIUS = "springRadius"
TIP_RADIUS = "springTipRadius"
BONE_CAPSULE = "springBoneAsCapsule"
MESH_CUTOFF = "springMeshCutoff"
OFFSET_WEIGHT = "springOffsetWeight"
TARGET_BLEND = "springTargetBlend"

_param = constants.param
BDN_PARAMS = (
    _param(INTENSITY, "Total Intensity", 1.0, "Global"),
    _param(DAMPING, "Damping", 0.1, "Dynamics"),
    _param(
        ELASTICITY,
        "Elasticity",
        30.0,
        "Dynamics",
        maximum=5000.0,
        soft_maximum=200.0,
    ),
    _param(STIFFNESS, "Stiffness", 0.0, "Dynamics"),
    _param(
        MASS, "Mass", 1.0, "Dynamics", minimum=0.001, maximum=100.0, soft_maximum=10.0
    ),
    _param(DAMPING + TIP, "Damping", 1.0, "Tip Multiplier", maximum=5.0),
    _param(ELASTICITY + TIP, "Elasticity", 1.0, "Tip Multiplier", maximum=5.0),
    _param(STIFFNESS + TIP, "Stiffness", 1.0, "Tip Multiplier", maximum=5.0),
    _param(MASS + TIP, "Mass", 1.0, "Tip Multiplier", maximum=5.0),
    _param(GRAVITY, "Gravity", 0.0, "Forces"),
    _param(WIND_SCALE, "Wind Scale", 1.0, "Forces", maximum=100.0, soft_maximum=10.0),
    _param(
        TURBULENCE_ENABLE,
        "Turbulence",
        False,
        "Forces",
        minimum=False,
        maximum=True,
        kind=constants.PARAM_BOOL,
    ),
    _param(
        TURBULENCE_STRENGTH,
        "Turb. Strength",
        10.0,
        "Forces",
        maximum=1000.0,
        soft_maximum=100.0,
    ),
    _param(
        TURBULENCE_SEED,
        "Turb. Seed",
        0,
        "Forces",
        maximum=1000,
        kind=constants.PARAM_INT,
    ),
    _param(
        TURBULENCE_SEED_PER_BONE,
        "Turb. Seed per Bone",
        False,
        "Forces",
        minimum=False,
        maximum=True,
        kind=constants.PARAM_BOOL,
    ),
    _param(
        ANGLE_ENABLE,
        "Angle Limit",
        False,
        "Limits",
        minimum=False,
        maximum=True,
        kind=constants.PARAM_BOOL,
    ),
    _param(ANGLE, "Angle", 60.0, "Limits", maximum=360.0),
    _param(RADIUS, "Root Radius", 0.0, "Collision", maximum=1000.0, soft_maximum=10.0),
    _param(
        TIP_RADIUS,
        "Tip Radius",
        0.0,
        "Collision",
        maximum=1000.0,
        soft_maximum=10.0,
    ),
    _param(
        BONE_CAPSULE,
        "Bone As Capsule",
        False,
        "Collision",
        minimum=False,
        maximum=True,
        kind=constants.PARAM_BOOL,
    ),
    _param(
        MESH_CUTOFF,
        "Mesh Cutoff",
        10.0,
        "Collision",
        maximum=10000.0,
        soft_maximum=100.0,
    ),
    _param(OFFSET_WEIGHT, "Root Motion Cancel", 1.0, "Root Motion"),
    _param(TARGET_BLEND, "Pose Blend", 0.0, "Target"),
    _param(
        FORCE_FUNCTION,
        "Elastic Function",
        0,
        "Advanced",
        maximum=2,
        kind=constants.PARAM_INT,
    ),
)

BDN_TOOLTIPS = {
    INTENSITY: (
        "Master blend between the animation (0) and the simulation (1).\n"
        "1: full simulation. 0.5: half way, to tone down a shot. Key "
        "it to fade the simulation in or out."
    ),
    DAMPING: (
        "Velocity lost every frame (0-1): how fast the motion calms "
        "down.\n"
        "0.05-0.1: lively, keeps swinging (antennas, ribbons). 0.2-0.3: "
        "natural (tails, hair). 0.4-0.6: heavy or underwater, and "
        "for long chains (20-30 bones)."
    ),
    ELASTICITY: (
        "Force pulling each bone back to its target pose (the "
        "animation): how springy the chain is.\n"
        "20: soft, loose (cloth strips). 60-80: hair, tails. 150+: "
        "springy, snaps back (antennas). 500+: long chains (20-30 "
        "bones) that would sag. 0: the target pose has no effect."
    ),
    STIFFNESS: (
        "Holds each bone where it was on the previous frame: higher "
        "values resist the motion, slower and heavier.\n"
        "0: free motion, the usual choice. 0.05-0.2: some drag (hair, "
        "tails). 0.3: long chains. Above 0.5 the chain barely moves."
    ),
    MASS: (
        "Divides the elasticity, wind and turbulence forces (not the "
        "gravity).\n"
        "1: default. 2-5: heavier, slower to come back and less pushed "
        "by the wind. 0.5: light, very reactive."
    ),
    DAMPING
    + TIP: (
        "Multiplier of the damping at the chain tip: it blends from the "
        "root value to root value x multiplier at the tip.\\n"
        "1: same value along the chain. 0.5: livelier tips. 2: tips calm down faster."
    ),
    ELASTICITY
    + TIP: (
        "Multiplier of the elasticity at the chain tip: it blends from the "
        "root value to root value x multiplier at the tip.\\n"
        "1: same value along the chain. 0.4-0.6: floppier tips, the whip for hair and tails."
    ),
    STIFFNESS
    + TIP: (
        "Multiplier of the stiffness at the chain tip: it blends from the "
        "root value to root value x multiplier at the tip.\\n"
        "1: same value along the chain. 0: free tips. 2: heavier, more dragging tips."
    ),
    MASS
    + TIP: (
        "Multiplier of the mass at the chain tip: it blends from the "
        "root value to root value x multiplier at the tip.\\n"
        "1: same value along the chain. 2: heavier tips (a tail tuft, a braid end)."
    ),
    GRAVITY: (
        "Multiplier of the solver gravity (Solver panel).\n"
        "0: no gravity, the chain holds its pose (antennas). 0.1-0.3: "
        "hair, tails. 0.6-1: hanging things (cloth strips, ropes). "
        "Raise the elasticity with it, or the chain sags."
    ),
    WIND_SCALE: (
        "Multiplier of the connected wind strength for this spring.\n"
        "0: not affected. 1: the wind strength. 2-5: light parts that "
        "catch more wind (hair, cloth) next to heavier ones."
    ),
    TURBULENCE_ENABLE: (
        "Adds a random force whose direction slowly wanders: flutter "
        "and breeze without keys. Repeatable: restarts at the solver "
        "start frame. Combine with a wind for a gusty breeze."
    ),
    TURBULENCE_STRENGTH: (
        "Force of the turbulence, divided by the mass. For scale, the "
        "gravity is 980.\n"
        "10: barely visible. 100-200: gentle breeze on hair or cloth. "
        "500+: strong, chaotic flutter."
    ),
    TURBULENCE_SEED: (
        "Picks another random sequence: another take of the same "
        "turbulence. Change it when two springs move alike."
    ),
    TURBULENCE_SEED_PER_BONE: (
        "Gives every bone its own seed (seed + bone index).\n"
        "Off: the bones and branches share one direction, a coherent "
        "sway. On: they move independently (skirt strands, hair "
        "locks)."
    ),
    ANGLE_ENABLE: (
        "Limits how far each bone can rotate from its target pose. "
        "Takes priority over the collisions."
    ),
    ANGLE: (
        "Maximum angle, in degrees, between a bone and its target "
        "pose.\n"
        "30-45: tight (short hair, stiff straps). 60-90: natural limit "
        "for hair and cloth strips. 120+: only stops extreme flips."
    ),
    OFFSET_WEIGHT: (
        "Cancels the motion of the offset node (the rig world or "
        "global control), so moving the whole character does not "
        "shake the chains.\n"
        "1: fully cancelled, the usual choice. 0: world motion fully "
        "simulated. 0.5: some drag on fast travels or cuts."
    ),
    TARGET_BLEND: (
        "Blend of the target pose between the animation (0) and the "
        "pose holders (1), in the Blend target mode.\n"
        "Key it to fade between following the animation and holding a "
        "captured pose."
    ),
    RADIUS: (
        "Collision radius of the chain at its root, in scene units: the "
        "thickness the colliders push away. The radius blends linearly "
        "to the Tip Radius along the chain. Each bone is a sphere at its "
        "end, or a capsule with Bone As Capsule. Sections with their own "
        "collider (Fit Capsules on the spring controls) use its radii "
        "instead.\n"
        "0: the bone is a point. 0.5-1: thin hair strands. 2-5: braids, "
        "tails, cloth strips. Fit Bone Radius measures both radii from "
        "the mesh."
    ),
    TIP_RADIUS: (
        "Collision radius of the chain at its tip, in scene units.\n"
        "Same as Root Radius: even thickness (ropes, cloth strips). About "
        "a third to a half of it: tapered tails and braids. 0: pointy tip."
    ),
    BONE_CAPSULE: (
        "Collide with the whole bone, a capsule from its root radius to "
        "its end radius, instead of a sphere at its end.\n"
        "On: long bones, few joints (tails, cloth strips): nothing passes "
        "between two joints. Off: faster, enough for dense chains. "
        "Sphere and capsule colliders only."
    ),
    MESH_CUTOFF: (
        "Distance beyond which a mesh collider is ignored, in scene "
        "units: limits the search on big meshes.\n"
        "10: default, a body for a hair chain. Lower it on dense meshes "
        "to save time, raise it for fast motion that moves far from the "
        "mesh in one frame."
    ),
    FORCE_FUNCTION: (
        "Experimental. Shape of the elastic force: 0 Linear (default), "
        "1 Quadratic, 2 Cubic. Quadratic and Cubic pull harder the "
        "further a bone is from its target: big swings come back "
        "faster, small ones stay soft."
    ),
}
BDN_PARAMS = constants.with_tooltips(BDN_PARAMS, BDN_TOOLTIPS)

# parameter: boneDynamicsNode attribute, connected to every node
DIRECT_PARAMS = (
    (GRAVITY, "gravityMultiply"),
    (ANGLE_ENABLE, "enableAngleLimit"),
    (ANGLE, "angleLimit"),
    (TURBULENCE_ENABLE, "enableTurbulence"),
    (TURBULENCE_STRENGTH, "turbulenceStrength"),
    (FORCE_FUNCTION, "elasticForceFunction"),
    (OFFSET_WEIGHT, "offsetMatrixWeight"),
    (BONE_CAPSULE, "boneAsCapsule"),
    (MESH_CUTOFF, "meshColCutoff"),
)
# ramped parameters: (parameter, boneDynamicsNode attribute), one per RGB
RAMPED_PARAMS = (
    (DAMPING, "damping"),
    (ELASTICITY, "elasticity"),
    (STIFFNESS, "stiffness"),
)

# node attribute: suffix of its radius ramp (blendTwoAttr named after the
# node), the spring Root / Tip Radius gradient
RADIUS_RAMPS = {"rootRadius": "_rootRadiusRamp", "radius": "_radiusRamp"}
# boneDynamicsNode collider arrays, cleared and refilled together
COLLIDER_ARRAYS = (
    "sphereCollider",
    "capsuleColliderInput",
    "infinitePlaneCollider",
    "meshCollider",
)

# Network attributes ---------------------------------------------------------
TARGET_MODE_ATTR = "targetMode"
POLICY_ATTR = "branchPolicy"
PRIMARY_ATTR = "primaryBranch"
TIP_LENGTH_ATTR = "tipLength"
TREE_ATTR = "tree"
ROOTS_ATTR = "roots"
POSES_ATTR = "poses"
OFFSET_ATTR = "offsetNode"
WIND_SCALE_ATTR = "windScaleNode"
GROUP_ATTR = "group"
POSE_WEIGHT_ATTR = "poseWeight"

TARGET_ANIMATION = "animation"
TARGET_CONTROLS = "controls"
TARGET_CAPTURED = "captured"
TARGET_BLEND_MODE = "blend"
TARGET_EXTERNAL = "external"
TARGET_MODES = (
    TARGET_ANIMATION,
    TARGET_CONTROLS,
    TARGET_CAPTURED,
    TARGET_BLEND_MODE,
    TARGET_EXTERNAL,
)

AUTO_OFFSET = "auto"
OFFSET_CANDIDATES = ("world_ctl", "global_C0_ctl")

# Wind -----------------------------------------------------------------------
WIND_NAME = "mgear_spring_wind"
WIND_STRENGTH = "strength"
WIND_CONTROLLER_ATTR = "controller"
WIND_VECTOR_ATTR = "windVector"

# boneDynamicsNode attribute: boneDynamicsVisualizer attribute
VISUALIZER_CONNECTIONS = (
    ("outputRotate", "outputRotate"),
    ("iterations", "drawBoneCollision"),
    ("enableAngleLimit", "drawAngleLimit"),
    ("enable", "enable"),
    ("boneTranslate", "boneTranslate"),
    ("boneJointOrient", "boneJointOrient"),
    ("boneParentMatrix", "boneParentMatrix"),
    ("boneParentInverseMatrix", "boneParentInverseMatrix"),
    ("endTranslate", "endTranslate"),
    ("rotationOffset", "rotationOffset"),
    ("boneScale", "boneScale"),
    ("boneInverseScale", "boneInverseScale"),
    ("endScale", "endScale"),
    ("radius", "radius"),
    ("angleLimit", "angleLimit"),
    ("rootRadius", "rootRadius"),
    ("boneAsCapsule", "boneAsCapsule"),
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _plug(node, attr):
    return "{}.{}".format(node, attr)


def _add_message(node, attr, source=None, multi=False):
    """Add a message attribute, optionally connected from a node.

    Args:
        node (str): Node receiving the attribute.
        attr (str): Attribute name.
        source (str, optional): Node whose message is connected.
        multi (bool, optional): Multi attribute.
    """
    cmds.addAttr(node, longName=attr, attributeType="message", multi=multi)
    if source:
        cmds.connectAttr(source + ".message", _plug(node, attr))


def find_offset_node(control):
    """Return the default root-motion node of a control's rig.

    Args:
        control (str): A control of the rig.

    Returns:
        str: The Shifter world or global control in the control's
        namespace, or None.
    """
    namespace = node_remap.get_namespace(control)
    for name in OFFSET_CANDIDATES:
        node = namespace + name
        if cmds.objExists(node):
            return node
    return None


class BoneDynamicsBackend(SpringBackend):
    """Chain springs solved by the optional boneDynamicsNode plug-in."""

    name = BACKEND
    collider_types = colliders.TYPES
    bone_volume = True
    label = "Bone Dynamics"
    unavailable_message = (
        "Install the boneDynamicsNode plug-in to use this solver: copy "
        "boneDynamicsNode.mll for your Maya version to a plug-ins folder "
        "and load it. See Help > Documentation."
    )
    read_only_message = (
        "The boneDynamicsNode plug-in is not loaded: these springs can't be "
        "edited or baked. Install the plug-in, or delete the springs."
    )

    def __init__(self):
        self._saved_start = None

    @property
    def editable(self):
        """bool: Editable only when the plug-in is loaded."""
        return self.is_available()

    def is_available(self):
        return utils.is_plugin_available(PLUGIN)

    def param_specs(self):
        return BDN_PARAMS

    def param_warnings(self, springs, values):
        if any(value.get(ELASTICITY) == 0 for value in values):
            return ["Elasticity is 0: the target pose has no effect."]
        return []

    # create ---------------------------------------------------------------

    def create(self, controls, params=None, options=None):
        """Create chain springs from root controls, in one undo chunk.

        Every selected control without a selected ancestor is a root: its
        child controls are walked into a chain tree.

        Args:
            controls (list): Root controls.
            params (dict, optional): Parameter values.
            options (dict, optional): ``target_mode`` (default
                ``"animation"``), ``branch_policy`` (default
                ``"kinematic"``), ``primary`` (int), ``split`` (bool),
                ``tip_length`` (float, default 1), ``offset`` (node name,
                ``"auto"`` (default) or None), ``visualizer`` (bool),
                ``tree`` (data from :func:`chain.tree_to_data`, with
                scene names, instead of walking the hierarchy).

        Returns:
            list: The created :class:`registry.Spring` records.
        """
        utils.ensure_plugin(PLUGIN)
        options = dict(options or {})
        values = self.default_params()
        values.update(params or {})
        if options.get("tree"):
            trees = [chain.tree_from_data(options["tree"])]
        else:
            trees = [
                chain.build_tree(root, proxy.control_children)
                for root in dag.get_top_nodes(controls)
            ]
        if options.get("split"):
            trees = [sub for tree in trees for sub in chain.split_branches(tree)]
        springs = []
        with utils.undo_chunk("springManagerCreate"):
            solver_node = solver.get_solver()
            for tree in trees:
                spring = self._create_one(tree, values, options, solver_node)
                if spring:
                    springs.append(spring)
        return springs

    def _create_one(self, tree, values, options, solver_node):
        controls = [node.name for node in tree.walk()]
        for control in controls:
            if registry.spring_from_node(control):
                mgear.log(
                    "{} already has a spring, chain skipped".format(control),
                    mgear.sev_warning,
                )
                return None
        root = tree.name
        prefix = node_remap.flat_name(root)
        policy = options.get("branch_policy") or chain.KINEMATIC
        primary = int(options.get("primary", 0))
        tip_length = float(options.get("tip_length", 1.0))
        offset = options.get("offset", AUTO_OFFSET)
        if offset == AUTO_OFFSET:
            offset = find_offset_node(root)

        network = self._create_network(
            tree, prefix, policy, primary, tip_length, offset
        )
        with utils.capture_created_nodes() as created:
            add_settings(root, self.param_specs(), values)
            context = {
                "settings": root,
                "solver": solver_node,
                "offset": offset,
                "enable": self._enable_plug(root, solver_node, prefix),
                "count": 0,
            }
            context.update(self._ramp_plugs(root, prefix))
            rig = proxy.build(
                tree,
                prefix,
                intensity_plug=_plug(root, INTENSITY),
                pose_weight_plug=_plug(network, POSE_WEIGHT_ATTR),
                policy=policy,
                primary=primary,
                tip_length=tip_length,
                attach=lambda section, bone, end, target: self._attach(
                    section, bone, end, target, context
                ),
            )
        cmds.connectAttr(rig["group"] + ".message", _plug(network, GROUP_ATTR))
        attribute.connect_messages(
            [rig["roots"][control] for control in controls], network, ROOTS_ATTR
        )
        attribute.connect_messages(
            [rig["poses"][control] for control in controls], network, POSES_ATTR
        )
        registry.add_members(network, created)
        spring = registry.Spring(network, self.name)
        mode = options.get("target_mode") or TARGET_ANIMATION
        if mode != TARGET_ANIMATION:
            self.set_target_mode([spring], mode, options.get("external"))
        if options.get("visualizer"):
            self.set_visualizer([spring], True)
        return spring

    def _create_network(self, tree, prefix, policy, primary, tip_length, offset):
        """Create the tagged network of a chain spring.

        Returns:
            str: The network node.
        """
        controls = [node.name for node in tree.walk()]
        network = registry.create_network(
            "{}_{}".format(prefix, constants.NETWORK_SUFFIX),
            self.name,
            controls,
            tree.name,
            {
                TARGET_MODE_ATTR: TARGET_ANIMATION,
                POLICY_ATTR: policy,
                TREE_ATTR: json.dumps(chain.tree_to_data(tree), separators=(",", ":")),
                constants.REST_ATTR: json.dumps(rest_values(controls)),
            },
        )
        cmds.addAttr(network, longName=PRIMARY_ATTR, attributeType="long")
        cmds.setAttr(_plug(network, PRIMARY_ATTR), primary)
        cmds.addAttr(network, longName=TIP_LENGTH_ATTR, attributeType="double")
        cmds.setAttr(_plug(network, TIP_LENGTH_ATTR), tip_length)
        cmds.addAttr(network, longName=POSE_WEIGHT_ATTR, attributeType="double")
        _add_message(network, ROOTS_ATTR, multi=True)
        _add_message(network, POSES_ATTR, multi=True)
        _add_message(network, OFFSET_ATTR, offset)
        _add_message(network, WIND_SCALE_ATTR)
        _add_message(network, GROUP_ATTR)
        return network

    def _enable_plug(self, control, solver_node, prefix):
        """Return a plug that is on when the solver is on and intensity > 0.

        Args:
            control (str): Settings control.
            solver_node (str): Solver node.
            prefix (str): Name prefix.

        Returns:
            str: The enable plug.
        """
        # multiplyDivide: multDoubleLinear is deprecated in Maya 2026
        multiply = cmds.createNode("multiplyDivide", name=prefix + "_sprg_enable_mul")
        cmds.connectAttr(_plug(control, INTENSITY), multiply + ".input1X")
        cmds.connectAttr(_plug(solver_node, solver.ENABLE), multiply + ".input2X")
        condition = cmds.createNode("condition", name=prefix + "_sprg_enable_cnd")
        cmds.connectAttr(multiply + ".outputX", condition + ".firstTerm")
        cmds.setAttr(condition + ".operation", 2)  # greater than
        cmds.setAttr(condition + ".colorIfTrueR", 1)
        cmds.setAttr(condition + ".colorIfFalseR", 0)
        return condition + ".outColorR"

    def _ramp_plugs(self, settings, prefix):
        """Create the per-spring tip values of the ramped parameters.

        Args:
            settings (str): Settings control.
            prefix (str): Name prefix.

        Returns:
            dict: ``tips`` (multiplyDivide with the damping, elasticity
            and stiffness tip values in X, Y, Z), ``mass_tip`` and
            ``radius_tip`` (plugs). The tip radius is a parameter itself.
        """
        tips = cmds.createNode("multiplyDivide", name=prefix + "_sprg_tips")
        for (param, _), axis in zip(RAMPED_PARAMS, "XYZ"):
            cmds.connectAttr(_plug(settings, param), tips + ".input1" + axis)
            cmds.connectAttr(_plug(settings, param + TIP), tips + ".input2" + axis)
        mass_tip = cmds.createNode("multiplyDivide", name=prefix + "_sprg_massTip")
        cmds.connectAttr(_plug(settings, MASS), mass_tip + ".input1X")
        cmds.connectAttr(_plug(settings, MASS + TIP), mass_tip + ".input2X")
        return {
            "tips": tips,
            "mass_tip": mass_tip + ".outputX",
            "radius_tip": _plug(settings, TIP_RADIUS),
        }

    def _attach(self, section, bone, end, target, context):
        """Create and connect the boneDynamicsNode of a section.

        Args:
            section (chain.Section): The section.
            bone (str): Sim bone joint.
            end (str): Sim end joint.
            target (str): Target bone joint.
            context (dict): ``settings``, ``solver``, ``offset``,
                ``enable``, ``tips``, ``mass_tip`` and ``radius_tip`` of the
                spring, and
                ``count``, the number of sections attached so far.
        """
        settings = context["settings"]
        name = bone.split("|")[-1].replace("_jnt", "_bdn")
        node = cmds.createNode(NODE_TYPE, name=name)
        connections = (
            ("time1.outTime", "time"),
            (bone + ".translate", "boneTranslate"),
            (bone + ".parentMatrix[0]", "boneParentMatrix"),
            (bone + ".parentInverseMatrix[0]", "boneParentInverseMatrix"),
            (bone + ".jointOrient", "boneJointOrient"),
            (end + ".translate", "endTranslate"),
            (bone + ".scale", "boneScale"),
            (bone + ".inverseScale", "boneInverseScale"),
            (end + ".scale", "endScale"),
            (target + ".rotate", "rotationOffset"),
            (context["enable"], "enable"),
            (_plug(settings, WIND_SCALE), "additionalForceScale"),
        )
        for source, destination in connections:
            cmds.connectAttr(source, _plug(node, destination), force=True)
        cmds.connectAttr(_plug(node, "outputRotate"), bone + ".rotate", force=True)
        solver.connect(context["solver"], node)
        if context["offset"]:
            cmds.connectAttr(
                context["offset"] + ".worldMatrix[0]", _plug(node, "offsetMatrix")
            )
        for param, attr in DIRECT_PARAMS:
            cmds.connectAttr(_plug(settings, param), _plug(node, attr))

        # ramps: lerp(value, value * tip, ratio), the products per spring
        ramp = cmds.createNode("blendColors", name=name + "_ramp")
        cmds.setAttr(ramp + ".blender", section.ratio)
        for (param, attr), channel, axis in zip(RAMPED_PARAMS, "RGB", "XYZ"):
            cmds.connectAttr(
                context["tips"] + ".output" + axis, ramp + ".color1" + channel
            )
            cmds.connectAttr(_plug(settings, param), ramp + ".color2" + channel)
            cmds.connectAttr(ramp + ".output" + channel, _plug(node, attr))
        # turbulence seed: seed + section index when seeded per bone, so
        # the bones (and branches) do not move in unison
        context["count"] += 1
        seed = cmds.createNode("blendWeighted", name=name + "_turbSeed")
        cmds.connectAttr(_plug(settings, TURBULENCE_SEED), seed + ".input[0]")
        cmds.setAttr(seed + ".weight[0]", 1.0)
        cmds.connectAttr(_plug(settings, TURBULENCE_SEED_PER_BONE), seed + ".input[1]")
        cmds.setAttr(seed + ".weight[1]", context["count"])
        cmds.connectAttr(seed + ".output", _plug(node, "turbulenceSeed"))

        # single values: lerp(value, value * tip, ratio)
        for suffix, param, tip, ratio, attr in (
            ("_massRamp", MASS, "mass_tip", section.ratio, "mass"),
            (
                RADIUS_RAMPS["rootRadius"],
                RADIUS,
                "radius_tip",
                section.ratio,
                "rootRadius",
            ),
            (RADIUS_RAMPS["radius"], RADIUS, "radius_tip", section.end_ratio, "radius"),
        ):
            lerp = cmds.createNode("blendTwoAttr", name=name + suffix)
            cmds.setAttr(lerp + ".attributesBlender", ratio)
            cmds.connectAttr(_plug(settings, param), lerp + ".input[0]")
            cmds.connectAttr(context[tip], lerp + ".input[1]")
            cmds.connectAttr(lerp + ".output", _plug(node, attr))

    def sections(self, spring):
        """Return the simulated sections of a spring, with their ramp ratios.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            list: ``(bone joint, end joint, ratio, end ratio)`` tuples, the
            ratios going from 0 at the root to 1 at the tips.
        """
        result = []
        for node in nodes_of_type(spring, NODE_TYPE):
            # the radius ramps hold the section ratios, see _attach
            bone, end, root_ramp, end_ramp = (
                cmds.listConnections(_plug(node, attr), source=True, destination=False)[
                    0
                ]
                for attr in ("boneTranslate", "endTranslate", "rootRadius", "radius")
            )
            result.append(
                (
                    bone,
                    end,
                    cmds.getAttr(root_ramp + ".attributesBlender"),
                    cmds.getAttr(end_ramp + ".attributesBlender"),
                )
            )
        return result

    # target pose ------------------------------------------------------------

    def target_mode(self, spring):
        """Return the target pose mode of a spring.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            str: One of :data:`TARGET_MODES`.
        """
        return attribute.get_string_attr(
            spring.node, TARGET_MODE_ATTR, TARGET_ANIMATION
        )

    def poses(self, spring):
        """Return the pose holders of a spring, in control order.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            list: Pose holder names.
        """
        return attribute.get_message_inputs(spring.node, POSES_ATTR)

    def roots(self, spring):
        """Return the spring roots of a spring, in control order.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            list: Spring root names.
        """
        return attribute.get_message_inputs(spring.node, ROOTS_ATTR)

    def sim_joint(self, control):
        """Return the simulated joint driving a spring control.

        The control's parent constraint blends its target joints (first
        half) and its sim joints (second half), see :func:`proxy.build`.

        Args:
            control (str): Control of a Bone Dynamics spring.

        Returns:
            str: The sim joint long name, or None when the control is not
            driven by a Bone Dynamics spring.
        """
        for constraint in (
            cmds.listRelatives(control, type="parentConstraint", fullPath=True) or []
        ):
            targets = cmds.parentConstraint(constraint, query=True, targetList=True)
            sims = cmds.ls(targets[len(targets) // 2 :], long=True)
            spring = registry.spring_from_node(sims[0]) if sims else None
            if spring and spring.backend == self.name:
                return sims[0]
        return None

    def set_target_mode(self, springs, mode, external=None):
        """Set the target pose mode of springs, in one undo chunk.

        Args:
            springs (list): :class:`registry.Spring` records.
            mode (str): One of :data:`TARGET_MODES`.
            external (list, optional): For ``external``: the nodes whose
                rotation drives the target pose, in control order.

        Raises:
            ValueError: If the mode is unknown, or an external chain does
                not have one node per control. Nothing is changed then.
        """
        if mode not in TARGET_MODES:
            raise ValueError("Unknown target mode: {}".format(mode))
        poses = {spring: self.poses(spring) for spring in springs}
        if mode == TARGET_EXTERNAL:
            for spring_poses in poses.values():
                if len(external or ()) != len(spring_poses):
                    raise ValueError(
                        "The external chain needs {} nodes".format(len(spring_poses))
                    )
        with utils.undo_chunk("springManagerTargetMode"):
            for spring in springs:
                weight = _plug(spring.node, POSE_WEIGHT_ATTR)
                attribute.disconnect_plug_inputs(weight)
                for pose in poses[spring]:
                    attribute.disconnect_plug_inputs(
                        pose + ".rotate",
                        keep=lambda source: anim_utils.is_anim_source(
                            source.split(".")[0]
                        ),
                    )
                if mode == TARGET_ANIMATION:
                    cmds.setAttr(weight, 0)
                elif mode == TARGET_BLEND_MODE:
                    cmds.connectAttr(_plug(spring.settings_node, TARGET_BLEND), weight)
                else:
                    cmds.setAttr(weight, 1)
                if mode == TARGET_EXTERNAL:
                    for node, pose in zip(external, poses[spring]):
                        cmds.connectAttr(node + ".rotate", pose + ".rotate", force=True)
                self._show_pose_controls(spring, poses[spring], mode == TARGET_CONTROLS)
                attribute.set_string_attr(spring.node, TARGET_MODE_ATTR, mode)

    def capture_pose(self, springs):
        """Store the current animated pose as the target pose.

        Pose holders driven by a connection or keyed are left as is.

        Args:
            springs (list): :class:`registry.Spring` records.
        """
        with utils.undo_chunk("springManagerCapturePose"):
            for spring in springs:
                for root, pose in zip(self.roots(spring), self.poses(spring)):
                    if attribute.has_input(pose + ".rotate"):
                        continue
                    for axis in "XYZ":
                        plug = pose + ".rotate" + axis
                        if not attribute.has_input(plug):
                            cmds.setAttr(plug, cmds.getAttr(root + ".rotate" + axis))

    def _show_pose_controls(self, spring, poses, visible):
        """Show the pose holders as keyable controls, or hide them.

        Args:
            spring (registry.Spring): The spring.
            poses (list): Its pose holders.
            visible (bool): Show the pose controls.
        """
        for pose in poses:
            shapes = cmds.listRelatives(pose, shapes=True, fullPath=True) or []
            if visible and not shapes:
                circle = cmds.circle(
                    normal=(1, 0, 0), constructionHistory=False, name="tmpPoseShape"
                )[0]
                shape = cmds.listRelatives(circle, shapes=True, fullPath=True)[0]
                shape = cmds.parent(shape, pose, shape=True, relative=True)[0]
                cmds.delete(circle)
                cmds.setAttr(shape + ".overrideEnabled", True)
                cmds.setAttr(shape + ".overrideRGBColors", True)
                cmds.setAttr(shape + ".overrideColorRGB", 0.4, 0.9, 1.0)
                registry.add_members(spring.node, [shape])
                shapes = [shape]
            for shape in shapes:
                cmds.setAttr(shape + ".visibility", visible)
            for axis in "XYZ":
                cmds.setAttr(pose + ".rotate" + axis, keyable=visible)

    # wind -------------------------------------------------------------------

    def create_wind(self, name=WIND_NAME):
        """Create a wind controller: an arrow, blowing along its +Z axis.

        Args:
            name (str, optional): Controller name.

        Returns:
            str: The wind controller transform.
        """
        with utils.undo_chunk("springManagerCreateWind"):
            curve = cmds.curve(
                degree=1,
                point=[(0, 0, 0), (0, 0, 10), (-1.5, 0, 7), (0, 0, 10), (1.5, 0, 7)],
                name=name,
            )
            cmds.addAttr(
                curve,
                longName=WIND_STRENGTH,
                attributeType="double",
                minValue=0,
                defaultValue=100,
                keyable=True,
            )
            vector = cmds.createNode("vectorProduct", name=curve + "_vector")
            cmds.setAttr(vector + ".operation", 3)
            cmds.setAttr(vector + ".input1", 0, 0, 1, type="double3")
            cmds.setAttr(vector + ".normalizeOutput", True)
            cmds.connectAttr(curve + ".worldMatrix[0]", vector + ".matrix")
            network = registry.create_network(
                curve + "_net", self.name, [], None, kind=constants.KIND_WIND
            )
            _add_message(network, WIND_CONTROLLER_ATTR, curve)
            _add_message(network, WIND_VECTOR_ATTR, vector)
            # owned by the wind: kept when springs using it are deleted
            registry.add_members(network, [vector])
        return curve

    def winds(self):
        """Return the wind controllers of the scene.

        Returns:
            list: Wind controller names.
        """
        controllers = []
        for network in registry.list_shared(constants.KIND_WIND, self.name):
            controllers.extend(
                attribute.get_message_inputs(network, WIND_CONTROLLER_ATTR)
            )
        return controllers

    def _wind_network(self, wind):
        """Return the shared network of a wind controller.

        Args:
            wind (str): Wind controller.

        Returns:
            str: The wind network node.

        Raises:
            ValueError: If the node is not a spring wind controller.
        """
        for network in (
            cmds.listConnections(
                wind + ".message", source=False, destination=True, type="network"
            )
            or []
        ):
            if registry.node_kind(network) == constants.KIND_WIND:
                return network
        raise ValueError("{} is not a spring wind controller".format(wind))

    def wind_of(self, spring):
        """Return the wind controller of a spring.

        Args:
            spring (registry.Spring): The spring.

        Returns:
            str: The wind controller, or None.
        """
        for network in registry.shared_of(spring, constants.KIND_WIND):
            controllers = attribute.get_message_inputs(network, WIND_CONTROLLER_ATTR)
            if controllers:
                return controllers[0]
        return None

    def connect_wind(self, springs, wind):
        """Drive the additional force of springs with a wind controller.

        A spring has one wind: its previous wind is disconnected.

        Args:
            springs (list): :class:`registry.Spring` records.
            wind (str): Wind controller from :meth:`create_wind`.
        """
        network = self._wind_network(wind)
        with utils.undo_chunk("springManagerConnectWind"):
            registry.assign(network, springs)

    def disconnect_wind(self, springs):
        """Remove the wind from springs.

        Args:
            springs (list): :class:`registry.Spring` records.
        """
        with utils.undo_chunk("springManagerDisconnectWind"):
            for spring in springs:
                for network in registry.shared_of(spring, constants.KIND_WIND):
                    registry.unassign(network, [spring])

    # shared nodes -------------------------------------------------------------

    def bone_node(self, joint):
        """Return the boneDynamicsNode simulating a sim joint.

        Args:
            joint (str): Sim joint.

        Returns:
            str: The node, or None when the joint is not a simulated bone.
        """
        for plug in (
            cmds.listConnections(
                joint + ".translate", source=False, destination=True, plugs=True
            )
            or []
        ):
            node, attr = plug.split(".", 1)
            if attr == "boneTranslate" and cmds.nodeType(node) == NODE_TYPE:
                return node
        return None

    def link_collider(self, network):
        """Let a collider on a sim joint set the volume of its bone.

        A capsule drives its bone's ``rootRadius`` (from radiusB, the start)
        and ``radius`` (from radiusA, the end), and turns Bone As Capsule on.
        A sphere drives both, unless a capsule already does. Each section
        then collides with the volume other chains collide against, fitted
        per section. Bones without a collider keep the spring Root / Tip
        Radius gradient.

        Args:
            network (str): Collider network.

        Returns:
            bool: True when the collider drives a bone.
        """
        kind_type = colliders.collider_type(network)
        driver_node = colliders.driver(network)
        node = self.bone_node(driver_node) if driver_node else None
        if not node or kind_type not in (colliders.SPHERE, colliders.CAPSULE):
            return False
        shape = colliders.dimension_node(network)
        if kind_type == colliders.CAPSULE:
            links = (("radiusB", "rootRadius"), ("radiusA", "radius"))
            spring = registry.spring_from_node(node)
            if spring:
                self.set_params([spring], {BONE_CAPSULE: True})
        else:
            if cmds.listConnections(
                _plug(node, "rootRadius"),
                source=True,
                destination=False,
                type=colliders.SHAPE_TYPES[colliders.CAPSULE],
            ):
                return False
            links = (("radius", "rootRadius"), ("radius", "radius"))
        for source, destination in links:
            cmds.connectAttr(_plug(shape, source), _plug(node, destination), force=True)
        return True

    def unlink_collider(self, network):
        """Give the bones driven by a collider back to the spring gradient.

        Args:
            network (str): Collider network.
        """
        shape = colliders.dimension_node(network)
        if not shape:
            return
        for plug in (
            cmds.listConnections(
                shape, source=False, destination=True, plugs=True, type=NODE_TYPE
            )
            or []
        ):
            node, attr = plug.split(".", 1)
            ramps = cmds.ls(node + RADIUS_RAMPS.get(attr, ""), type="blendTwoAttr")
            if attr in RADIUS_RAMPS and ramps:
                cmds.connectAttr(ramps[0] + ".output", plug, force=True)

    def shared_changed(self, spring, kind):
        if kind == constants.KIND_WIND:
            self._disconnect_wind_nodes(spring)
            for network in registry.shared_of(spring, kind):
                self._connect_wind_nodes(spring, network)
        elif kind == constants.KIND_COLLIDER:
            self._connect_colliders(spring)

    def _connect_colliders(self, spring):
        """Rewire the collider inputs of a spring's nodes.

        Every collider array of the nodes is cleared, then refilled from the
        assigned colliders in order, so the arrays have no gaps.

        Args:
            spring (registry.Spring): The spring.
        """
        nodes = nodes_of_type(spring, NODE_TYPE)
        for node in nodes:
            for array in COLLIDER_ARRAYS:
                attribute.clear_multi(_plug(node, array))
        counters = dict.fromkeys(colliders.TYPES, 0)
        for network in colliders.usable(
            registry.shared_of(spring, constants.KIND_COLLIDER)
        ):
            kind_type = colliders.collider_type(network)
            # dimensions holder (sphere, capsule) or the mesh shape
            shape = colliders.dimension_node(network) or colliders.collider_shape(
                network
            )
            if kind_type not in counters or (
                kind_type != colliders.PLANE and not shape
            ):
                continue
            index = counters[kind_type]
            counters[kind_type] += 1
            matrix = colliders.collider_transform(network) + ".worldMatrix[0]"
            if kind_type == colliders.SPHERE:
                links = (
                    (matrix, "sphereCollider[{}].sphereColMatrix"),
                    (shape + ".radius", "sphereCollider[{}].sphereColRadius"),
                )
            elif kind_type == colliders.CAPSULE:
                prefix = "capsuleColliderInput[{}]."
                links = (
                    (matrix, prefix + "capsuleColliderMatrix"),
                    (shape + ".height", prefix + "capsuleColliderHeight"),
                    (shape + ".radiusA", prefix + "capsuleColliderRadiusA"),
                    (shape + ".radiusB", prefix + "capsuleColliderRadiusB"),
                )
            elif kind_type == colliders.PLANE:
                links = ((matrix, "infinitePlaneCollider[{}].infinitePlaneColMatrix"),)
            else:
                links = ((shape + ".worldMesh[0]", "meshCollider[{}]"),)
            for node in nodes:
                for source, destination in links:
                    cmds.connectAttr(source, _plug(node, destination.format(index)))

    def _connect_wind_nodes(self, spring, network):
        """Wire a wind network into the nodes of a spring.

        Args:
            spring (registry.Spring): The spring.
            network (str): Wind network.
        """
        wind = attribute.get_message_inputs(network, WIND_CONTROLLER_ATTR)[0]
        vector = attribute.get_message_inputs(network, WIND_VECTOR_ATTR)[0]
        settings = spring.settings_node
        with utils.capture_created_nodes() as created:
            scale = cmds.createNode(
                "multiplyDivide",
                name=node_remap.flat_name(settings) + "_sprg_wind",
            )
        cmds.connectAttr(_plug(wind, WIND_STRENGTH), scale + ".input1X")
        cmds.connectAttr(_plug(settings, WIND_SCALE), scale + ".input2X")
        for node in nodes_of_type(spring, NODE_TYPE):
            cmds.connectAttr(
                vector + ".output", _plug(node, "additionalForce"), force=True
            )
            cmds.connectAttr(
                scale + ".outputX", _plug(node, "additionalForceScale"), force=True
            )
        cmds.connectAttr(
            scale + ".message", _plug(spring.node, WIND_SCALE_ATTR), force=True
        )
        registry.add_members(spring.node, created)

    def _disconnect_wind_nodes(self, spring):
        """Remove the wind wiring of a spring's nodes.

        Args:
            spring (registry.Spring): The spring.
        """
        settings = spring.settings_node
        for node in nodes_of_type(spring, NODE_TYPE):
            force = _plug(node, "additionalForce")
            attribute.disconnect_plug_inputs(force)
            cmds.setAttr(force, 0, 0, 0, type="double3")
            cmds.connectAttr(
                _plug(settings, WIND_SCALE),
                _plug(node, "additionalForceScale"),
                force=True,
            )
        scale = attribute.get_message_inputs(spring.node, WIND_SCALE_ATTR)
        if scale:
            cmds.delete(scale)

    # visualizer ------------------------------------------------------------

    def set_visualizer(self, springs, visible):
        """Create or remove the boneDynamicsVisualizer shapes of springs.

        Args:
            springs (list): :class:`registry.Spring` records.
            visible (bool): True to create them, False to delete them.
        """
        with utils.undo_chunk("springManagerVisualizer"):
            for spring in springs:
                members = spring.members
                existing = nodes_of_type(spring, VISUALIZER_TYPE, members)
                if not visible:
                    if existing:
                        cmds.delete(
                            cmds.listRelatives(existing, parent=True, fullPath=True)
                        )
                    continue
                if existing:
                    continue
                groups = attribute.get_message_inputs(spring.node, GROUP_ATTR)
                group = groups[0] if groups else None
                with utils.capture_created_nodes() as created:
                    for node in nodes_of_type(spring, NODE_TYPE, members):
                        shape = cmds.createNode(
                            VISUALIZER_TYPE, name=node + "_visShape"
                        )
                        for source, destination in VISUALIZER_CONNECTIONS:
                            cmds.connectAttr(
                                _plug(node, source), _plug(shape, destination)
                            )
                        cmds.setAttr(shape + ".overrideEnabled", True)
                        cmds.setAttr(shape + ".overrideDisplayType", 2)
                        # tidy outliner: the shape draws at the bones anyway
                        if group:
                            cmds.parent(
                                cmds.listRelatives(shape, parent=True)[0], group
                            )
                registry.add_members(spring.node, created)

    # delete -----------------------------------------------------------------

    def detach(self, spring):
        members = set(cmds.ls(spring.members, long=True) or [])
        constraints = [
            constraint
            for control in spring.controls
            for constraint in cmds.listRelatives(
                control, type="parentConstraint", fullPath=True
            )
            or []
            if constraint in members
        ]
        if constraints:
            cmds.delete(constraints)

    def delete(self, spring, transfer_animation=True):
        network = spring.node
        controls = spring.controls
        settings = spring.settings_node
        roots = self.roots(spring)
        if spring.state == constants.STATE_BAKED:
            transfer_animation = False
        self.detach(spring)
        if transfer_animation:
            for control, root in zip(controls, roots):
                anim_utils.move_animation_curves(root, control, constants.MOVED_ATTRS)
        restore_rest_values(network)
        # keeps the shared solver and wind
        registry.delete_members(network)
        if settings:
            remove_settings(settings, self.param_specs())
        # deleting the members can already remove the network
        if cmds.objExists(network):
            cmds.delete(network)

    # parameters -----------------------------------------------------------

    def set_enabled(self, springs, enabled):
        self.set_params(springs, {INTENSITY: float(enabled)})

    # bake -----------------------------------------------------------------

    def bake_channels(self, spring):
        return {
            control: attribute.get_unlocked_channels(control, constants.MOVED_ATTRS)
            for control in spring.controls
        }

    def prepare_bake(self, springs, start):
        self._saved_start = solver.get_start_frame()
        solver.set_start_frame(start)

    def finish_bake(self, springs):
        if self._saved_start is not None:
            solver.set_start_frame(self._saved_start)
        self._saved_start = None

    # presets --------------------------------------------------------------

    def get_solver_settings(self):
        return solver.get_settings()

    def set_solver_settings(self, settings):
        if settings:
            solver.set_settings(settings)

    def to_preset(self, spring):
        network = spring.node
        tree = json.loads(attribute.get_string_attr(network, TREE_ATTR) or "{}")
        offset = attribute.get_message_inputs(network, OFFSET_ATTR)
        return {
            "backend": self.name,
            "controls": spring.controls,
            "options": {
                "tree": chain.rename_tree_data(tree, node_remap.short_name),
                "branch_policy": attribute.get_string_attr(
                    network, POLICY_ATTR, chain.KINEMATIC
                ),
                "primary": cmds.getAttr(_plug(network, PRIMARY_ATTR)),
                "tip_length": cmds.getAttr(_plug(network, TIP_LENGTH_ATTR)),
                "target_mode": self.target_mode(spring),
                "offset": node_remap.short_name(offset[0]) if offset else None,
            },
            "params": self.get_params(spring),
        }

    def from_preset(self, entry, controls):
        params = entry.get("params") or {}
        handled, spring = self.update_existing(controls[0], params)
        if handled:
            return spring
        options = dict(entry.get("options") or {})
        rename = dict(
            zip(
                [node_remap.short_name(name) for name in entry.get("controls") or []],
                controls,
            )
        )
        options["tree"] = chain.rename_tree_data(
            options.get("tree"), lambda name: rename.get(name, name)
        )
        if options.get("offset"):
            namespace = node_remap.get_namespace(controls[0])
            options["offset"] = node_remap.add_namespace(options["offset"], namespace)
            if not cmds.objExists(options["offset"]):
                options["offset"] = AUTO_OFFSET
        springs = self.create([controls[0]], params, options)
        return springs[0] if springs else None
