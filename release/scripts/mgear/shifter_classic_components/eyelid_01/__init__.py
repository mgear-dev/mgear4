"""Component Eyelid 01 module

Builds the Eye Rigger 3.0 eyelid rig (:mod:`mgear.core.facial`) from an
eyelid loop on the mesh. The guide root is the eye center, root to aim is
the eye direction and the aim depth in front of the eyelid is the control
offset. The mesh must be in the scene when the rig builds.

Connectors:
    standard: the component makes its own eye aim control.
    eye_01, MCS_eye_01: the component goes under the parent eye component's
        look relative and follows its aim (root relative). Picked when the
        guide is drawn under one of these eye components.
"""

import mgear.pymaya as pm

from mgear.shifter import component
from mgear.shifter.component.facial_backend import ComponentBackend

from mgear.core.facial._eyelid_build import EyelidBuilder

from . import guide

# connectors following a parent eye component, and its relatives
EYE_CONNECTORS = ("eye_01", "MCS_eye_01")
EYE_AIM = "root"
EYE_LOOK = "look"


##########################################################
# COMPONENT
##########################################################


class Component(component.Main):
    """Shifter component Class"""

    # =====================================================
    # OBJECTS
    # =====================================================
    def addObjects(self):
        """Create the eyelid objects.

        The build validated the guide first: Guide.validate solved the
        eyelid geometry, reused here.
        """
        self.follow_eye = self._uses_eye_connector()
        settings = guide.eyelid_settings(self.settings, self.follow_eye)
        geometry = self.guide.geometry
        if geometry is None:
            settings, geometry = guide.solve(
                self.settings, self.guide.pos, self.side, self.follow_eye
            )
        self.backend = ComponentBackend(self)
        self.builder = EyelidBuilder(settings, geometry, self.backend)
        self.builder.build_objects()

    def _uses_eye_connector(self):
        """Tell if the eye connector can follow the parent component.

        Returns:
            bool: True with an eye connector and a parent eye component
                (root and look locators).
        """
        if self.settings["connector"] not in EYE_CONNECTORS:
            return False
        parent = self.guide.parentComponent
        if parent is not None and EYE_AIM in parent.tra and EYE_LOOK in parent.tra:
            return True
        pm.displayWarning(
            "{}: the {} connector needs an eye component parent. Using the "
            "standard connector".format(self.fullName, self.settings["connector"])
        )
        self.settings["connector"] = "standard"
        return False

    # =====================================================
    # ATTRIBUTES
    # =====================================================
    def addAttributes(self):
        """Create the tracking attributes on the blink controls."""
        self.builder.build_attributes()

    # =====================================================
    # OPERATORS
    # =====================================================
    def addOperators(self):
        """Create the eyelid deformers, constraints and networks."""
        self.builder.build_operators()

    # =====================================================
    # CONNECTOR
    # =====================================================
    def setRelation(self):
        """Set the relation beetween object from guide to rig"""
        self.relatives["root"] = self.root
        self.relatives["aim"] = self.root
        self.controlRelatives["root"] = self.builder.up_ctl
        self.controlRelatives["aim"] = self.builder.up_ctl
        self.aliasRelatives["root"] = "eyelid"

    def addConnection(self):
        """Add the eye connectors."""
        for connector in EYE_CONNECTORS:
            self.connections[connector] = self.connect_eye

    def connect_eye(self):
        """Parent the component under the eye look relative."""
        self.parent_comp.relatives[EYE_LOOK].addChild(self.root)

    def postConnect(self):
        """Drive the eyelid tracking from the eye aim."""
        if self.follow_eye:
            source = self.parent_comp.relatives[EYE_AIM]
        else:
            source = self.builder.aim_ctl
        # the eye component owns the eyeball joint
        self.builder.connect_tracking(source, add_center_joint=not self.follow_eye)

    # =====================================================
    # FINALIZE
    # =====================================================
    def finalize(self):
        """Lock the npo transforms and skin when the autoskin is on."""
        super(Component, self).finalize()
        if self.options["joint_rig"]:
            self.builder.build_skin()
