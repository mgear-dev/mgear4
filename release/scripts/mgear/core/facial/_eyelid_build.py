"""Eyelid rig builder.

Builds the Eye Rigger eyelid rig in phases that line up with the Shifter
build steps:

1. :meth:`EyelidBuilder.build_objects`: curves, controls, joint drivers.
2. :meth:`EyelidBuilder.build_attributes`: control attributes.
3. :meth:`EyelidBuilder.build_operators`: deformers, constraints, networks.
4. :meth:`EyelidBuilder.connect_tracking`: the eye aim source.
5. :meth:`EyelidBuilder.build_skin`: optional topological autoskin, once the
   joints exist.

Controls, joints and named nodes are created through a
:class:`mgear.core.facial.backend.BaseBackend`.
"""

import math

from maya import cmds

import mgear.pymaya as pm
from mgear.pymaya import datatypes

from mgear.core import applyop
from mgear.core import attribute
from mgear.core import curve
from mgear.core import node
from mgear.core import skin
from mgear.core import transform
from mgear.core import vector

from . import eyelid_schema
from ._build_base import MAIN_KEYABLE
from ._build_base import SECONDARY_KEYABLE
from ._build_base import FacialBuilder
from ._build_base import curve_points as _curve_points
from ._build_base import mid_point as _mid_point
from ._build_base import select_joint_indices
from ._build_base import xyz as _xyz

HALF_PI = math.pi * 0.5

# number of points of the blink blend shape curves
BLINK_POINTS = 30

# the aim control doesn't mirror: invert ry and rz to mirror a pose
AIM_MIRROR_CONF = (0, 0, 0, 0, 1, 1, 0, 0, 0)

# contact range (from the end of the blink) where the lids blend to the
# shared close shape
CONTACT_BLEND = 0.1

UPPER_NAMES = ("inCorner", "upInMid", "upMid", "upOutMid", "outCorner")
LOWER_NAMES = ("inCorner", "lowInMid", "lowMid", "lowOutMid", "outCorner")


class EyelidBuilder(FacialBuilder):
    """Build an eyelid rig from solved geometry.

    Args:
        settings (dict): Coerced eyelid settings.
        geometry (EyelidGeometry): Solved geometry.
        backend (BaseBackend): Backend creating the nodes.
    """

    def __init__(self, settings, geometry, backend):
        super(EyelidBuilder, self).__init__(settings, geometry, backend)
        self.own_aim = eyelid_schema.uses_own_aim(settings)

        # curves
        self.up_crv = None
        self.low_crv = None
        self.up_ctl_crv = None
        self.low_ctl_crv = None
        self.up_driver_crv = None
        self.low_driver_crv = None
        self.up_rest_crv = None
        self.low_rest_crv = None
        self.up_profile_crv = None
        self.low_profile_crv = None
        self.mid_up_driver_crv = None
        self.mid_low_driver_crv = None
        self.close_target_crv = None

        # hierarchy
        self.over_npo = None
        self.center_lookat = None
        self.aim_ctl = None
        self.aim_trigger_ref = None
        self.up_ctl = None
        self.low_ctl = None
        self.blink_driver = None

        # eyelid controls
        self.up_controls = []
        self.low_controls = []
        self.up_ghosts = []
        self.low_ghosts = []
        self.corner_ctls = []
        self.track_levels = []
        self.corner_track_levels = []

        # joints
        self.joint_seeds = []
        self.center_joint = None

        # operator nodes used by later phases
        self.contact_div = None
        self.up_tracking = {}
        self.low_tracking = {}
        self.corner_tracking = []
        self.vertical_offsets = []
        self.driven_attrs = []

    # ------------------------------------------------------------------
    # helpers

    # ------------------------------------------------------------------
    # phase 1

    def build_objects(self):
        """Create the curves, controls and joint drivers."""
        self._build_curves()
        self._build_roots()
        self._build_blink_controls()
        self._build_eyelid_controls(upper=True)
        self._build_eyelid_controls(upper=False)
        self._build_joint_drivers()

    def _build_curves(self):
        b = self.backend
        g = self.geometry
        root = b.setup_root
        self.up_crv = b.add_curve(root, "upperEyelid", g.upper_points)
        self.low_crv = b.add_curve(root, "lowerEyelid", g.lower_points)
        self.up_ctl_crv = b.add_curve(root, "upCtl_crv", g.upper_points)
        self.low_ctl_crv = b.add_curve(root, "lowCtl_crv", g.lower_points)
        for crv in (self.up_ctl_crv, self.low_ctl_crv):
            cmds.rebuildCurve(
                str(crv),
                spans=2,
                rebuildType=0,
                replaceOriginal=True,
                constructionHistory=False,
            )

        # the blink blend shape curves share the same point count
        up_points = [
            _xyz(p) for p in curve.getParamPositionsOnCurve(self.up_crv, BLINK_POINTS)
        ]
        low_points = [
            _xyz(p) for p in curve.getParamPositionsOnCurve(self.low_crv, BLINK_POINTS)
        ]
        self.up_driver_crv = b.add_curve(root, "upDriver_crv", up_points)
        self.low_driver_crv = b.add_curve(root, "lowDriver_crv", low_points)
        for crv in (self.up_driver_crv, self.low_driver_crv):
            cmds.setAttr(str(crv) + ".lineWidth", 5)
        self.up_rest_crv = b.add_curve(root, "upRest_target_crv", up_points)
        self.low_rest_crv = b.add_curve(root, "lowRest_target_crv", low_points)
        self.up_profile_crv = b.add_curve(root, "upProfile_target_crv", up_points)
        self.low_profile_crv = b.add_curve(root, "lowProfile_target_crv", low_points)
        self.mid_up_driver_crv = b.add_curve(root, "midUpDriver_crv", up_points)
        self.mid_low_driver_crv = b.add_curve(root, "midLowDriver_crv", low_points)
        self.close_target_crv = b.add_curve(root, "closeTarget_crv", up_points)

    def _build_roots(self):
        b = self.backend
        g = self.geometry
        center_m = self._control_matrix(g.eye_center)
        self.over_npo = b.add_transform(b.root, "center_lookatRoot", center_m)
        self.center_lookat = b.add_transform(self.over_npo, "center_lookat", center_m)

        if self.own_aim:
            # the aim never mirrors: the same rotations aim both eyes the
            # same way
            aim_m = datatypes.Matrix(g.rig_matrix)
            aim_npo = b.add_transform(b.root, "aim_npo", aim_m)
            self.aim_ctl = b.add_ctl(
                aim_npo,
                "aim",
                aim_m,
                "arrow",
                "main",
                ["rx", "ry", "rz"],
                w=self.settings["ctl_size"],
                po=datatypes.Vector(0, 0, g.aim_distance),
                mirror_conf=AIM_MIRROR_CONF,
            )

        trigger_root = b.add_transform(self.center_lookat, "aimTrigger_root", center_m)
        trigger_lvl = b.add_transform(trigger_root, "aimTrigger_lvl", center_m)
        cmds.setAttr(str(trigger_lvl) + ".tz", 1.0)
        self.aim_trigger_ref = b.add_transform(
            trigger_lvl, "aimTrigger_ref", transform.getTransform(trigger_lvl)
        )

    def _build_blink_controls(self):
        b = self.backend
        s = self.settings
        frame = self.geometry.frame
        size = s["ctl_size"]
        po = datatypes.Vector(0, 0, self.geometry.offset)
        if s["simplified"]:
            shape = "square"
            keyable = ["ty", "tx", "rz"]
            ro_up = ro_low = datatypes.Vector(HALF_PI, 0, 0)
            up_size = low_size = 0.6
        else:
            shape = "arrow"
            keyable = ["ty"]
            ro_up = datatypes.Vector(HALF_PI, HALF_PI, 0)
            ro_low = datatypes.Vector(HALF_PI, HALF_PI, HALF_PI * 2)
            up_size = 2.5
            low_size = 1.5

        up_point = _mid_point(self.up_rest_crv)
        low_point = _mid_point(self.low_rest_crv)
        up_coords = vector.to_frame_coordinates(up_point, frame)
        low_height = vector.to_frame_coordinates(low_point, frame)[1]
        low_point = tuple(
            frame["center"][i]
            + frame["lateral"][i] * up_coords[0]
            + frame["up"][i] * low_height
            + frame["normal"][i] * up_coords[2]
            for i in range(3)
        )

        blink_ctls = []
        for name, point, width, ro in (
            ("upBlink", up_point, up_size * size, ro_up),
            ("lowBlink", low_point, low_size * size, ro_low),
        ):
            m = self._control_matrix(point)
            npo = b.add_transform(self.over_npo, name + "_npo", m)
            blink_ctls.append(
                b.add_ctl(
                    npo,
                    name,
                    m,
                    shape,
                    "main",
                    keyable,
                    w=width,
                    d=width,
                    ro=ro,
                    po=po,
                    tag_parent=self.aim_ctl,
                )
            )
        self.up_ctl, self.low_ctl = blink_ctls
        self.blink_driver = b.add_transform(
            self.up_ctl, "blink_drv", self._control_matrix(up_point)
        )

    def _build_eyelid_controls(self, upper):
        """Create the 5 upper or the 3 lower eyelid controls.

        The corners are controls. The mid points are driver transforms
        (``_loc``) following ghost controls that live under the blink
        control.
        """
        b = self.backend
        s = self.settings
        size = s["ctl_size"]
        names = UPPER_NAMES if upper else LOWER_NAMES
        blink_ctl = self.up_ctl if upper else self.low_ctl
        points = _curve_points(self.up_ctl_crv if upper else self.low_ctl_crv)
        controls = [] if upper else [self.up_controls[0]]
        ghosts = []
        for i, point in enumerate(points):
            if not upper and i in (0, 4):
                continue
            secondary = i % 2 == 1
            role = "secondary" if secondary else "main"
            width = (0.3 if secondary else 0.6) * size
            keyable = SECONDARY_KEYABLE if secondary else MAIN_KEYABLE
            m = self._control_matrix(point)
            npo = b.add_transform(self.center_lookat, names[i] + "_npo", m)
            if i == 2 or (upper and i in (0, 4)):
                # extra level for the tracking offsets
                npo = b.add_transform(npo, names[i] + "_trk", m)
                if i == 2:
                    self.track_levels.append(npo)
                else:
                    self.corner_track_levels.append(npo)
            ghost = i in (1, 2, 3)
            if ghost:
                # the mid points follow ghost controls under the blink control
                driver = b.add_transform(npo, names[i] + "_loc", m)
                if i == 2:
                    m = self._control_matrix(transform.getTranslation(blink_ctl))
                parent = b.add_transform(blink_ctl, names[i] + "Ctl_npo", m)
                tag_parent = blink_ctl
            else:
                parent = npo
                tag_parent = self.up_ctl
            if ghost and i == 2 and s["simplified"]:
                # the blink control drives the mid point in simplified mode
                ctl = b.add_transform(parent, names[i] + "_lock", m)
            else:
                ctl = b.add_ctl(
                    parent,
                    names[i],
                    m,
                    "circle",
                    role,
                    keyable,
                    w=width,
                    d=width,
                    ro=datatypes.Vector(HALF_PI, 0, 0),
                    po=datatypes.Vector(0, 0, self.geometry.offset),
                    tag_parent=tag_parent,
                )
            if ghost:
                attribute.connect_local_transform(ctl, [driver])
                ghosts.append(ctl)
                controls.append(driver)
            else:
                self.corner_ctls.append(ctl)
                controls.append(ctl)
        if upper:
            self.up_controls = controls
            self.up_ghosts = ghosts
        else:
            controls.append(self.up_controls[-1])
            self.low_controls = controls
            self.low_ghosts = ghosts

    def _build_joint_drivers(self):
        b = self.backend
        s = self.settings
        g = self.geometry
        rig_m = datatypes.Matrix(g.rig_matrix)
        drivers_root = b.add_transform(b.root, "joints", rig_m)
        targets_root = b.add_transform(b.setup_root, "targets", datatypes.Matrix())
        # the lower lid shares the corner points with the upper lid
        for crv, vertices, points, prefix, base_name, skip_ends in (
            (
                self.up_crv,
                g.upper,
                g.upper_points,
                "upEyelid",
                "upEyelid_jnt_base",
                False,
            ),
            (
                self.low_crv,
                g.lower,
                g.lower_points,
                "lowEyelid",
                "lowEyelid_base",
                True,
            ),
        ):
            picks = select_joint_indices(
                len(vertices),
                s["everyNVertex"],
                s["fixedJoints"],
                s["fixedJointsNumber"],
                skip_ends=skip_ends,
            )
            info = node.createCurveInfoNode(crv)
            self._name_node(info, prefix + "_curveInfo")
            for point_index, joint_index in picks:
                position = points[point_index]
                target = b.add_transform(
                    targets_root,
                    prefix + "_aimTarget",
                    transform.setMatrixPosition(
                        datatypes.Matrix(), datatypes.Vector(*position)
                    ),
                    idx=point_index,
                )
                pm.connectAttr(
                    "{}.controlPoints[{}]".format(info, point_index),
                    target.attr("translate"),
                )
                base = b.add_transform(drivers_root, base_name, rig_m, idx=point_index)
                applyop.aimCns(
                    base,
                    target,
                    axis="zy",
                    wupType="objectrotation",
                    wupVector=[0, 1, 0],
                    wupObject=drivers_root,
                )
                ref = b.add_transform(
                    base,
                    prefix + "_jnt_ref",
                    transform.setMatrixPosition(
                        transform.getTransform(base), datatypes.Vector(*position)
                    ),
                    idx=point_index,
                )
                handle = b.add_deform_joint(ref, prefix + "_jnt", idx=joint_index)
                self.joint_seeds.append((handle, vertices[point_index]))

    # ------------------------------------------------------------------
    # phase 2

    def build_attributes(self):
        """Add the tracking and simplified mode attributes."""
        s = self.settings
        for ctl, store, v_value, h_value in (
            (self.up_ctl, self.up_tracking, s["upperVTrack"], s["upperHTrack"]),
            (self.low_ctl, self.low_tracking, s["lowerVTrack"], s["lowerHTrack"]),
        ):
            for key, value in (("vTracking", v_value), ("hTracking", h_value)):
                store[key] = attribute.addAttribute(
                    ctl,
                    key,
                    "float",
                    value,
                    minValue=0,
                    keyable=False,
                    channelBox=True,
                )
        for ctl in self.corner_ctls:
            self.corner_tracking.append(
                attribute.addAttribute(
                    ctl,
                    "vTracking",
                    "float",
                    0.1,
                    minValue=0,
                    keyable=False,
                    channelBox=True,
                )
            )
        if not s["simplified"]:
            return
        for ctl, prefix in ((self.up_ctl, "upper"), (self.low_ctl, "lower")):
            self.vertical_offsets.append(
                attribute.addAttribute(
                    ctl,
                    "verticalOffset",
                    "float",
                    0,
                    minValue=-0.2,
                    maxValue=0.2,
                    keyable=True,
                )
            )
            self.driven_attrs.append(
                [
                    attribute.addAttribute(
                        ctl,
                        "{}Driven{}".format(prefix, i),
                        "float",
                        0,
                        keyable=False,
                        channelBox=False,
                    )
                    for i in range(3)
                ]
            )

    # ------------------------------------------------------------------
    # phase 3

    def build_operators(self):
        """Create the deformers, constraints and the blink and tracking networks."""
        self._constrain_controls()
        self._build_blink_network()
        self._build_tracking_network()
        if self.settings["simplified"]:
            self._build_simplified()

    def _constrain(self, drivers, driven):
        cns = pm.parentConstraint(*(list(drivers) + [driven]), maintainOffset=True)
        # no flip
        cns.attr("interpType").set(0)
        return cns

    def _constrain_controls(self):
        for controls, ghosts in (
            (self.up_controls, self.up_ghosts),
            (self.low_controls, self.low_ghosts),
        ):
            for i in (1, 3):
                self._constrain(
                    (controls[i - 1], controls[i + 1]), controls[i].getParent()
                )
            self._constrain((ghosts[1], controls[0]), ghosts[0].getParent())
            self._constrain((ghosts[1], controls[-1]), ghosts[2].getParent())

    def _build_blink_network(self):
        b = self.backend
        applyop.gear_curvecns_op(self.up_ctl_crv, self.up_controls)
        applyop.gear_curvecns_op(self.low_ctl_crv, self.low_controls)

        def add_wire(crv, driver, name):
            wire = cmds.wire(str(crv), wire=str(driver), name=b.name(name))[0]
            cmds.setAttr(wire + ".dropoffDistance[0]", 100)
            return wire

        up_wire = add_wire(self.up_crv, self.up_driver_crv, "upEyelid_wire")
        low_wire = add_wire(self.low_crv, self.low_driver_crv, "lowEyelid_wire")
        add_wire(self.up_profile_crv, self.up_ctl_crv, "upProfile_wire")
        add_wire(self.low_profile_crv, self.low_ctl_crv, "lowProfile_wire")

        up_ty = self.up_ctl.attr("ty")
        low_ty = self.low_ctl.attr("ty")
        pm.pointConstraint(self.low_ctl, self.blink_driver, maintainOffset=False)
        rest = self.blink_driver.attr("ty").get()

        up_div = node.createDivNode(up_ty, rest)
        self._name_node(up_div, "upBlink_div")
        low_div = node.createDivNode(low_ty, -rest)
        self._name_node(low_div, "lowBlink_div")
        minus = node.createPlusMinusAverage1D(
            [rest, self.blink_driver.attr("ty")], operation=2
        )
        self._name_node(minus, "contact_pma")
        self.contact_div = node.createDivNode(minus.attr("output1D"), rest)
        self._name_node(self.contact_div, "contact_div")

        # the lid wires stop following the driver curves when the blink
        # controls start to move. Eye Rigger 2.1 left the lower wire scale at
        # 0 at rest, which moved the lower lid off the mesh. Both lids now
        # mirror each other.
        for ty, input_max, wire, prefix in (
            (up_ty, rest / 8.0, up_wire, "up"),
            (low_ty, -rest / 8.0, low_wire, "low"),
        ):
            remap = self._smooth_remap(
                prefix + "Wire_remap", ty, input_max=input_max, outputs=(1.0, 0.0)
            )
            pm.connectAttr(remap.attr("outValue"), wire + ".scale[0]")

        def blend_shape(targets, base, name):
            return cmds.blendShape(
                *([str(t) for t in targets] + [str(base)]), name=b.name(name)
            )[0]

        mid_up = blend_shape(
            (self.low_rest_crv, self.up_profile_crv),
            self.mid_up_driver_crv,
            "midUpDriver_blendShape",
        )
        mid_low = blend_shape(
            (self.up_rest_crv, self.low_profile_crv),
            self.mid_low_driver_crv,
            "midLowDriver_blendShape",
        )
        close = blend_shape(
            (self.mid_up_driver_crv, self.mid_low_driver_crv),
            self.close_target_crv,
            "closeTarget_blendShape",
        )
        pm.connectAttr(up_div.attr("outputX"), mid_up + ".weight[0]")
        cmds.setAttr(mid_up + ".weight[1]", 1)
        pm.connectAttr(low_div.attr("outputX"), mid_low + ".weight[0]")
        cmds.setAttr(mid_low + ".weight[1]", 1)
        cmds.setAttr(close + ".weight[0]", 0.5)
        cmds.setAttr(close + ".weight[1]", 0.5)

        up_blink = blend_shape(
            (self.low_rest_crv, self.close_target_crv, self.up_profile_crv),
            self.up_driver_crv,
            "upBlink_blendShape",
        )
        low_blink = blend_shape(
            (self.up_rest_crv, self.close_target_crv, self.low_profile_crv),
            self.low_driver_crv,
            "lowBlink_blendShape",
        )
        # Near contact each lid blends smoothly from its own shape (rest
        # target by its blink value, plus its profile) to the shared close
        # shape, which already averages both profiles. Eye Rigger 2.1
        # switched at contact and added the profiles again, so the lids
        # jumped.
        close_weight = self._smooth_remap(
            "closeBlink_remap",
            self.contact_div.attr("outputX"),
            input_min=1.0 - CONTACT_BLEND,
        ).attr("outValue")
        open_weight = node.createReverseNode(close_weight)
        self._name_node(open_weight, "closeBlink_reverse")
        # rest target weight of each lid: X upper, Y lower
        rest_weight = node.createMulNode(
            [open_weight.attr("outputX"), open_weight.attr("outputX")],
            [up_div.attr("outputX"), low_div.attr("outputX")],
        )
        self._name_node(rest_weight, "blinkRest_mult")
        for axis, blend in (("X", up_blink), ("Y", low_blink)):
            pm.connectAttr(rest_weight.attr("output" + axis), blend + ".weight[0]")
            pm.connectAttr(close_weight, blend + ".weight[1]")
            pm.connectAttr(open_weight.attr("outputX"), blend + ".weight[2]")

    def _build_tracking_network(self):
        trigger_ty = self.aim_trigger_ref.attr("ty")
        trigger_tx = self.aim_trigger_ref.attr("tx")
        contact = self.contact_div.attr("outputX")

        up_mult = node.createMulNode(self.up_tracking["vTracking"], trigger_ty)
        self._name_node(up_mult, "upVTrack_mult")
        low_mult = node.createMulNode(self.low_tracking["vTracking"], trigger_ty)
        self._name_node(low_mult, "lowVTrack_mult")
        # the up or low eyelid leads, from the tracking direction
        lead = self._create_node("remapValue", "vTrack_remap")
        pm.connectAttr(trigger_ty, lead.attr("inputValue"))
        lead.attr("inputMax").set(0.1)
        lead.attr("inputMin").set(-0.1)
        pm.connectAttr(up_mult.attr("outputX"), lead.attr("outputMax"))
        pm.connectAttr(low_mult.attr("outputX"), lead.attr("outputMin"))
        # both eyelids follow the lead when they touch
        for mult, level, name in (
            (up_mult, self.track_levels[0], "upVTrack_remap"),
            (low_mult, self.track_levels[1], "lowVTrack_remap"),
        ):
            remap = self._smooth_remap(name, contact, input_min=1.0 - CONTACT_BLEND)
            pm.connectAttr(mult.attr("outputX"), remap.attr("outputMin"))
            pm.connectAttr(lead.attr("outColorR"), remap.attr("outputMax"))
            pm.connectAttr(remap.attr("outValue"), level.attr("ty"))

        for store, level, name in (
            (self.up_tracking, self.track_levels[0], "upHTrack_mult"),
            (self.low_tracking, self.track_levels[1], "lowHTrack_mult"),
        ):
            mult = node.createMulNode(store["hTracking"], trigger_tx)
            self._name_node(mult, name)
            pm.connectAttr(mult.attr("outputX"), level.attr("tx"))

        for i, (track, level) in enumerate(
            zip(self.corner_tracking, self.corner_track_levels)
        ):
            up_mult = node.createMulNode(track, self.up_ctl.attr("ty"))
            self._name_node(up_mult, "cornerUpTrack_mult", i)
            low_mult = node.createMulNode(track, self.low_ctl.attr("ty"))
            self._name_node(low_mult, "cornerLowTrack_mult", i)
            plus = node.createPlusMinusAverage1D(
                [up_mult.attr("outputX"), low_mult.attr("outputX")]
            )
            self._name_node(plus, "cornerTrack_pma", i)
            pm.connectAttr(plus.attr("output1D"), level.attr("ty"))

    def _build_simplified(self):
        for i, (blink_ctl, ghosts, name) in enumerate(
            (
                (self.up_ctl, self.up_ghosts, "upperMidSum_pma"),
                (self.low_ctl, self.low_ghosts, "lowerMidSum_pma"),
            )
        ):
            mid = ghosts[1]
            attribute.connect_local_transform(
                blink_ctl, [mid], s=False, r=True, t=False
            )
            pm.connectAttr(blink_ctl.attr("tx"), mid.attr("tx"))
            attribute.hide_shapes(
                [ghosts[0], ghosts[2]], "hide_mid_ctl", blink_ctl, False
            )
            plus = self._create_node("plusMinusAverage", name)
            pm.connectAttr(self.vertical_offsets[i], plus.attr("input1D[0]"))
            for j, attr in enumerate(self.driven_attrs[i]):
                pm.connectAttr(attr, plus.attr("input1D[{}]".format(j + 1)))
            pm.connectAttr(plus.attr("output1D"), mid.attr("ty"))
            attribute.lockAttribute(mid)

    # ------------------------------------------------------------------
    # phase 4

    def connect_tracking(self, source, add_center_joint=True):
        """Drive the eyelid tracking from the eye aim.

        Args:
            source (dagNode): Transform aiming the eye: the rig's own aim
                control or an external one.
            add_center_joint (bool, optional): Register an eye joint
                following the source, for the eyeball skin.
        """
        pm.parentConstraint(source, self.aim_trigger_ref, maintainOffset=True)
        if add_center_joint:
            self.center_joint = self.backend.add_deform_joint(source, "center_jnt")

    # ------------------------------------------------------------------
    # phase 5

    def build_skin(self):
        """Skin the eyelid and eyeball meshes when the doSkin setting is on.

        Returns:
            str: The eyelid skin cluster, or None when skipped.
        """
        s = self.settings
        if not s["doSkin"]:
            return None
        head = self.backend.head_joint()
        if not head:
            pm.displayWarning(
                "Eyelid autoskin skipped: set the head joint to skin against"
            )
            return None
        seeds = [
            (self.backend.deform_joint(handle), vertex)
            for handle, vertex in self.joint_seeds
        ]
        skin_cluster = skin.apply_topological_autoskin(
            self.geometry.mesh,
            seeds,
            base_influence=head,
            rigid_loops=s["rigidLoops"],
            falloff_loops=s["falloffLoops"],
            loop_vertices=self.geometry.loop,
        )
        eye_mesh = s["eyeMesh"]
        if (
            eye_mesh
            and self.center_joint is not None
            and not skin.getSkinCluster(eye_mesh)
        ):
            cmds.skinCluster(
                self.backend.deform_joint(self.center_joint),
                eye_mesh,
                toSelectedBones=True,
                normalizeWeights=1,
                name=eye_mesh.split("|")[-1] + "_skinCluster",
            )
        return skin_cluster
