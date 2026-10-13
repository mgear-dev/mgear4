"""Brow Rigger 3.0: one brow rig from an edge or vertex path.

Builds the brow rig of :mod:`mgear.core.facial` with the facial rigger tool
backend, one side per build: a left, right or center brow. A center brow
can follow the inner controls of the side brows (hookLeft, hookRight).
Settings are the Brow Rigger 1.0 settings in camelCase plus the new 3.0
options, see :mod:`mgear.core.facial.brow_schema`, so 1.0 ``.brows`` files
load.

Example:
    >>> from mgear.rigbits.facial_rigger3 import brow
    >>> brow.rig(vertexLoop="head.vtx[120:126]", headJnt="head_jnt")
"""

import json

from maya import cmds

import mgear.pymaya as pm

from mgear.core import settings_schema
from mgear.core import utils
from mgear.core.facial import brow_schema
from mgear.core.facial import brow_solver
from mgear.core.facial._brow_build import BrowBuilder

from . import tool_backend

# settings naming scene nodes, checked before building
NODE_KEYS = (
    "frontNode",
    "headJnt",
    "parent_node",
    "hookLeft",
    "hookRight",
    "slideSurface",
)


def _display_warnings(warnings):
    for warning in warnings:
        pm.displayWarning("Brow Rigger: {}".format(warning))


def get_settings(**kwargs):
    """Get complete brow settings from keyword arguments.

    Legacy keys are migrated, missing keys get their default and values are
    coerced. Warnings are displayed.

    Returns:
        dict: The settings.
    """
    settings, warnings = settings_schema.migrate(
        kwargs,
        brow_schema.SCHEMA,
        brow_schema.DROPPED_KEYS,
        upgrade=brow_schema.legacy_upgrade,
    )
    _display_warnings(warnings)
    return settings_schema.coerce(settings, brow_schema.SCHEMA)


def solve(settings):
    """Solve the brow geometry, displaying the error of invalid settings.

    The nodes the settings name must exist.

    Args:
        settings (dict): Complete, coerced brow settings.

    Returns:
        BrowGeometry: The geometry, or None for invalid settings.
    """
    for key in NODE_KEYS:
        if settings[key] and not cmds.objExists(settings[key]):
            pm.displayError(
                "Brow Rigger: {} {} doesn't exist".format(key, settings[key])
            )
            return None
    front = None
    if settings["frontNode"]:
        front = cmds.xform(
            settings["frontNode"], query=True, worldSpace=True, translation=True
        )
    try:
        return brow_solver.solve(settings, front=front)
    except ValueError as error:
        pm.displayError("Brow Rigger: {}".format(error))
        return None


def check_detection(**kwargs):
    """Select the first brow end found from the path, without building.

    It is the inner end of a left or right brow, the right end of a center
    brow.

    Args:
        **kwargs: Brow settings.

    Returns:
        BrowGeometry: The geometry, or None for invalid settings.
    """
    geometry = solve(get_settings(**kwargs))
    if geometry is None:
        return None
    cmds.select(brow_solver.detection_selection(geometry))
    end = "right" if geometry.side == "C" else "inner"
    pm.displayInfo(
        "Brow Rigger: {} brow, the selection is its {} end".format(geometry.side, end)
    )
    return geometry


def rig(**kwargs):
    """Build a brow rig.

    Args:
        **kwargs: Brow settings, see :mod:`mgear.core.facial.brow_schema`.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(get_settings(**kwargs))


def _rig(settings):
    """Build a brow rig from complete, coerced settings.

    Args:
        settings (dict): Brow settings.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    if not settings["namePrefix"]:
        pm.displayError("Brow Rigger: a name prefix is needed")
        return None
    geometry = solve(settings)
    if geometry is None:
        return None
    name = tool_backend.root_name(settings["namePrefix"], geometry.side)
    if cmds.objExists(name):
        pm.displayError(
            "Brow Rigger: {} already exists. Choose another name prefix".format(name)
        )
        return None

    hooked = bool(settings["hookLeft"] and settings["hookRight"])
    with utils.undo_chunk("browRigger"):
        backend = tool_backend.ToolBackend(
            settings["namePrefix"],
            geometry.side,
            ctl_name=settings["ctlName"],
            ctl_set=settings["ctlSet"],
            def_set=settings["defSet"],
            head_joint=settings["headJnt"] or None,
            parent_node=settings["parent_node"] or None,
        )
        builder = BrowBuilder(settings, geometry, backend, hooked=hooked)
        builder.build_objects()
        builder.build_attributes()
        builder.build_operators()
        if builder.hooked:
            builder.connect_hooks(settings["hookLeft"], settings["hookRight"])
        builder.build_skin()
        backend.finalize()
    return backend.root


def settings_from_data(data):
    """Get brow settings from loaded ``.brows`` file data, 3.0 or 1.0.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        dict: The settings.
    """
    settings, warnings = brow_schema.settings_from_data(data)
    _display_warnings(warnings)
    return settings


def load_settings(path):
    """Load brow settings from a 3.0 or 1.0 ``.brows`` file.

    Args:
        path (str): File path.

    Returns:
        dict: The settings.
    """
    with open(path, "r") as f:
        return settings_from_data(json.load(f))


def save_settings(path, settings):
    """Save brow settings to a ``.brows`` file.

    Args:
        path (str): File path.
        settings (dict): Brow settings.
    """
    brow_schema.save_settings(path, settings)


def rig_from_data(data):
    """Build a brow rig from loaded ``.brows`` file data, 3.0 or 1.0.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(settings_from_data(data))


def rig_from_file(path):
    """Build a brow rig from a 3.0 or 1.0 ``.brows`` file.

    Args:
        path (str): File path.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(load_settings(path))
