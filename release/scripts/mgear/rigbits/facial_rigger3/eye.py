"""Eye Rigger 3.0: eyelid rig from an edge or vertex loop.

Builds the eyelid rig of :mod:`mgear.core.facial` with the facial rigger
tool backend. Settings are the Eye Rigger 2.1 settings plus the vertex loop,
see :mod:`mgear.core.facial.eyelid_schema`, so 2.1 ``.eyes`` files load.

Example:
    >>> from mgear.rigbits.facial_rigger3 import eye
    >>> eye.rig(
    ...     eyeMesh="eye_L_geo",
    ...     edgeLoop="head.e[120:139]",
    ...     headJnt="head_jnt",
    ... )
"""

import json

from maya import cmds

import mgear.pymaya as pm

from mgear.core import settings_schema
from mgear.core import utils
from mgear.core.facial import eyelid_schema
from mgear.core.facial import eyelid_solver
from mgear.core.facial._eyelid_build import EyelidBuilder

from . import tool_backend


def _display_warnings(warnings):
    for warning in warnings:
        pm.displayWarning("Eye Rigger: {}".format(warning))


def get_settings(**kwargs):
    """Get complete eye settings from keyword arguments.

    Legacy keys are migrated, missing keys get their default and values are
    coerced. Warnings are displayed.

    Returns:
        dict: The settings.
    """
    settings, warnings = settings_schema.migrate(
        kwargs,
        eyelid_schema.SCHEMA,
        eyelid_schema.DROPPED_KEYS,
        upgrade=eyelid_schema.legacy_loop_type,
    )
    _display_warnings(warnings)
    return settings_schema.coerce(settings, eyelid_schema.SCHEMA)


def rig(**kwargs):
    """Build an eye rig.

    The rig makes its own aim control unless an aim controller is set.

    Args:
        **kwargs: Eye settings, see :mod:`mgear.core.facial.eyelid_schema`.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(get_settings(**kwargs))


def _rig(settings):
    """Build an eye rig from complete, coerced settings.

    Args:
        settings (dict): Eye settings.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    source = eyelid_schema.TRACKING_SOURCES[settings["trackingSource"]]
    if source == "external" and not settings["aim_controller"]:
        pm.displayError("Eye Rigger: set the aim controller for external tracking")
        return None
    if not settings["namePrefix"]:
        pm.displayError("Eye Rigger: a name prefix is needed")
        return None
    try:
        geometry = eyelid_solver.solve(settings)
    except ValueError as error:
        pm.displayError("Eye Rigger: {}".format(error))
        return None

    name = tool_backend.root_name(settings["namePrefix"], geometry.side)
    if cmds.objExists(name):
        pm.displayError(
            "Eye Rigger: {} already exists. Choose another name prefix".format(name)
        )
        return None

    with utils.undo_chunk("eyeRigger"):
        backend = tool_backend.ToolBackend(
            settings["namePrefix"],
            geometry.side,
            ctl_name=settings["ctlName"],
            ctl_set=settings["ctlSet"],
            def_set=settings["defSet"],
            head_joint=settings["headJnt"] or None,
            parent_node=settings["parent_node"] or None,
            static_parent=settings["deformers_group"] or None,
        )
        builder = EyelidBuilder(settings, geometry, backend)
        builder.build_objects()
        builder.build_attributes()
        builder.build_operators()
        if builder.own_aim:
            builder.connect_tracking(builder.aim_ctl)
        else:
            builder.connect_tracking(pm.PyNode(settings["aim_controller"]))
        builder.build_skin()
        backend.finalize()
    return backend.root


def settings_from_data(data):
    """Get eye settings from loaded ``.eyes`` file data, 3.0 or 2.1.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        dict: The settings.
    """
    settings, warnings = eyelid_schema.settings_from_data(data)
    _display_warnings(warnings)
    return settings


def load_settings(path):
    """Load eye settings from a 3.0 or 2.1 ``.eyes`` file.

    Args:
        path (str): File path.

    Returns:
        dict: The settings.
    """
    with open(path, "r") as f:
        return settings_from_data(json.load(f))


def save_settings(path, settings):
    """Save eye settings to a ``.eyes`` file.

    Args:
        path (str): File path.
        settings (dict): Eye settings.
    """
    eyelid_schema.save_settings(path, settings)


def rig_from_data(data):
    """Build an eye rig from loaded ``.eyes`` file data, 3.0 or 2.1.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(settings_from_data(data))


def rig_from_file(path):
    """Build an eye rig from a 3.0 or 2.1 ``.eyes`` file.

    Args:
        path (str): File path.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.
    """
    return _rig(load_settings(path))
