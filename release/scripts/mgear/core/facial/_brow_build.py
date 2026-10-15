"""Brow rig builder.

Builds the Brow Rigger rig in phases that line up with the Shifter build
steps:

1. :meth:`BrowBuilder.build_objects`: curves, controls, joint drivers.
2. :meth:`BrowBuilder.build_attributes`: squeeze, surface offset and
   visibility attributes.
3. :meth:`BrowBuilder.build_operators`: control curves (on the slide
   surface when set), secondary riders, wires and the squeeze network.
4. :meth:`BrowBuilder.connect_hooks`: a center brow follows the inner
   controls of the left and right brows.
5. :meth:`BrowBuilder.build_skin`: optional topological autoskin, once the
   joints exist.

The main controls (with tangent controls at the ends) drive a main control
curve. The optional secondary controls ride it and drive a secondary curve.
The last of them drives a rope with a wire, and the joints slide on the
rope. Controls, joints and named nodes are created through a
:class:`mgear.core.facial.backend.BaseBackend`.
"""

import math

from maya import cmds
from maya.api import OpenMaya as om2

import mgear.pymaya as pm
from mgear.pymaya import datatypes

from mgear.core import applyop
from mgear.core import attribute
from mgear.core import curve
from mgear.core import node

from ._build_base import MAIN_KEYABLE
from ._build_base import FacialBuilder
from ._build_base import cv_points
from ._build_base import select_joint_indices
from ._build_base import uniform_curve
from ._build_base import xyz

HALF_PI = math.pi * 0.5

TRANSLATE_KEYABLE = ("tx", "ty", "tz")

# mirror pose flags of controls on a not mirrored frame: tx, ry, rz invert
CENTER_MIRROR_CONF = (1, 0, 0, 0, 1, 1, 0, 0, 0)

# control shape sizes, as a part of the distance between secondary
# controls (Brow Rigger 1.0)
BROW_SIZE = 2.5
MAIN_SIZE = 1.0
TANGENT_SIZE = 0.8
SECONDARY_SIZE = 0.55

WIRE_DROPOFF = 1000


def squeeze_weight(index, count):
    """Get how much a main control squeezes, from the inner to the outer one.

    Args:
        index (int): Main control index, 0 is the inner control.
        count (int): Main controls.

    Returns:
        float: 1 at the inner control, 0 at the outer one, smooth.
    """
    t = index / float(max(count - 1, 1))
    return 1.0 - t * t * (3.0 - 2.0 * t)


def main_names(side, count):
    """Get the main control names, from the first to the last path end.

    Args:
        side (str): "L", "R" or "C".
        count (int): Main controls.

    Returns:
        list: Names, e.g. ["in", "mid01", "out"], ["out_R", "mid01", "out_L"]
            for a center brow.
    """
    ends = ("out_R", "out_L") if side == "C" else ("in", "out")
    mids = ["mid{:02d}".format(i) for i in range(1, count - 1)]
    return [ends[0]] + mids + [ends[1]]


def pad_curve_inputs(items):
    """Repeat the end inputs of a cubic curve with fewer than 4 inputs.

    Args:
        items (list): Curve inputs.

    Returns:
        list: At least 4 inputs, the same curve shape.
    """
    items = list(items)
    while len(items) < 4:
        items = [items[0]] + items + [items[-1]]
    return items


def _sample_by_length(crv, count):
    """Get count points spread by length along a curve, ends included."""
    crv = pm.PyNode(crv)
    length = crv.length()
    points = []
    for i in range(count):
        param = crv.findParamFromLength(length * i / float(count - 1))
        points.append(xyz(crv.getPointAtParam(param, space="world")))
    return points


class BrowBuilder(FacialBuilder):
    """Build a brow rig from solved geometry.

    Args:
        settings (dict): Coerced brow settings.
        geometry (BrowGeometry): Solved geometry.
        backend (BaseBackend): Backend creating the nodes.
        hooked (bool, optional): Center brow whose ends follow the left and
            right brows: the ends are hook transforms, not controls.
    """

    def __init__(self, settings, geometry, backend, hooked=False):
        super(BrowBuilder, self).__init__(settings, geometry, backend)
        self.hooked = hooked and geometry.side == "C"
        self.sliding = bool(settings["slideSurface"])

        # curves
        self.main_crv = None
        self.main_upv_crv = None
        self.sec_crv = None
        self.sec_upv_crv = None
        self.rope = None
        self.rope_upv = None

        # controls
        self.brow_ctl = None
        self.main_ctls = []
        self.main_items = []
        self.tangent_ctls = {}
        self.sec_ctls = []
        self.squeeze_offsets = []
        self.hooks = []
        self.inner_ctl = None
        self.sec_riders = []

        # curve inputs: their short names, up vectors and sliders, by node
        self.item_names = {}
        self.upvs = {}
        self.sliders = {}
        self.slide_root = None

        # joints
        self.drivers_root = None
        self.joint_seeds = []

        # attributes
        self.squeeze = None
        self.surface_offsets = {}
        self.secondary_vis = None

    # ------------------------------------------------------------------
    # helpers

    def _size(self):
        g = self.geometry
        count = self.settings["secondaryControls"]
        return g.length / float(max(count, 1)) * self.settings["ctlSize"]

    def _mirror_conf(self):
        g = self.geometry
        if g.side != "C" and self.settings["mirrorBehavior"]:
            return None
        return CENTER_MIRROR_CONF

    def _add_control(
        self, parent, name, point, shape, role, keyable, width, tag, squeeze=False
    ):
        """Create a control with an npo and an up vector child.

        With squeeze, a squeeze level goes between the npo and the control:
        its local translation is free for the squeeze network.

        Returns:
            tuple: (npo, control)
        """
        b = self.backend
        m = self._control_matrix(point)
        npo = b.add_transform(parent, name + "_npo", m)
        ctl_parent = npo
        if squeeze:
            ctl_parent = b.add_transform(npo, name + "_squeeze", m)
            self.squeeze_offsets.append((len(self.main_items), ctl_parent))
        ctl = b.add_ctl(
            ctl_parent,
            name,
            m,
            shape,
            role,
            keyable,
            w=width,
            d=width,
            ro=None if shape == "sphere" else datatypes.Vector(HALF_PI, 0, 0),
            po=datatypes.Vector(0, 0, self.geometry.control_offset),
            tag_parent=tag,
            mirror_conf=self._mirror_conf(),
        )
        self._add_upv(ctl, name, m)
        return npo, ctl

    def _add_upv(self, item, name, m):
        upv = self.backend.add_transform(item, name + "_upv", m)
        cmds.setAttr(str(upv) + ".tz", self.settings["upvOffset"])
        self.item_names[str(item)] = name
        self.upvs[str(item)] = upv
        return upv

    # ------------------------------------------------------------------
    # phase 1

    def build_objects(self):
        """Create the curves, controls and joint drivers."""
        b = self.backend
        s = self.settings
        g = self.geometry
        root = b.setup_root
        brow = b.add_curve(root, "brow_crv", g.curve_points, edit_points=True)
        main_points = _sample_by_length(brow, s["mainControls"])
        sec_points = _sample_by_length(brow, s["secondaryControls"])
        rope_points = _sample_by_length(brow, s["ropeCount"])
        mid_point = _sample_by_length(brow, 3)[1]
        pm.delete(brow)
        self._build_controls(main_points, sec_points, mid_point)
        self._build_curves(rope_points)
        self._build_joint_drivers()

    def _build_controls(self, main_points, sec_points, mid_point):
        b = self.backend
        s = self.settings
        g = self.geometry
        size = self._size()
        brow_m = self._control_matrix(mid_point)
        brow_npo = b.add_transform(b.root, "brow_npo", brow_m)
        self.brow_ctl = b.add_ctl(
            brow_npo,
            "brow",
            brow_m,
            "square",
            "main",
            MAIN_KEYABLE,
            w=BROW_SIZE * size,
            d=BROW_SIZE * size * 0.5,
            ro=datatypes.Vector(HALF_PI, 0, 0),
            po=datatypes.Vector(0, 0, g.control_offset * 1.5),
            mirror_conf=self._mirror_conf(),
        )

        names = main_names(g.side, len(main_points))
        last = len(names) - 1
        for i, (name, point) in enumerate(zip(names, main_points)):
            if self.hooked and i in (0, last):
                # the center brow ends follow the side brows
                m = self._control_matrix(point)
                hook = b.add_transform(b.root, name + "_hook", m)
                self._add_upv(hook, name + "_hook", m)
                self.hooks.append(hook)
                self.main_items.append(hook)
                continue
            _, ctl = self._add_control(
                self.brow_ctl,
                name,
                point,
                "square",
                "main",
                TRANSLATE_KEYABLE + ("rx", "ry", "rz"),
                MAIN_SIZE * size,
                self.brow_ctl,
                squeeze=g.side != "C",
            )
            self.main_ctls.append(ctl)
            self.main_items.append(ctl)
            if i in (0, last):
                _, tangent = self._add_control(
                    ctl,
                    name + "_tangent",
                    point,
                    "sphere",
                    "secondary",
                    TRANSLATE_KEYABLE,
                    TANGENT_SIZE * size,
                    ctl,
                )
                self.tangent_ctls[i] = tangent
        if not self.hooked:
            self.inner_ctl = self.main_items[0]

        if not s["useSecondary"]:
            return
        for i, point in enumerate(sec_points):
            _, ctl = self._add_control(
                self.brow_ctl,
                "sec{:02d}".format(i),
                point,
                "circle",
                "secondary",
                TRANSLATE_KEYABLE,
                SECONDARY_SIZE * size,
                self.brow_ctl,
            )
            self.sec_ctls.append(ctl)

    def _main_curve_items(self):
        """Get the main curve inputs: main controls, tangents by the ends."""
        items = list(self.main_items)
        last = len(items) - 1
        if last in self.tangent_ctls:
            items.insert(last, self.tangent_ctls[last])
        if 0 in self.tangent_ctls:
            items.insert(1, self.tangent_ctls[0])
        return pad_curve_inputs(items)

    def _build_curves(self, rope_points):
        b = self.backend
        s = self.settings
        root = b.setup_root
        normal = self.geometry.frame["normal"]
        offset = s["upvOffset"]

        def forward(points):
            return [tuple(p[i] + normal[i] * offset for i in range(3)) for p in points]

        def control_curve(name, items):
            points = [
                xyz(
                    cmds.xform(str(item), query=True, worldSpace=True, translation=True)
                )
                for item in items
            ]
            return (
                b.add_curve(root, name + "_crv", points),
                b.add_curve(root, name + "Upv_crv", forward(points)),
            )

        self.main_crv, self.main_upv_crv = control_curve(
            "mainCtl", self._main_curve_items()
        )
        if self.sec_ctls:
            self.sec_crv, self.sec_upv_crv = control_curve(
                "secCtl", pad_curve_inputs(self.sec_ctls)
            )
        self.rope = b.add_curve(root, "rope_crv", rope_points, edit_points=True)
        self.rope_upv = b.add_curve(
            root, "ropeUpv_crv", forward(rope_points), edit_points=True
        )
        for crv in (self.rope, self.rope_upv):
            uniform_curve(crv, s["ropeCount"])

    def _build_joint_drivers(self):
        b = self.backend
        s = self.settings
        g = self.geometry
        rig_m = datatypes.Matrix(g.rig_matrix)
        self.drivers_root, _ = self._world_drivers_root()
        orientation = None
        if not s["jointsFollowCurve"]:
            # translate only: every joint keeps the brow frame, which turns
            # with the rig
            _, orientation = self._fixed_orientation("jointOrient", rig_m)
        picks = select_joint_indices(
            len(g.path), s["everyNVertex"], s["fixedJoints"], s["fixedJointsNumber"]
        )
        for point_index, joint_index in picks:
            position = g.curve_points[point_index]
            u = curve.get_length_ratio_at_point(self.rope, position)
            driver = self._add_path_driver(
                "brow", joint_index, self.rope, self.rope_upv, u, orientation
            )
            handle = b.add_deform_joint(
                driver, "brow_jnt", idx=joint_index, parent="head"
            )
            self.joint_seeds.append((handle, g.path[point_index]))

    # ------------------------------------------------------------------
    # phase 2

    def build_attributes(self, secondary_vis=None):
        """Add the squeeze, surface offset and visibility attributes.

        Args:
            secondary_vis (Attribute, optional): Existing bool attribute
                showing the secondary controls, e.g. on a Shifter UI host.
                A ``secondaryVis`` attribute is added to the whole brow
                control when None.
        """
        if self.squeeze_offsets:
            self.squeeze = attribute.addAttribute(
                self.brow_ctl, "squeeze", "float", 0, minValue=0, maxValue=1
            )
        if self.sliding:
            for ctl in self.main_ctls + self.sec_ctls:
                self.surface_offsets[str(ctl)] = attribute.addAttribute(
                    ctl, "surfaceOffset", "float", 0
                )
        if not self.sec_ctls:
            return
        host, name = self.brow_ctl, "secondaryVis"
        if secondary_vis is not None:
            host, name = str(secondary_vis).split(".", 1)
        self.secondary_vis = attribute.hide_shapes(self.sec_ctls, name, host)

    # ------------------------------------------------------------------
    # phase 3

    def build_operators(self):
        """Create the curve operators, secondary riders, wires and squeeze."""
        main_items = self._main_curve_items()
        if self.sliding:
            unique = {str(item): item for item in main_items}
            self._build_sliders(list(unique.values()))
        self._drive_curve(self.main_crv, self.main_upv_crv, main_items)
        if self.sec_ctls:
            self._build_secondary_riders()
            if self.sliding:
                self._build_sliders(self.sec_ctls, self.sec_riders)
            self._drive_curve(
                self.sec_crv, self.sec_upv_crv, pad_curve_inputs(self.sec_ctls)
            )
        driver, driver_upv = self.main_crv, self.main_upv_crv
        if self.sec_ctls:
            driver, driver_upv = self.sec_crv, self.sec_upv_crv
        for crv, wire_driver, name in (
            (self.rope, driver, "rope_wire"),
            (self.rope_upv, driver_upv, "ropeUpv_wire"),
        ):
            wire = cmds.wire(
                str(crv), wire=str(wire_driver), name=self.backend.name(name)
            )[0]
            cmds.setAttr(wire + ".dropoffDistance[0]", WIRE_DROPOFF)
        if self.squeeze is not None:
            self._build_squeeze_network()

    def _build_sliders(self, items, riders=None):
        """Slide the curve inputs on the surface.

        Each control drives a slider on the slide surface, which then feeds
        the curves instead of the control. Tangents use the offset of their
        end control.

        A main control slider keeps its rest distance from the surface
        (scaled with the rig). A secondary control slider keeps the current
        distance of its rider on the main curve instead, so the main
        controls surface offsets carry over to the secondary layer.

        Args:
            items (list): Controls to slide.
            riders (list, optional): The rider of each control.
        """
        b = self.backend
        if self.slide_root is None:
            self.slide_root = b.add_transform(b.root, "slide", datatypes.Matrix())
        group = self.slide_root
        tangent_parent = {
            str(tangent): str(self.main_items[i])
            for i, tangent in self.tangent_ctls.items()
        }
        surface = self.settings["slideSurface"]
        # the rest distance scales with the rig
        root_scale = self._root_scale_node()
        for i, item in enumerate(items):
            key = str(item)
            name = self.item_names[key]
            m = datatypes.Matrix(
                cmds.xform(key, query=True, worldSpace=True, matrix=True)
            )
            slider = b.add_transform(group, name + "_slide", m)
            offset = self.surface_offsets.get(tangent_parent.get(key, key))
            applyop.surface_slide(key, str(slider), surface, offset)
            rest = slider.attr("restDistance").get()
            if riders:
                distance = applyop.surface_distance(riders[i], surface)
                total = self._create_node("plusMinusAverage", name + "_slideRest")
                pm.connectAttr(distance, total.attr("input1D[0]"))
                # keep the rest pose: the rider is not exactly on the
                # control. The correction scales with the rig
                correction = node.createMulDL()
                self._name_node(correction, name + "_slideCorrection")
                correction.attr("input1").set(rest - pm.PyNode(distance).get())
                pm.connectAttr(
                    root_scale.attr("outputScaleX"), correction.attr("input2")
                )
                pm.connectAttr(correction.attr("output"), total.attr("input1D[1]"))
                pm.connectAttr(total.attr("output1D"), slider.attr("restDistance"))
            else:
                scaled = node.createMulDL()
                self._name_node(scaled, name + "_slideRest")
                scaled.attr("input1").set(rest)
                pm.connectAttr(root_scale.attr("outputScaleX"), scaled.attr("input2"))
                pm.connectAttr(scaled.attr("output"), slider.attr("restDistance"))
            self.sliders[key] = slider
            self._add_upv(slider, name + "_slide", m)

    def _drive_curve(self, crv, upv_crv, items):
        """Drive a control curve and its up vector curve from controls."""
        inputs = [self.sliders.get(str(item), item) for item in items]
        upvs = [self.upvs[str(item)] for item in inputs]
        applyop.gear_curvecns_op(crv, inputs)
        applyop.gear_curvecns_op(upv_crv, upvs)

    def _build_secondary_riders(self):
        """The secondary controls ride the main control curve."""
        b = self.backend
        rig_m = datatypes.Matrix(self.geometry.rig_matrix)
        riders_root, root_scale = self._world_drivers_root("secRiders")
        for i, ctl in enumerate(self.sec_ctls):
            position = cmds.xform(
                str(ctl), query=True, worldSpace=True, translation=True
            )
            u = curve.get_length_ratio_at_point(self.main_crv, position)
            rider = b.add_transform(riders_root, "secRider", rig_m, idx=i)
            path = applyop.pathCns(rider, self.main_crv, u=u)
            self._name_node(path, "secRider_motionPath", i)
            pm.connectAttr(root_scale.attr("outputScale"), rider.attr("scale"))
            applyop.matrix_constraint(rider, ctl.getParent(), "t", offset=True)
            self.sec_riders.append(rider)

    def _build_squeeze_network(self):
        """Slide the main controls toward the inner end by the squeeze."""
        count = self.settings["mainControls"]
        distance = self.settings["squeezeDistance"] * self.geometry.length
        for i, level in self.squeeze_offsets:
            weight = squeeze_weight(i, count)
            if not weight:
                continue
            mult = node.createMulDL()
            self._name_node(mult, "squeeze_mult", i)
            pm.connectAttr(self.squeeze, mult.attr("input1"))
            # control X points from the inner to the outer end
            mult.attr("input2").set(-weight * distance)
            pm.connectAttr(mult.attr("output"), level.attr("tx"))

    # ------------------------------------------------------------------
    # phase 4

    def connect_hooks(self, left, right):
        """Make the center brow ends follow the left and right brows.

        Args:
            left (dagNode): Transform the left end follows, usually the
                inner control of the left brow.
            right (dagNode): Transform the right end follows.
        """
        if not self.hooked:
            return
        # the hooks run from the right to the left end
        for hook, target in zip(self.hooks, (right, left)):
            applyop.matrix_constraint(str(target), str(hook), "rt", offset=True)
        # the whole brow control stays halfway between both side brows
        middle = applyop.gear_intmatrix_op(
            self.hooks[0].attr("worldMatrix[0]"),
            self.hooks[1].attr("worldMatrix[0]"),
            0.5,
        )
        self._name_node(middle, "browMiddle_intMatrix")
        npo = str(self.brow_ctl.getParent())
        offset = (
            om2.MMatrix(cmds.getAttr(npo + ".worldMatrix[0]"))
            * om2.MMatrix(cmds.getAttr(str(middle) + ".output")).inverse()
        )
        mult = self._create_node("multMatrix", "browMiddle_multMatrix")
        cmds.setAttr(str(mult) + ".matrixIn[0]", list(offset), type="matrix")
        pm.connectAttr(middle.attr("output"), mult.attr("matrixIn[1]"))
        pm.connectAttr(npo + ".parentInverseMatrix[0]", mult.attr("matrixIn[2]"))
        decompose = self._create_node("decomposeMatrix", "browMiddle_decomp")
        pm.connectAttr(mult.attr("matrixSum"), decompose.attr("inputMatrix"))
        pm.connectAttr(decompose.attr("outputTranslate"), npo + ".translate")
        pm.connectAttr(decompose.attr("outputRotate"), npo + ".rotate")

    # ------------------------------------------------------------------
    # phase 5

    def build_skin(self):
        """Skin the brow mesh when the doSkin setting is on.

        Returns:
            str: The skin cluster, or None when skipped.
        """
        return self._autoskin(self.joint_seeds, self.geometry.path, "Brow")
