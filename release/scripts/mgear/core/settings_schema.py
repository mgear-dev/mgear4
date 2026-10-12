"""Settings schema: one definition of a tool's settings.

A schema is a list of :class:`Param`. It is the single source of the keys,
types, defaults, ranges and labels of a tool's settings, so the tool UI, its
configuration files and a Shifter component built on the same code all
agree. It also migrates settings saved by older versions of a tool. No Qt.

Example:
    >>> from mgear.core import settings_schema as ss
    >>> SCHEMA = [
    ...     ss.Param("prefix", "string", "eye", scope="tool"),
    ...     ss.Param("count", "long", 3, minimum=1, legacy_keys=("nb",)),
    ... ]
    >>> settings, warnings = ss.migrate({"nb": 0}, SCHEMA)
    >>> ss.coerce(settings, SCHEMA)
    {'prefix': 'eye', 'count': 1}
"""

import json

from . import config_io

VALUE_TYPES = ("bool", "long", "double", "string", "enum")
SCOPES = ("shared", "tool")


class Param(object):
    """One setting of a schema.

    Args:
        key (str): Setting key, used in files, kwargs and guide attributes.
        value_type (str): "bool", "long", "double", "string" or "enum".
        default (object): Default value. Enums use the choice index.
        scope (str, optional): "shared" for settings a Shifter component
            uses too, "tool" for tool-only settings.
        minimum (float, optional): Minimum value of numbers.
        maximum (float, optional): Maximum value of numbers.
        label (str, optional): UI label. Defaults to the key.
        legacy_keys (tuple, optional): Older keys of this setting.
        choices (tuple, optional): Enum choice names.
        kind (str, optional): UI hint for strings filled from the
            selection: "mesh", "edges", "vertices", "vertex" (one vertex),
            "node" or "set" (object set).
        tooltip (str, optional): UI tooltip.
    """

    def __init__(
        self,
        key,
        value_type,
        default,
        scope="shared",
        minimum=None,
        maximum=None,
        label="",
        legacy_keys=(),
        choices=None,
        kind=None,
        tooltip="",
    ):
        if value_type not in VALUE_TYPES:
            raise ValueError("Unknown value type: {}".format(value_type))
        if scope not in SCOPES:
            raise ValueError("Unknown scope: {}".format(scope))
        self.key = key
        self.value_type = value_type
        self.default = default
        self.scope = scope
        self.minimum = minimum
        self.maximum = maximum
        self.label = label or key
        self.legacy_keys = tuple(legacy_keys)
        self.choices = tuple(choices or ())
        self.kind = kind
        self.tooltip = tooltip

    def __repr__(self):
        return "Param({!r}, {!r}, {!r})".format(self.key, self.value_type, self.default)


def defaults(schema):
    """Get the default settings of a schema.

    Args:
        schema (list): Schema params.

    Returns:
        dict: {key: default}
    """
    return {param.key: param.default for param in schema}


def migrate(data, schema, dropped_keys=()):
    """Bring saved settings up to date with a schema.

    Legacy keys are renamed, dropped and unknown keys removed and missing
    keys set to their default.

    Args:
        data (dict): Saved settings.
        schema (list): Schema params.
        dropped_keys (tuple, optional): Keys that older versions used and
            this one ignores.

    Returns:
        tuple: (settings dict, list of warning strings)
    """
    renames = {}
    for param in schema:
        for legacy in param.legacy_keys:
            renames[legacy] = param.key
    keys = set(param.key for param in schema)
    settings = defaults(schema)
    warnings = []
    for key, value in data.items():
        if key in keys:
            settings[key] = value
        elif key in renames:
            if renames[key] not in data:
                settings[renames[key]] = value
        elif key in dropped_keys:
            warnings.append("Setting '{}' is no longer used".format(key))
        else:
            warnings.append("Unknown setting '{}' ignored".format(key))
    return settings, warnings


def _coerce_value(param, value):
    if param.value_type == "string":
        return "" if value is None else str(value)
    if param.value_type == "bool":
        return bool(value)
    if param.value_type == "enum":
        if isinstance(value, str):
            value = param.choices.index(value) if value in param.choices else 0
        value = int(value)
        if not 0 <= value < max(len(param.choices), 1):
            value = param.default
        return value
    value = int(value) if param.value_type == "long" else float(value)
    if param.minimum is not None:
        value = max(value, type(value)(param.minimum))
    if param.maximum is not None:
        value = min(value, type(value)(param.maximum))
    return value


def coerce(data, schema):
    """Cast settings to their types and clamp numbers to their range.

    Enums accept a choice name or index and are stored as the index. Keys
    that are not in the schema are kept as they are.

    Args:
        data (dict): Settings.
        schema (list): Schema params.

    Returns:
        dict: New settings dict.
    """
    settings = dict(data)
    for param in schema:
        if param.key in settings:
            try:
                settings[param.key] = _coerce_value(param, settings[param.key])
            except (TypeError, ValueError):
                settings[param.key] = param.default
    return settings


def filter_scope(data, schema, scope):
    """Keep only the settings of a scope.

    Args:
        data (dict): Settings.
        schema (list): Schema params.
        scope (str): "shared" or "tool".

    Returns:
        dict: Settings of that scope.
    """
    keys = set(param.key for param in schema if param.scope == scope)
    return {key: value for key, value in data.items() if key in keys}


def choice_name(schema, key, value):
    """Get the choice name of an enum setting value.

    Args:
        schema (list): Schema params.
        key (str): Enum setting key.
        value (int or str): Choice index or name.

    Returns:
        str: The choice name.
    """
    param = next(param for param in schema if param.key == key)
    return param.choices[_coerce_value(param, value)]


def save_settings(path, file_type, schema_version, data):
    """Save settings to a versioned configuration file.

    Args:
        path (str): File path.
        file_type (str): File type id.
        schema_version (int): Schema version.
        data (dict): Settings.

    Returns:
        dict: The written file data.
    """
    return config_io.write_file(path, file_type, schema_version, "settings", data)


def load_settings(path, file_type, schema, dropped_keys=(), label=None):
    """Load settings from a configuration file.

    Reads files written by :func:`save_settings` and legacy files holding
    only a flat settings dict, then migrates and coerces the settings.

    Args:
        path (str): File path.
        file_type (str): Expected file type id.
        schema (list): Schema params.
        dropped_keys (tuple, optional): Keys older versions used.
        label (str, optional): Readable file kind for the error message.

    Returns:
        tuple: (settings dict, list of warning strings)

    Raises:
        ValueError: If the file is of another type.
    """
    with open(path, "r") as f:
        data = json.load(f)
    return settings_from_data(data, file_type, schema, dropped_keys, label)


def settings_from_data(data, file_type, schema, dropped_keys=(), label=None):
    """Get settings from loaded file data or a flat settings dict.

    Args:
        data (dict): File data or a legacy flat settings dict.
        file_type (str): Expected file type id.
        schema (list): Schema params.
        dropped_keys (tuple, optional): Keys older versions used.
        label (str, optional): Readable file kind for the error message.

    Returns:
        tuple: (settings dict, list of warning strings)

    Raises:
        ValueError: If the data is of another file type.
    """
    if not isinstance(data, dict):
        raise ValueError("Not a {} file".format(label or file_type))
    if "type" in data and "settings" in data:
        if data["type"] != file_type:
            raise ValueError("Not a {} file".format(label or file_type))
        data = data["settings"]
    settings, warnings = migrate(data, schema, dropped_keys)
    return coerce(settings, schema), warnings
