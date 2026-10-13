"""Lips rig builder.

Builds the Lips Rigger rig in phases that line up with the Shifter build
steps:

1. :meth:`LipsBuilder.build_objects`: curves, controls, joint drivers.
2. :meth:`LipsBuilder.build_attributes`: jaw follow, zipper, roll and
   visibility attributes.
3. :meth:`LipsBuilder.build_operators`: curve operators, wires, zipper and
   roll networks.
4. :meth:`LipsBuilder.connect_refs`: the upper (head) and lower (jaw)
   references the lips follow.
5. :meth:`LipsBuilder.build_skin`: optional topological autoskin, once the
   joints exist.

The controls drive two 7 point control curves, which drive rope curves with
wires. The joints slide on zipper curves: copies of the ropes that blend to
a zip curve between both lips for the lips zipper. Controls, joints and named
nodes are created through a :class:`mgear.core.facial.backend.BaseBackend`.
"""

import math

from maya import cmds

import mgear.pymaya as pm
from mgear.pymaya import datatypes

from mgear.core import applyop
from mgear.core import attribute
from mgear.core import curve
from mgear.core import node
from mgear.core import transform
from mgear.core import vector

from ._build_base import MAIN_KEYABLE
from ._build_base import FacialBuilder
from ._build_base import cv_points
from ._build_base import select_joint_indices
from ._build_base import uniform_curve
from ._build_base import xyz

HALF_PI = math.pi * 0.5

LIP_SECONDARY_KEYABLE = ("tx", "ty", "tz", "rx", "ry", "rz")

# mirror pose flags of the center controls: tx, ry and rz invert
CENTER_MIRROR_CONF = (1, 0, 0, 0, 1, 1, 0, 0, 0)

# control curve points
CONTROL_POINTS = 7

# (name, side, role) of the upper control curve points, right to left. The
# lower curve shares the corners.
UPPER_CONTROLS = (
    ("corner_R", "R", "main"),
    ("upOuter_R", "R", "secondary"),
    ("upInner_R", "R", "secondary"),
    ("upper", "C", "main"),
    ("upInner_L", "L", "secondary"),
    ("upOuter_L", "L", "secondary"),
    ("corner_L", "L", "main"),
)
LOWER_CONTROLS = (
    None,
    ("lowOuter_R", "R", "secondary"),
    ("lowInner_R", "R", "secondary"),
    ("lower", "C", "main"),
    ("lowInner_L", "L", "secondary"),
    ("lowOuter_L", "L", "secondary"),
    None,
)

# parent control of each secondary control, and the two controls its
# position blends between with the first one's weight (Lips Rigger 1.0)
SECONDARY_LAYOUT = (
    ("upOuter_R", "corner_R", ("corner_R", "upper", 0.75)),
    ("upInner_R", "upper", ("corner_R", "upper", 0.25)),
    ("upInner_L", "upper", ("upper", "corner_L", 0.75)),
    ("upOuter_L", "corner_L", ("upper", "corner_L", 0.25)),
    ("lowOuter_R", "corner_R", ("corner_R", "lower", 0.75)),
    ("lowInner_R", "lower", ("corner_R", "lower", 0.25)),
    ("lowInner_L", "lower", ("lower", "corner_L", 0.75)),
    ("lowOuter_L", "corner_L", ("lower", "corner_L", 0.25)),
)

# control shape sizes, as a part of the mouth width (Lips Rigger 1.0)
MAIN_SIZE = 0.15
SECONDARY_SIZE = 0.09

CORNERS = ("corner_R", "corner_L")

WIRE_DROPOFF = 1000

# squash and stretch scale limits
SQUASH_RANGE = (0.25, 4.0)


def roll_weight(lateral, half_width, falloff=True):
    """Get how much a lip joint rolls, from its lateral position.

    Args:
        lateral (float): Lateral coordinate of the joint in the mouth frame.
        half_width (float): Half the mouth width.
        falloff (bool, optional): Fade to 0 at the corners, smoothly.

    Returns:
        float: 1 at the center, 0 at the corners.
    """
    if not falloff:
        return 1.0
    d = min(abs(lateral) / (half_width or 1.0), 1.0)
    return 1.0 - d * d * (3.0 - 2.0 * d)


def zipper_distances(count):
    """Get the zip distance of each zipper curve point from its corner.

    Args:
        count (int): Curve points, from the right to the left corner.

    Returns:
        list: (side, distance) per point. side is "R", "L" or "C" (center
            point, zipped by both sides). distance goes from 0 at the
            corner to 1 at the center.
    """
    last = float(count - 1)
    result = []
    for j in range(count):
        t = j / last
        if abs(t - 0.5) < 1e-6:
            result.append(("C", 1.0))
        elif t < 0.5:
            result.append(("R", t * 2.0))
        else:
            result.append(("L", (1.0 - t) * 2.0))
    return result


class LipsBuilder(FacialBuilder):
    """Build a lips rig from solved geometry.

    Args:
        settings (dict): Coerced lips settings.
        geometry (LipsGeometry): Solved geometry.
        backend (BaseBackend): Backend creating the nodes.
    """

    def __init__(self, settings, geometry, backend):
        super(LipsBuilder, self).__init__(settings, geometry, backend)

        # curves
        self.up_ctl_crv = None
        self.low_ctl_crv = None
        self.up_upv_ctl_crv = None
        self.low_upv_ctl_crv = None
        self.up_rope = None
        self.low_rope = None
        self.up_rope_upv = None
        self.low_rope_upv = None
        # {(lip, suffix): curve}: where each lip zips to, "Upv" suffix for
        # the up vector curves
        self.zip_curves = {}
        self.up_zipper = None
        self.low_zipper = None
        self.up_zipper_upv = None
        self.low_zipper_upv = None

        # controls by name
        self.controls = {}
        self.npos = {}
        self.upvs = {}

        # joints
        self.drivers_root = None
        self.joint_seeds = []
        self.up_rolls = []
        self.low_rolls = []

        # attributes
        self.jaw_follow = {}
        self.zipper = {}
        self.up_roll = None
        self.low_roll = None
        self.zipper_height = None
        self.squash_stretch = {}
        self.secondary_vis = None

    @property
    def secondary_controls(self):
        """list: The 8 secondary controls."""
        return [self.controls[name] for name, _, _ in SECONDARY_LAYOUT]

    # ------------------------------------------------------------------
    # phase 1

    def build_objects(self):
        """Create the curves, controls and joint drivers."""
        self._build_curves()
        self._build_controls()
        self._build_joint_drivers()

    def _build_curves(self):
        b = self.backend
        g = self.geometry
        s = self.settings
        root = b.setup_root
        normal = g.frame["normal"]
        offset = s["upvOffset"]

        def forward(points):
            return [tuple(p[i] + normal[i] * offset for i in range(3)) for p in points]

        curves = {}
        for prefix, points in (
            ("up", g.upper_curve_points),
            ("low", g.lower_curve_points),
        ):
            # the lip curve passes through the lip points: the control and
            # rope curves sample it, then it goes
            lip = b.add_curve(root, prefix + "Lip_crv", points, edit_points=True)
            ctl_points = [
                xyz(p) for p in curve.getParamPositionsOnCurve(lip, CONTROL_POINTS)
            ]
            rope_points = [
                xyz(p) for p in curve.getParamPositionsOnCurve(lip, s["ropeCount"])
            ]
            pm.delete(lip)
            rope = b.add_curve(root, prefix + "Rope_crv", rope_points, edit_points=True)
            rope_upv = b.add_curve(
                root, prefix + "RopeUpv_crv", forward(rope_points), edit_points=True
            )
            for crv in (rope, rope_upv):
                uniform_curve(crv, s["ropeCount"])
            curves[prefix] = (
                b.add_curve(root, prefix + "Ctl_crv", ctl_points),
                b.add_curve(root, prefix + "CtlUpv_crv", forward(ctl_points)),
                rope,
                rope_upv,
                b.add_curve(root, prefix + "Zipper_crv", cv_points(rope)),
                b.add_curve(root, prefix + "ZipperUpv_crv", cv_points(rope_upv)),
            )
        (
            self.up_ctl_crv,
            self.up_upv_ctl_crv,
            self.up_rope,
            self.up_rope_upv,
            self.up_zipper,
            self.up_zipper_upv,
        ) = curves["up"]
        (
            self.low_ctl_crv,
            self.low_upv_ctl_crv,
            self.low_rope,
            self.low_rope_upv,
            self.low_zipper,
            self.low_zipper_upv,
        ) = curves["low"]
        for lip in ("up", "low"):
            for suffix, rope in (("", self.up_rope), ("Upv", self.up_rope_upv)):
                self.zip_curves[(lip, suffix)] = b.add_curve(
                    root, "{}Zip{}_crv".format(lip, suffix), cv_points(rope)
                )

    def _build_controls(self):
        b = self.backend
        g = self.geometry
        s = self.settings
        size = g.mouth_width * s["ctlSize"]
        po = datatypes.Vector(0, 0, g.control_offset)
        ro = datatypes.Vector(HALF_PI, 0, 0)
        # mirrored side controls mirror with the same values
        side_conf = None if s["mirrorBehavior"] else CENTER_MIRROR_CONF
        points = {
            "up": [xyz(p) for p in self.up_ctl_crv.getCVs(space="world")],
            "low": [xyz(p) for p in self.low_ctl_crv.getCVs(space="world")],
        }
        parents = {name: parent for name, parent, _ in SECONDARY_LAYOUT}
        # main controls first: the secondary ones go under them
        layout = []
        for key, controls in (("up", UPPER_CONTROLS), ("low", LOWER_CONTROLS)):
            for i, item in enumerate(controls):
                if item:
                    layout.append((item, points[key][i]))
        layout.sort(key=lambda entry: entry[0][2] != "main")
        for (name, side, role), point in layout:
            m = self._control_matrix(point, g.side_matrix(side))
            parent = self.controls.get(parents.get(name), b.root)
            npo = b.add_transform(parent, name + "_npo", m)
            main = role == "main"
            width = (MAIN_SIZE if main else SECONDARY_SIZE) * size
            ctl = b.add_ctl(
                npo,
                name,
                m,
                "square" if main else "circle",
                role,
                MAIN_KEYABLE if main else LIP_SECONDARY_KEYABLE,
                w=width,
                d=width,
                ro=ro,
                po=po,
                tag_parent=None if main else parent,
                mirror_conf=CENTER_MIRROR_CONF if side == "C" else side_conf,
            )
            upv = b.add_transform(ctl, name + "_upv", m)
            cmds.setAttr(str(upv) + ".tz", s["upvOffset"])
            self.npos[name] = npo
            self.controls[name] = ctl
            self.upvs[name] = upv

    def _curve_inputs(self, upper, nodes):
        """Get the control curve inputs of a lip, right to left."""
        layout = UPPER_CONTROLS if upper else LOWER_CONTROLS
        last = len(layout) - 1
        return [
            nodes[item[0] if item else CORNERS[i // last]]
            for i, item in enumerate(layout)
        ]

    def _build_joint_drivers(self):
        b = self.backend
        s = self.settings
        g = self.geometry
        rig_m = datatypes.Matrix(g.rig_matrix)
        self.drivers_root, root_scale = self._world_drivers_root()
        half_width = g.mouth_width * 0.5
        for zipper, rope, upv_zipper, vertices, points, prefix, parent, rolls in (
            (
                self.up_zipper,
                self.up_rope,
                self.up_zipper_upv,
                g.upper,
                g.upper_curve_points,
                "upLip",
                "head",
                self.up_rolls,
            ),
            (
                self.low_zipper,
                self.low_rope,
                self.low_zipper_upv,
                g.lower,
                g.lower_curve_points,
                "lowLip",
                "jaw",
                self.low_rolls,
            ),
        ):
            # the lower lip shares the corners with the upper lip
            picks = select_joint_indices(
                len(vertices),
                s["everyNVertex"],
                s["fixedJoints"],
                s["fixedJointsNumber"],
                skip_ends=prefix == "lowLip",
            )
            for point_index, joint_index in picks:
                position = points[point_index]
                u = curve.get_length_ratio_at_point(rope, position)
                upv = b.add_transform(
                    self.drivers_root, prefix + "Upv", rig_m, idx=joint_index
                )
                # the up vectors zip with the lips, so zipping doesn't roll
                path = applyop.pathCns(upv, upv_zipper, u=u)
                self._name_node(path, prefix + "Upv_motionPath", joint_index)
                driver = b.add_transform(
                    self.drivers_root, prefix + "Drv", rig_m, idx=joint_index
                )
                path = applyop.pathCns(driver, zipper, u=u, tangent=True)
                self._name_node(path, prefix + "_motionPath", joint_index)
                # X along the lip, Y to the up vector in front of the lip
                path.attr("worldUpType").set(1)
                path.attr("frontAxis").set(0)
                path.attr("upAxis").set(1)
                pm.connectAttr(upv.attr("worldMatrix[0]"), path.attr("worldUpMatrix"))
                pm.connectAttr(root_scale.attr("outputScale"), driver.attr("scale"))
                roll = b.add_transform(
                    driver,
                    prefix + "Roll",
                    transform.getTransform(driver),
                    idx=joint_index,
                )
                lateral = vector.to_frame_coordinates(position, g.frame)[0]
                rolls.append((roll, roll_weight(lateral, half_width, s["rollFalloff"])))
                handle = b.add_deform_joint(
                    roll, prefix + "_jnt", idx=joint_index, parent=parent
                )
                self.joint_seeds.append((handle, vertices[point_index]))

    # ------------------------------------------------------------------
    # phase 2

    def build_attributes(self, secondary_vis=None):
        """Add the jaw follow, zipper, roll and visibility attributes.

        Args:
            secondary_vis (Attribute, optional): Existing bool attribute
                showing the secondary controls, e.g. on a Shifter UI host.
                A ``secondaryVis`` attribute is added to the upper control
                when None.
        """
        s = self.settings
        for name in CORNERS:
            ctl = self.controls[name]
            self.jaw_follow[name] = attribute.addAttribute(
                ctl, "jawFollow", "float", s["jawFollow"], minValue=0, maxValue=1
            )
            self.zipper[name] = attribute.addAttribute(
                ctl, "zipper", "float", 0, minValue=0, maxValue=1
            )
        upper = self.controls["upper"]
        lower = self.controls["lower"]
        self.up_roll = attribute.addAttribute(
            upper, "roll", "float", 0, minValue=-90, maxValue=90
        )
        self.zipper_height = attribute.addAttribute(
            upper, "zipperHeight", "float", 0.5, minValue=0, maxValue=1
        )
        self.low_roll = attribute.addAttribute(
            lower, "roll", "float", 0, minValue=-90, maxValue=90
        )
        if s["squashStretch"]:
            for lip, ctl in (("up", upper), ("low", lower)):
                self.squash_stretch[lip] = attribute.addAttribute(
                    ctl, "squashStretch", "float", 1, minValue=0, maxValue=1
                )
        host, name = upper, "secondaryVis"
        if secondary_vis is not None:
            host, name = str(secondary_vis).split(".", 1)
        self.secondary_vis = attribute.hide_shapes(self.secondary_controls, name, host)

    # ------------------------------------------------------------------
    # phase 3

    def build_operators(self):
        """Create the curve operators, wires and the zipper and roll networks."""
        self._build_curve_network()
        self._blend_secondaries()
        self._build_zipper_network()
        self._build_roll_network()
        if self.squash_stretch:
            self._build_squash_network()

    def _build_curve_network(self):
        b = self.backend
        for upper, ctl_crv, upv_crv in (
            (True, self.up_ctl_crv, self.up_upv_ctl_crv),
            (False, self.low_ctl_crv, self.low_upv_ctl_crv),
        ):
            applyop.gear_curvecns_op(ctl_crv, self._curve_inputs(upper, self.controls))
            applyop.gear_curvecns_op(upv_crv, self._curve_inputs(upper, self.upvs))
        for crv, driver, name in (
            (self.up_rope, self.up_ctl_crv, "upRope_wire"),
            (self.low_rope, self.low_ctl_crv, "lowRope_wire"),
            (self.up_rope_upv, self.up_upv_ctl_crv, "upRopeUpv_wire"),
            (self.low_rope_upv, self.low_upv_ctl_crv, "lowRopeUpv_wire"),
        ):
            wire = cmds.wire(str(crv), wire=str(driver), name=b.name(name))[0]
            cmds.setAttr(wire + ".dropoffDistance[0]", WIRE_DROPOFF)

    def _blend_secondaries(self):
        for name, _, (first, second, weight) in SECONDARY_LAYOUT:
            applyop.matrix_blend_constraint(
                [self.controls[first], self.controls[second]],
                self.npos[name],
                weights=[weight, 1.0 - weight],
                channels="t",
                offset=True,
            )

    def _build_zipper_network(self):
        """Zip the lips: zipper curves blend to where both lips meet.

        The joints sit inside the lips, a thickness away from their surface.
        Each lip zips to the weighted average of its rope and the other rope
        moved by twice the thickness, so the lip surfaces meet instead of
        crossing. The joint up vector curves zip the same way, so the joints
        keep their orientation while zipping.
        """
        low_weight = self._create_node("reverse", "zipperHeight_reverse")
        pm.connectAttr(self.zipper_height, low_weight.attr("inputX"))
        both = self._create_node("condition", "zipperCenter_condition")
        both.attr("operation").set(2)
        for term, color, name in (
            ("firstTerm", "colorIfTrueR", "corner_L"),
            ("secondTerm", "colorIfFalseR", "corner_R"),
        ):
            pm.connectAttr(self.zipper[name], both.attr(term))
            pm.connectAttr(self.zipper[name], both.attr(color))
        sources = {
            "R": self.zipper["corner_R"],
            "L": self.zipper["corner_L"],
            "C": both.attr("outColorR"),
        }

        # the curves are in the build world space: the lips up axis
        # offset between the joints of both lips at contact
        gap = 2.0 * self.geometry.thickness
        up = self.geometry.frame["up"]

        blend_shapes = []
        for suffix, ropes, zippers in (
            (
                "",
                (self.up_rope, self.low_rope),
                (self.up_zipper, self.low_zipper),
            ),
            (
                "Upv",
                (self.up_rope_upv, self.low_rope_upv),
                (self.up_zipper_upv, self.low_zipper_upv),
            ),
        ):
            plugs = [rope.getShape().attr("local") for rope in ropes]
            for i, (lip, zipper) in enumerate(zip(("up", "low"), zippers)):
                # the other rope, moved to where this lip's joints meet it
                other = 1 - i
                sign = 1.0 if lip == "up" else -1.0
                shift = self._create_node(
                    "transformGeometry", "{}Zip{}_shift".format(lip, suffix)
                )
                offset = [v * gap * sign for v in up]
                cmds.setAttr(
                    str(shift) + ".transform",
                    [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0] + offset + [1],
                    type="matrix",
                )
                pm.connectAttr(plugs[other], shift.attr("inputGeometry"))
                inputs = [plugs[0], plugs[1]]
                inputs[other] = shift.attr("outputGeometry")
                avg = self._create_node(
                    "avgCurves", "{}Zip{}_avgCurves".format(lip, suffix)
                )
                avg.attr("automaticWeight").set(False)
                avg.attr("normalizeWeights").set(False)
                pm.connectAttr(inputs[0], avg.attr("inputCurve1"))
                pm.connectAttr(inputs[1], avg.attr("inputCurve2"))
                pm.connectAttr(self.zipper_height, avg.attr("weight1"))
                pm.connectAttr(low_weight.attr("outputX"), avg.attr("weight2"))
                zip_crv = self.zip_curves[(lip, suffix)]
                pm.connectAttr(
                    avg.attr("outputCurve"), zip_crv.getShape().attr("create")
                )
                pm.connectAttr(
                    ropes[i].getShape().attr("local"),
                    zipper.getShape().attr("create"),
                )
                name = "{}Zipper{}_blendShape".format(lip, suffix)
                blend = cmds.blendShape(
                    str(zip_crv), str(zipper), name=self.backend.name(name)
                )[0]
                cmds.setAttr(blend + ".weight[0]", 1)
                blend_shapes.append(blend)

        falloff = self.settings["zipperFalloff"]
        count = len(self.up_zipper.getCVs())
        for j, (side, distance) in enumerate(zipper_distances(count)):
            start = distance * (1.0 - falloff)
            remap = self._smooth_remap(
                "zipper_remap",
                sources[side],
                input_min=start,
                input_max=start + falloff,
                idx=j,
            )
            for blend in blend_shapes:
                pm.connectAttr(
                    remap.attr("outValue"),
                    "{}.inputTarget[0].inputTargetGroup[0].targetWeights[{}]".format(
                        blend, j
                    ),
                )

    def _build_roll_network(self):
        """Roll the lip joints around the lips, out with positive values."""
        # the joint X axis runs along the lip and Z points down: the upper
        # lip rolls out with a negative X rotation, the lower one positive
        for attr, rolls, sign, prefix in (
            (self.up_roll, self.up_rolls, -1.0, "upRoll"),
            (self.low_roll, self.low_rolls, 1.0, "lowRoll"),
        ):
            for i, (roll, weight) in enumerate(rolls):
                mult = node.createMulDL()
                self._name_node(mult, prefix + "_mult", i)
                pm.connectAttr(attr, mult.attr("input1"))
                mult.attr("input2").set(weight * sign)
                pm.connectAttr(mult.attr("output"), roll.attr("rx"))

    def _build_squash_network(self):
        """Scale the lip joints across the lip by the lip stretch.

        The joints scale on their front (Y) and down (Z) axes by
        1 / sqrt(rope length / rest length), keeping the lip cross section
        area. The squashStretch attribute blends it from none (0) to full
        (1). The lengths are local: the global scale doesn't count.
        """
        for lip, rope, rolls in (
            ("up", self.up_rope, self.up_rolls),
            ("low", self.low_rope, self.low_rolls),
        ):
            info = node.createCurveInfoNode(rope)
            self._name_node(info, lip + "Squash_curveInfo")
            rest = info.attr("arcLength").get()
            ratio = self._create_node("multiplyDivide", lip + "Squash_ratio")
            ratio.attr("operation").set(2)
            pm.connectAttr(info.attr("arcLength"), ratio.attr("input1X"))
            ratio.attr("input2X").set(rest)
            power = self._create_node("multiplyDivide", lip + "Squash_power")
            power.attr("operation").set(3)
            pm.connectAttr(ratio.attr("outputX"), power.attr("input1X"))
            power.attr("input2X").set(-0.5)
            clamp = self._create_node("clamp", lip + "Squash_clamp")
            clamp.attr("minR").set(SQUASH_RANGE[0])
            clamp.attr("maxR").set(SQUASH_RANGE[1])
            pm.connectAttr(power.attr("outputX"), clamp.attr("inputR"))
            blend = self._create_node("blendColors", lip + "Squash_blend")
            pm.connectAttr(clamp.attr("outputR"), blend.attr("color1R"))
            blend.attr("color2R").set(1.0)
            pm.connectAttr(self.squash_stretch[lip], blend.attr("blender"))
            for roll, _ in rolls:
                for axis in ("sy", "sz"):
                    pm.connectAttr(blend.attr("outputR"), roll.attr(axis))

    # ------------------------------------------------------------------
    # phase 4

    def connect_refs(self, upper_ref, lower_ref=None):
        """Make the lips follow the upper (head) and lower (jaw) references.

        The upper and lower controls follow their reference. The corners
        blend between both by their ``jawFollow`` attribute.

        Args:
            upper_ref (dagNode): Transform the upper lip follows.
            lower_ref (dagNode, optional): Transform the lower lip follows.
                The upper reference when None.
        """
        b = self.backend
        rig_m = datatypes.Matrix(self.geometry.rig_matrix)
        lower_ref = lower_ref if lower_ref is not None else upper_ref
        refs = [
            b.add_transform(pm.PyNode(ref), name, rig_m)
            for ref, name in ((upper_ref, "upperRef_cns"), (lower_ref, "lowerRef_cns"))
        ]
        applyop.matrix_constraint(refs[0], self.npos["upper"], "rt", offset=True)
        applyop.matrix_constraint(refs[1], self.npos["lower"], "rt", offset=True)
        for name in CORNERS:
            blend = applyop.matrix_blend_constraint(
                refs, self.npos[name], channels="rt", offset=True
            )
            follow = self.jaw_follow[name]
            reverse = self._create_node("reverse", name + "JawFollow_reverse")
            pm.connectAttr(follow, reverse.attr("inputX"))
            pm.connectAttr(reverse.attr("outputX"), blend + ".wtMatrix[0].weightIn")
            pm.connectAttr(follow, blend + ".wtMatrix[1].weightIn")

    # ------------------------------------------------------------------
    # phase 5

    def build_skin(self):
        """Skin the lips mesh when the doSkin setting is on.

        Returns:
            str: The skin cluster, or None when skipped.
        """
        return self._autoskin(self.joint_seeds, self.geometry.loop, "Lips")
