"""Build facial rigs from configuration files, whatever the rig type. No Qt."""

import json
import os

from mgear.core.facial import eyelid_schema
from mgear.core.facial import lips_schema

from . import eye
from . import lips

# file type id and legacy extension of each rig module
RIGGERS = (
    (eyelid_schema.FILE_TYPE, eyelid_schema.FILE_EXT, eye),
    (lips_schema.FILE_TYPE, lips_schema.FILE_EXT, lips),
)

FILE_FILTER = "Facial Rigger Configuration ({})".format(
    " ".join("*" + ext for _, ext, _ in RIGGERS)
)


def _load(path):
    with open(path, "r") as f:
        return json.load(f)


def _rigger(data, path):
    file_type = data.get("type") if isinstance(data, dict) else None
    extension = os.path.splitext(path)[1].lower()
    for rig_type, rig_extension, module in RIGGERS:
        if file_type == rig_type or (not file_type and extension == rig_extension):
            return module
    raise ValueError("Not a facial rigger configuration: {}".format(path))


def rigger_for_file(path):
    """Get the rig module that reads a configuration file.

    Files are matched by their ``type``, or by extension for legacy files.

    Args:
        path (str): Configuration file path, 3.0 or older.

    Returns:
        module: The rig module, with ``rig_from_data(data)``.

    Raises:
        ValueError: If the file is not a facial rigger configuration.
    """
    return _rigger(_load(path), path)


def rig_from_file(path):
    """Build the facial rig of a configuration file.

    Args:
        path (str): Configuration file path.

    Returns:
        PyNode: The rig root, or None if the rig wasn't built.

    Raises:
        ValueError: If the file is not a facial rigger configuration.
    """
    data = _load(path)
    return _rigger(data, path).rig_from_data(data)
