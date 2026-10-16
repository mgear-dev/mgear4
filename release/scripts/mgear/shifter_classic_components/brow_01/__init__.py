"""Component Brow 01 module

Builds the Brow Rigger 3.0 brow rig (:mod:`mgear.core.facial`) from a path
along the brow on the mesh, one side per component. The guide root is near
the brow, root to aim is the front direction and the aim depth is the
control offset. The mesh, and the slide surface when set, must be in the
scene when the rig builds.

A center brow (side C) with leftBrow and rightBrow set follows the inner
controls of those brow_01 components at its ends.
"""

# TODO: project each joint on the slide surface too, if the control points
#   are not enough on strongly curved skulls

from mgear.shifter import component
from mgear.shifter.component.facial_backend import ComponentBackend

from mgear.core.facial._brow_build import BrowBuilder

from . import guide

##########################################################
# COMPONENT
##########################################################


class Component(component.Main):
    """Shifter component Class"""

    # =====================================================
    # OBJECTS
    # =====================================================
    def addObjects(self):
        """Create the brow objects.

        The build validated the guide first: Guide.validate solved the brow
        geometry, reused here.
        """
        settings = guide.brow_settings(self.settings)
        geometry = self.guide.geometry
        if geometry is None:
            settings, geometry = guide.solve(self.settings, self.guide.pos, self.side)
        self.backend = ComponentBackend(self)
        self.builder = BrowBuilder(
            settings, geometry, self.backend, hooked=guide.hooked(self.settings)
        )
        self.builder.build_objects()

    # =====================================================
    # ATTRIBUTES
    # =====================================================
    def addAttributes(self):
        """Create the squeeze, surface offset and visibility attributes."""
        secondary_vis = None
        if self.settings["useSecondary"]:
            secondary_vis = self.addAnimParam(
                "secondaryVis", "Secondary Controls Vis", "bool", True
            )
        self.builder.build_attributes(secondary_vis=secondary_vis)

    # =====================================================
    # OPERATORS
    # =====================================================
    def addOperators(self):
        """Create the curve operators, secondary riders, wires and squeeze."""
        self.builder.build_operators()

    # =====================================================
    # CONNECTOR
    # =====================================================
    def setRelation(self):
        """Set the relation beetween object from guide to rig"""
        self.relatives["root"] = self.root
        self.relatives["aim"] = self.root
        self.controlRelatives["root"] = self.builder.brow_ctl
        self.controlRelatives["aim"] = self.builder.brow_ctl
        self.aliasRelatives["root"] = "brow"

    def postConnect(self):
        """Hook a center brow to the inner controls of the side brows."""
        if not self.builder.hooked:
            return
        inner = []
        for key in ("leftBrow", "rightBrow"):
            name = self.settings[key]
            side_brow = self.rig.components[name[: -len("_root")]]
            inner.append(side_brow.builder.inner_ctl)
        self.builder.connect_hooks(*inner)

    # =====================================================
    # FINALIZE
    # =====================================================
    def finalize(self):
        """Lock the npo transforms and skin when the autoskin is on."""
        super(Component, self).finalize()
        if self.options["joint_rig"]:
            self.run_autoskin(self.builder.build_skin)
