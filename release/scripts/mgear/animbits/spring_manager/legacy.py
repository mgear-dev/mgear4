"""Support for spring setups made by the previous Spring Manager.

Legacy setups are identified by the ``springSetupMembers`` message
attribute on the control. They can only be baked or deleted.
"""

from maya import cmds

import mgear
from mgear.core import anim_utils
from mgear.core import attribute

from . import constants
from .backends import SpringBackend
from .backends import classic

# attributes added on the control by the previous Spring Manager
LEGACY_ATTRS = tuple(spec.attr for spec in classic.CLASSIC_PARAMS) + (
    constants.LEGACY_MEMBERS_ATTR,
    "springConfig",
    "springTranslation",
    "springRotation",
)


def _constraints(control):
    return cmds.listRelatives(control, type="parentConstraint", fullPath=True) or []


class LegacyBackend(SpringBackend):
    """Setups made by the Spring Manager of mGear 5.3 and older."""

    name = constants.LEGACY_BACKEND
    label = "Legacy"
    read_only_message = (
        "Legacy springs can only be baked or deleted. Delete and recreate "
        "them to edit their parameters."
    )
    hidden = True
    editable = False

    def delete(self, spring, transfer_animation=True):
        control = spring.node
        members = spring.members
        root = members[0] if members else None
        solvers = (
            cmds.listConnections(
                control + ".message",
                source=False,
                destination=True,
                type="mgear_springNode",
            )
            or []
        )
        self.detach(spring)
        if root:
            if transfer_animation:
                anim_utils.move_animation_curves(root, control)
            cmds.delete(root)
            solvers = [node for node in solvers if cmds.objExists(node)]
            if solvers:
                cmds.delete(solvers)
        else:
            mgear.log(
                "Legacy spring on {} has no root node".format(control),
                mgear.sev_warning,
            )
        attribute.delete_attrs(control, LEGACY_ATTRS)

    def detach(self, spring):
        constraints = _constraints(spring.node)
        if constraints:
            cmds.delete(constraints)

    def bake_channels(self, spring):
        return {
            spring.node: attribute.get_unlocked_channels(
                spring.node, ("translate", "rotate")
            )
        }
