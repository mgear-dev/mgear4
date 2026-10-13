"""Component Lips 01 module

Builds the Lips Rigger 3.0 lips rig (:mod:`mgear.core.facial`) from the loop
between the lips on the mesh. The guide root is the mouth center, root to
aim is the mouth front direction and the aim depth in front of the lips is
the control offset. The mesh must be in the scene when the rig builds.

Connectors:
    standard: the upper lip follows the guide parent, the lower lip the
        guide element set in jawRef (the parent when empty).
    mouth_01, mouth_02, MCS_mouth_01, MCS_mouth_03: the component goes under
        the mouth component root relative, the upper lip follows its lipup
        relative and the lower lip its liplow relative (MCS_mouth_01 uses
        its teeth controls, which follow the head and the jaw). Picked when
        the guide is drawn under one of these mouth components.
"""

# TODO: number of secondary controls per side (1 to 3)
# TODO: lips pushing each other instead of passing through
# TODO: a second, outer row of joints for the lips volume

import mgear.pymaya as pm

from mgear.shifter import component
from mgear.shifter.component.facial_backend import ComponentBackend

from mgear.core.facial._lips_build import LipsBuilder

from . import guide

# connectors following a parent mouth component, and its relatives
MOUTH_CONNECTORS = ("mouth_01", "mouth_02", "MCS_mouth_01", "MCS_mouth_03")
MOUTH_ROOT = "root"
MOUTH_UPPER = "lipup"
MOUTH_LOWER = "liplow"


##########################################################
# COMPONENT
##########################################################


class Component(component.Main):
    """Shifter component Class"""

    # =====================================================
    # OBJECTS
    # =====================================================
    def addObjects(self):
        """Create the lips objects.

        The build validated the guide first: Guide.validate solved the lips
        geometry, reused here.
        """
        self.follow_mouth = self._uses_mouth_connector()
        settings = guide.lips_settings(self.settings)
        geometry = self.guide.geometry
        if geometry is None:
            settings, geometry = guide.solve(self.settings, self.guide.pos)
        self.backend = ComponentBackend(self)
        self.builder = LipsBuilder(settings, geometry, self.backend)
        self.builder.build_objects()

    def _uses_mouth_connector(self):
        """Tell if the mouth connector can follow the parent component.

        Returns:
            bool: True with a mouth connector and a parent mouth component
                (root, lipup and liplow relatives).
        """
        if self.settings["connector"] not in MOUTH_CONNECTORS:
            return False
        parent = self.guide.parentComponent
        names = (MOUTH_ROOT, MOUTH_UPPER, MOUTH_LOWER)
        if parent is not None and all(name in parent.tra for name in names):
            return True
        pm.displayWarning(
            "{}: the {} connector needs a mouth component parent. Using the "
            "standard connector".format(self.fullName, self.settings["connector"])
        )
        self.settings["connector"] = "standard"
        return False

    # =====================================================
    # ATTRIBUTES
    # =====================================================
    def addAttributes(self):
        """Create the jaw follow, zipper, roll and visibility attributes."""
        secondary_vis = self.addAnimParam(
            "secondaryVis", "Secondary Controls Vis", "bool", True
        )
        self.builder.build_attributes(secondary_vis=secondary_vis)

    # =====================================================
    # OPERATORS
    # =====================================================
    def addOperators(self):
        """Create the curve operators, wires and the zipper and roll networks."""
        self.builder.build_operators()

    # =====================================================
    # CONNECTOR
    # =====================================================
    def setRelation(self):
        """Set the relation beetween object from guide to rig"""
        self.relatives["root"] = self.root
        self.relatives["aim"] = self.root
        self.controlRelatives["root"] = self.builder.controls["upper"]
        self.controlRelatives["aim"] = self.builder.controls["upper"]
        self.aliasRelatives["root"] = "lips"

    def addConnection(self):
        """Add the mouth connectors."""
        for connector in MOUTH_CONNECTORS:
            self.connections[connector] = self.connect_mouth

    def connect_mouth(self):
        """Parent the component under the mouth root relative."""
        self.parent_comp.relatives[MOUTH_ROOT].addChild(self.root)

    def postConnect(self):
        """Make the lips follow the upper and lower references."""
        if self.follow_mouth:
            upper = self.parent_comp.relatives[MOUTH_UPPER]
            lower = self.parent_comp.relatives[MOUTH_LOWER]
        else:
            upper = self.parent
            jaw_ref = self.settings["jawRef"]
            lower = self.rig.findRelative(jaw_ref) if jaw_ref else upper
        self.builder.connect_refs(upper, lower)

    # =====================================================
    # FINALIZE
    # =====================================================
    def finalize(self):
        """Lock the npo transforms and skin when the autoskin is on."""
        super(Component, self).finalize()
        if self.options["joint_rig"] and self.options.get("autoskin", True):
            self.builder.build_skin()
