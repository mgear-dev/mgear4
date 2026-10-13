"""Lips Rigger 3.0: lips rig from an edge or vertex loop.

Builds the lips rig of :mod:`mgear.core.facial` with the facial rigger tool
backend. Settings are the Lips Rigger 1.0 settings in camelCase plus the new
3.0 options, see :mod:`mgear.core.facial.lips_schema`, so 1.0 ``.lips``
files load.

Example:
    >>> from mgear.rigbits.facial_rigger3 import lips
    >>> lips.rig(
    ...     vertexLoop="head.vtx[120:139]",
    ...     headJnt="head_jnt",
    ...     jawJnt="jaw_jnt",
    ... )
"""

import json

from maya import cmds

import mgear.pymaya as pm

from mgear.core import settings_schema
from mgear.core import utils
from mgear.core.facial import lips_schema
from mgear.core.facial import lips_solver
from mgear.core.facial._lips_build import LipsBuilder

from . import tool_backend

SIDE = "C"

# settings naming scene nodes, checked before building
NODE_KEYS = ("frontNode", "headJnt", "jawJnt", "upperRef", "lowerRef", "parent_node")


def _display_warnings(warnings):
    for warning in warnings:
        pm.displayWarning("Lips Rigger: {}".format(warning))


def get_settings(**kwargs):
    """Get complete lips settings from keyword arguments.

    Legacy keys are migrated, missing keys get their default and values are
    coerced. Warnings are displayed.

    Returns:
        dict: The settings.
    """
    settings, warnings = settings_schema.migrate(
        kwargs,
        lips_schema.SCHEMA,
        lips_schema.DROPPED_KEYS,
        upgrade=lips_schema.legacy_loop_type,
    )
    _display_warnings(warnings)
    return settings_schema.coerce(settings, lips_schema.SCHEMA)


def solve(settings):
    """Solve the lips geometry, displaying the error of invalid settings.

    The nodes the settings name must exist.

    Args:
        settings (dict): Complete, coerced lips settings.

    Returns:
        LipsGeometry: The geometry, or None for invalid settings.
    """
    for key in NODE_KEYS:
        if settings[key] and not cmds.objExists(settings[key]):
            pm.displayError(
                "Lips Rigger: {} {} doesn't exist".format(key, settings[key])
            )
            return None
    front = None
    if settings["frontNode"]:
        front = cmds.xform(
            settings["frontNode"], query=True, worldSpace=True, translation=True
        )
    try:
        return lips_solver.solve(settings, front=front)
    except ValueError as error:
        pm.displayError("Lips Rigger: {}".format(error))
        return None


def check_detection(**kwargs):
    """Select the detected upper lip and corners, without building.

    Args:
        **kwargs: Lips settings.

    Returns:
        LipsGeometry: The geometry, or None for invalid settings.
    """
    geometry = solve(get_settings(**kwargs))
    if geometry is None:
        return None
    cmds.select(lips_solver.detection_selection(geometry))
    pm.displayInfo(
        "Lips Rigger: the selection is the upper lip. Turn on Invert "
        "Upper/Lower if it is the lower lip"
    )
    return geometry


def rig(**kwargs):
    """Build a lips rig.

    Args:
        **kwargs: Lips settings, see :mod:`mgear.core.facial.lips_schema`.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(get_settings(**kwargs))


def _rig(settings):
    """Build a lips rig from complete, coerced settings.

    Args:
        settings (dict): Lips settings.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    if not settings["namePrefix"]:
        pm.displayError("Lips Rigger: a name prefix is needed")
        return None
    geometry = solve(settings)
    if geometry is None:
        return None

    name = tool_backend.root_name(settings["namePrefix"], SIDE)
    if cmds.objExists(name):
        pm.displayError(
            "Lips Rigger: {} already exists. Choose another name prefix".format(name)
        )
        return None

    upper_ref = settings["upperRef"] or settings["headJnt"]
    lower_ref = settings["lowerRef"] or settings["jawJnt"] or upper_ref
    with utils.undo_chunk("lipsRigger"):
        backend = tool_backend.ToolBackend(
            settings["namePrefix"],
            SIDE,
            ctl_name=settings["ctlName"],
            ctl_set=settings["ctlSet"],
            def_set=settings["defSet"],
            head_joint=settings["headJnt"] or None,
            parent_node=settings["parent_node"] or None,
            jaw_joint=settings["jawJnt"] or None,
        )
        builder = LipsBuilder(settings, geometry, backend)
        builder.build_objects()
        builder.build_attributes()
        builder.build_operators()
        if upper_ref:
            builder.connect_refs(upper_ref, lower_ref)
        builder.build_skin()
        backend.finalize()
    return backend.root


def settings_from_data(data):
    """Get lips settings from loaded ``.lips`` file data, 3.0 or 1.0.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        dict: The settings.
    """
    settings, warnings = lips_schema.settings_from_data(data)
    _display_warnings(warnings)
    return settings


def load_settings(path):
    """Load lips settings from a 3.0 or 1.0 ``.lips`` file.

    Args:
        path (str): File path.

    Returns:
        dict: The settings.
    """
    with open(path, "r") as f:
        return settings_from_data(json.load(f))


def save_settings(path, settings):
    """Save lips settings to a ``.lips`` file.

    Args:
        path (str): File path.
        settings (dict): Lips settings.
    """
    lips_schema.save_settings(path, settings)


def rig_from_data(data):
    """Build a lips rig from loaded ``.lips`` file data, 3.0 or 1.0.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(settings_from_data(data))


def rig_from_file(path):
    """Build a lips rig from a 3.0 or 1.0 ``.lips`` file.

    Args:
        path (str): File path.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(load_settings(path))
