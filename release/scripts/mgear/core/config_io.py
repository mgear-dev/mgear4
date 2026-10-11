"""Config IO: versioned JSON configuration files.

Shared file helpers for tools that save a configuration to a JSON file with
their own extension (``.lat``, ``.shw``, ``.smc``, ...). Each file has a
``type`` id, a ``schema_version``, the Maya version and scene it was saved
from, and the tool's data. Loading checks the ``type``, so a tool never
reads another tool's file. No Qt.

Example:
    >>> from mgear.core import config_io
    >>> path = config_io.file_path("C:/rig/data/hero", ".smc")
    >>> config_io.write_file(path, "mirror_config", 1, "controls", {})
    >>> data = config_io.load_file(path, "mirror_config", "mirror config")
"""

import json
import os

from maya import cmds


def file_path(path, ext):
    """Return a file path with an extension when it has none.

    Args:
        path (str): File path.
        ext (str): Extension with the dot, e.g. ``".lat"``.

    Returns:
        str: The path, with ``ext`` added if it had no extension.
    """
    if not os.path.splitext(path)[1]:
        path += ext
    return path


def write_file(path, file_type, schema_version, items_key, items, extra=None):
    """Write a configuration file.

    Args:
        path (str): Output file path.
        file_type (str): File type id, checked by :func:`load_file`.
        schema_version (int): Schema version of the items.
        items_key (str): Key of the items, e.g. ``"lattices"``.
        items (list or dict): Serializable configuration data.
        extra (dict, optional): More top level keys, written before the
            items.

    Returns:
        dict: The written data.
    """
    data = {
        "type": file_type,
        "schema_version": schema_version,
        "maya_version": cmds.about(version=True),
        "scene": cmds.file(query=True, sceneName=True),
    }
    data.update(extra or {})
    data[items_key] = items
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return data


def load_file(path, file_type, label=None):
    """Load and validate a configuration file.

    Args:
        path (str): File path.
        file_type (str): Expected file type id.
        label (str, optional): Readable file kind for the error message.

    Returns:
        dict: The loaded data.

    Raises:
        ValueError: If the file is not JSON or not of the expected type.
    """
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("type") != file_type:
        raise ValueError("Not a {} file: {}".format(label or file_type, path))
    return data
