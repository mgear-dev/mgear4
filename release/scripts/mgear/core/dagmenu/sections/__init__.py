"""Built-in dag menu contexts and sections."""

from functools import partial

from maya import cmds

from .. import components
from . import control
from . import guide


def is_control(ctx):
    """Detector of the "control" context: mGear rig controls.

    Args:
        ctx (MenuContext): The right-click context.

    Returns:
        bool: True when the node has an isCtl attribute.
    """
    return cmds.attributeQuery("isCtl", node=ctx.node, exists=True)


def is_guide(ctx):
    """Detector of the "guide" context: Shifter guide nodes.

    Args:
        ctx (MenuContext): The right-click context.

    Returns:
        bool: True when the node has a rig_name or isGearGuide attribute.
    """
    return cmds.attributeQuery(
        "rig_name", node=ctx.node, exists=True
    ) or cmds.attributeQuery("isGearGuide", node=ctx.node, exists=True)


def register_builtin_sections(registry):
    """Register the built-in contexts and sections.

    Args:
        registry (Registry): Dag menu registry.
    """
    registry.register_context(
        control.CONTEXT,
        is_control,
        priority=100,
        prepare=partial(components.prepare_control_menu, registry),
    )
    registry.register_context(guide.CONTEXT, is_guide, priority=90)
    control.register(registry)
    guide.register(registry)
