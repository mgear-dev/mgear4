"""Shifter component items for the dag menu.

A Shifter component can add its own right-click items with an optional
``dagmenu.py`` file in its folder, next to its ``__init__.py``::

    from functools import partial

    def build(builder, ctx):
        builder.item("Match Arm Pose", partial(match_pose, ctx.node))

    def register(registry):
        registry.register_section("match_pose", build)

The file is imported the first time a control of that component type is
right-clicked. Its sections are only shown for the controls of that
component type, after the built-in sections.
"""

import importlib.util
import json
import logging
import os

from maya import cmds

from mgear.core import anim_utils

logger = logging.getLogger("mgear.core.dagmenu")

COMP_TYPE_ATTR = "ctl_comp_type"
HOOK_FILE_NAME = "dagmenu.py"
COMPONENT_ORDER = 1000

_COMP_TYPES_CACHE = {}
_HOOK_PATHS = None
_LOADED_HOOKS = set()


def _get_guide_comp_types(root):
    """Get the component types stored in the guide data of a rig.

    The parsed data is cached per rig node (by UUID), so a rebuilt rig is
    parsed again and the guide data is not read on every right-click.

    Args:
        root (str): Rig top node.

    Returns:
        dict: Component full name (i.e: "arm_L0") to component type.
    """
    key = (cmds.ls(root, uuid=True) or [root])[0]
    if key in _COMP_TYPES_CACHE:
        return _COMP_TYPES_CACHE[key]
    comp_types = {}
    if cmds.attributeQuery("guide_data", node=root, exists=True):
        try:
            data = json.loads(cmds.getAttr("{}.guide_data".format(root)) or "")
            comp_types = {
                name: comp["param_values"]["comp_type"]
                for name, comp in data["components_dict"].items()
            }
        except (ValueError, KeyError, TypeError):
            pass
    _COMP_TYPES_CACHE[key] = comp_types
    return comp_types


def get_comp_type(node):
    """Get the Shifter component type of a rig control.

    Uses the control ctl_comp_type attribute. Rigs built before this
    attribute existed fall back to the rig guide data, matching the control
    name with the longest component full name.

    Args:
        node (str): Rig control.

    Returns:
        str: Component type. i.e: "arm_2jnt_01", None if not found.
    """
    if cmds.attributeQuery(COMP_TYPE_ATTR, node=node, exists=True):
        return cmds.getAttr("{}.{}".format(node, COMP_TYPE_ATTR)) or None

    root = anim_utils.find_rig_root(node)
    if not root:
        return None
    comp_types = _get_guide_comp_types(root)
    name = anim_utils.stripNamespace(node.split("|")[-1])
    matches = [c for c in comp_types if name.startswith(c + "_")]
    if not matches:
        return None
    return comp_types[max(matches, key=len)]


def get_component_hooks():
    """Get the dagmenu.py files of the Shifter components.

    The component directories are searched once per session.

    Returns:
        dict: Component type to dagmenu.py path.
    """
    global _HOOK_PATHS
    if _HOOK_PATHS is None:
        from mgear import shifter

        _HOOK_PATHS = {}
        for directory, names in shifter.getComponentDirectories().items():
            for comp_type in names:
                path = os.path.join(directory, comp_type, HOOK_FILE_NAME)
                if comp_type not in _HOOK_PATHS and os.path.isfile(path):
                    _HOOK_PATHS[comp_type] = path
    return _HOOK_PATHS


class ComponentRegistry(object):
    """Registry given to the register function of a component dagmenu.py.

    The sections are added to the "control" context and only shown for the
    controls of the component type.

    Args:
        registry (Registry): Dag menu registry.
        comp_type (str): Component type.
    """

    def __init__(self, registry, comp_type):
        self.registry = registry
        self.comp_type = comp_type

    def register_section(self, name, build, order=COMPONENT_ORDER, poll=None):
        """Register a section for the controls of the component.

        Args:
            name (str): Section name, unique in the component.
            build (callable): Called with a MenuBuilder and a MenuContext.
            order (int, optional): Build order. Defaults to 1000, after the
                built-in sections.
            poll (callable, optional): Called with a MenuContext, the section
                is skipped when it returns False.

        Returns:
            Section: The registered section.
        """
        comp_type = self.comp_type

        def comp_poll(ctx):
            if ctx.comp_type != comp_type:
                return False
            return poll is None or poll(ctx)

        return self.registry.register_section(
            "control", "{}.{}".format(comp_type, name), order, build, comp_poll
        )


def load_component_hook(registry, comp_type):
    """Import the dagmenu.py of a component and register its sections.

    The file is imported once per component type. An import error is logged
    once and not retried.

    Args:
        registry (Registry): Dag menu registry.
        comp_type (str): Component type.
    """
    if not comp_type or comp_type in _LOADED_HOOKS:
        return
    _LOADED_HOOKS.add(comp_type)
    path = get_component_hooks().get(comp_type)
    if not path:
        return
    try:
        spec = importlib.util.spec_from_file_location(
            "mgear_dagmenu_component_{}".format(comp_type), path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.register(ComponentRegistry(registry, comp_type))
    except Exception:
        logger.exception("dag menu hook failed: %s", path)


def prepare_control_menu(registry, ctx):
    """Load the dagmenu.py of the right-clicked control component.

    Prepare function of the "control" context. The component type is only
    resolved when some component has a dagmenu.py.

    Args:
        registry (Registry): Dag menu registry.
        ctx (MenuContext): The right-click context.
    """
    if get_component_hooks():
        load_component_hook(registry, ctx.comp_type)


def clear_cache():
    """Forget the found and loaded component hooks and the parsed guide data.

    The sections already registered by the hooks are kept.
    """
    global _HOOK_PATHS
    _HOOK_PATHS = None
    _COMP_TYPES_CACHE.clear()
    _LOADED_HOOKS.clear()
