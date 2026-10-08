"""Spring presets: file format, namespace remap and libraries.

Preset format v2 (JSON, ``.spg``)::

    {
        "version": 2,
        "namespaces": ["chr"],
        "springs": [
            {"backend": "classic", "controls": ["arm_L0_fk0_ctl"],
             "options": {"direction": "x"}, "params": {...}}
        ],
        "colliders": [],
        "assignments": {},
        "solver": {}
    }

Control names are stored without namespace. Unknown blocks and keys are
kept when reading and ignored when applying. Version 1 presets (previous
Spring Manager) are converted on read.
"""

import json
import os

from maya import cmds

import mgear
from mgear.core import node_remap
from mgear.core import utils

from . import constants
from .backends import classic
from .backends import editable_springs
from .backends import get_backend


def _is_value(value):
    """Return True for values a preset can store: numbers and vectors."""
    if isinstance(value, (list, tuple)):
        return all(isinstance(v, (bool, int, float)) for v in value)
    return isinstance(value, (bool, int, float))


# -----------------------------------------------------------------------------
# Preset data
# -----------------------------------------------------------------------------


def new_preset():
    """Return an empty v2 preset.

    Returns:
        dict: The preset with every block.
    """
    return {
        "version": constants.PRESET_VERSION,
        "type": constants.PRESET_RIG,
        "description": "",
        "namespaces": [],
        "springs": [],
        "colliders": [],
        "assignments": {},
        "solver": {},
    }


def build_preset(entries, description=""):
    """Build a rig preset from backend ``springs`` entries.

    Namespaces are stripped from the control names and recorded in the
    ``namespaces`` block.

    Args:
        entries (list): Backend entries (see ``SpringBackend.to_preset``).
        description (str, optional): Preset description.

    Returns:
        dict: The preset.
    """
    preset = new_preset()
    preset["description"] = description
    namespaces = []
    for entry in entries:
        entry = dict(entry)
        controls = entry.get("controls") or []
        for control in controls:
            namespace = node_remap.get_namespace(control).rstrip(":")
            if namespace not in namespaces:
                namespaces.append(namespace)
        entry["controls"] = [node_remap.short_name(name) for name in controls]
        entry["params"] = {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in (entry.get("params") or {}).items()
            if _is_value(value)
        }
        preset["springs"].append(entry)
    preset["namespaces"] = namespaces
    return preset


def build_values_preset(backend, params, description=""):
    """Build a values preset: parameter values only, for any spring.

    Args:
        backend (str): Backend name the values belong to.
        params (dict): ``{attr: value}``.
        description (str, optional): Preset description.

    Returns:
        dict: The preset.
    """
    preset = build_preset(
        [{"backend": backend, "controls": [], "params": params}], description
    )
    preset["type"] = constants.PRESET_VALUES
    return preset


def preset_type(preset):
    """Return the type of a preset.

    Presets without a ``type`` (older files) are rig presets when they
    store control names, values presets otherwise.

    Args:
        preset (dict): The preset.

    Returns:
        str: :data:`constants.PRESET_VALUES` or :data:`constants.PRESET_RIG`.
    """
    stored = preset.get("type")
    if stored in (constants.PRESET_VALUES, constants.PRESET_RIG):
        return stored
    if any(entry.get("controls") for entry in preset.get("springs") or []):
        return constants.PRESET_RIG
    return constants.PRESET_VALUES


def preset_backends(preset):
    """Return the solver backends a preset holds values for.

    Args:
        preset (dict): The preset.

    Returns:
        set: Backend names.
    """
    return {entry.get("backend") for entry in preset.get("springs") or []}


def describe(preset):
    """Return a short human readable summary of a preset.

    Args:
        preset (dict): The preset.

    Returns:
        str: Multi-line summary: type, how it applies and its contents.
    """
    entries = preset.get("springs") or []
    backends = sorted(
        get_backend(name).label if get_backend(name) else str(name)
        for name in preset_backends(preset)
    )
    lines = []
    if preset_type(preset) == constants.PRESET_VALUES:
        lines.append("{} values preset".format(" + ".join(backends)))
        lines.append(
            "Applies its parameter values to the selected springs, and "
            "creates springs on selected controls without one."
        )
    else:
        controls = [c for entry in entries for c in entry.get("controls") or []]
        lines.append(
            "{} rig preset: {} spring(s)".format(" + ".join(backends), len(entries))
        )
        lines.append(
            "Creates or updates springs on its controls, in the namespace "
            "of the selection."
        )
        shown = ", ".join(controls[:6])
        if len(controls) > 6:
            shown += ", ... ({} more)".format(len(controls) - 6)
        lines.append("Controls: " + shown)
    description = (preset.get("description") or "").strip()
    if description:
        lines.insert(0, description)
    return "\n".join(lines)


def convert_v1(data):
    """Convert a version 1 preset (previous Spring Manager) to v2.

    Args:
        data (dict): v1 preset with a ``configs`` dictionary.

    Returns:
        dict: The v2 preset.
    """
    param_names = [spec.attr for spec in classic.CLASSIC_PARAMS]
    entries = []
    for key, config in sorted((data.get("configs") or {}).items()):
        direction = config.get("direction")
        if direction not in classic.DIRECTIONS:
            mgear.log(
                "Preset direction '{}' for {} is not valid, using "
                "auto".format(direction, key),
                mgear.sev_warning,
            )
            direction = classic.AUTO_DIRECTION
        entries.append(
            {
                "backend": classic.CLASSIC_BACKEND,
                "controls": [key],
                "options": {"direction": direction},
                "params": {
                    name: config[name] for name in param_names if name in config
                },
            }
        )
    return build_preset(entries)


def normalize(data):
    """Return a v2 preset from loaded JSON data, converting v1 data.

    Missing blocks are added. Unknown blocks and keys are kept.

    Args:
        data (dict): Loaded JSON data.

    Returns:
        dict: The v2 preset.

    Raises:
        ValueError: If the data is not a spring preset.
    """
    if not isinstance(data, dict):
        raise ValueError("Not a spring preset")
    if "version" not in data:
        if "configs" not in data:
            raise ValueError("Not a spring preset")
        return convert_v1(data)
    preset = new_preset()
    preset.update(data)
    return preset


def read(path):
    """Read a preset file.

    Args:
        path (str): File path.

    Returns:
        dict: The v2 preset.

    Raises:
        ValueError: If the file is not a valid spring preset.
    """
    with open(path, "r") as stream:
        try:
            data = json.load(stream)
        except ValueError as error:
            raise ValueError("Invalid preset file {}: {}".format(path, error))
    return normalize(data)


def write(path, preset):
    """Write a preset file, creating the folder when needed.

    Args:
        path (str): File path.
        preset (dict): The preset.
    """
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w") as stream:
        json.dump(preset, stream, indent=4, sort_keys=True)


def resolve_controls(entry, namespace):
    """Return the scene names of a preset entry's controls.

    Args:
        entry (dict): Preset ``springs`` entry.
        namespace (str): Namespace with trailing colon, ``""`` for the
            root namespace.

    Returns:
        list: Control names.
    """
    return [
        node_remap.add_namespace(name, namespace)
        for name in entry.get("controls") or []
    ]


def match_values(preset, targets):
    """Return the parameter values to apply to springs, ignoring names.

    Only entries of the target's backend are used. With one such entry,
    every target of that backend gets its values. With several, a target
    gets the entry sharing one of its controls (short names). Rig
    dependent parameters are left out, see :func:`entry_values`.

    Args:
        preset (dict): The preset.
        targets (list): ``(backend name, controls)`` tuples.

    Returns:
        list: Parameter dicts, one per target (empty dict when no match).
    """
    entries = preset.get("springs") or []
    values = []
    for backend, controls in targets:
        candidates = [entry for entry in entries if entry.get("backend") == backend]
        if len(candidates) == 1:
            values.append(entry_values(candidates[0]))
            continue
        names = {node_remap.short_name(control) for control in controls}
        matched = {}
        for entry in candidates:
            if names & {node_remap.short_name(c) for c in entry.get("controls") or []}:
                matched = entry
                break
        values.append(entry_values(matched))
    return values


def entry_values(entry):
    """Return the parameter values of a preset entry to apply by value.

    Parameters flagged ``rig_dependent`` by the entry's backend (e.g. the
    classic rig scale) are left out: they depend on the target rig size.

    Args:
        entry (dict): Preset ``springs`` entry.

    Returns:
        dict: ``{attr: value}``.
    """
    params = dict(entry.get("params") or {})
    backend = get_backend(entry.get("backend"))
    for spec in backend.param_specs() if backend else ():
        if spec.rig_dependent:
            params.pop(spec.attr, None)
    return params


# -----------------------------------------------------------------------------
# Libraries
# -----------------------------------------------------------------------------


def factory_folder():
    """Return the folder of the presets shipped with mGear.

    Returns:
        str: Folder path.
    """
    return os.path.join(os.path.dirname(__file__), "presets")


def user_folder():
    """Return the user presets folder. It may not exist yet.

    Returns:
        str: ``<maya user prefs>/mGear/spring_presets``.
    """
    prefs = cmds.internalVar(userPrefDir=True)
    return os.path.join(prefs, *constants.USER_PRESETS_FOLDER)


def list_presets(folder):
    """Return the presets of a library folder.

    Args:
        folder (str): Folder path. Missing folders give no presets.

    Returns:
        list: ``(name, path)`` tuples sorted by name.
    """
    if not folder or not os.path.isdir(folder):
        return []
    presets = []
    for file_name in os.listdir(folder):
        path = os.path.join(folder, file_name)
        if (
            os.path.splitext(file_name)[1].lower() == constants.PRESET_EXTENSION
            and os.path.isfile(path)
            and os.path.getsize(path) > 0
        ):
            presets.append((preset_name(path), path))
    return sorted(presets, key=lambda item: item[0].lower())


def preset_name(path):
    """Return the name of a preset file, without folder and extension.

    Args:
        path (str): Preset file path.

    Returns:
        str: The preset name.
    """
    return os.path.splitext(os.path.basename(path))[0]


def preset_path(folder, name):
    """Return the file path of a preset name in a folder.

    Args:
        folder (str): Library folder.
        name (str): Preset name, without extension.

    Returns:
        str: File path.
    """
    return os.path.join(folder, name + constants.PRESET_EXTENSION)


def thumbnail_path(path):
    """Return the thumbnail image path of a preset file.

    The thumbnail is a PNG next to the preset, with the same name.

    Args:
        path (str): Preset file path.

    Returns:
        str: Image path. The file may not exist.
    """
    return os.path.splitext(path)[0] + constants.THUMBNAIL_EXTENSION


def rename(path, name):
    """Rename a preset file and its thumbnail.

    Args:
        path (str): Preset file path.
        name (str): New preset name, without extension.

    Returns:
        str: The new preset path.

    Raises:
        OSError: If a preset with that name already exists.
    """
    new_path = preset_path(os.path.dirname(path), name)
    if os.path.exists(new_path):
        raise OSError("A preset named '{}' already exists".format(name))
    os.rename(path, new_path)
    thumbnail = thumbnail_path(path)
    if os.path.exists(thumbnail):
        os.rename(thumbnail, thumbnail_path(new_path))
    return new_path


def remove(path):
    """Delete a preset file and its thumbnail.

    Args:
        path (str): Preset file path.
    """
    for file_path in (path, thumbnail_path(path)):
        if os.path.exists(file_path):
            os.remove(file_path)


def set_description(path, description):
    """Update the description stored in a preset file.

    Args:
        path (str): Preset file path.
        description (str): New description.
    """
    preset = read(path)
    preset["description"] = description
    write(path, preset)


# -----------------------------------------------------------------------------
# Scene
# -----------------------------------------------------------------------------


def collect(springs, description=""):
    """Build a rig preset from scene springs. Legacy springs are skipped.

    Args:
        springs (list): :class:`registry.Spring` records.
        description (str, optional): Preset description.

    Returns:
        dict: The preset, with an empty ``springs`` block when nothing
        could be collected.
    """
    pairs = editable_springs(springs)
    if len(pairs) < len(springs):
        mgear.log(
            "{} spring(s) can't be saved in a preset".format(len(springs) - len(pairs)),
            mgear.sev_warning,
        )
    preset = build_preset(
        [backend.to_preset(spring) for spring, backend in pairs], description
    )
    for backend in {backend for _, backend in pairs}:
        settings = backend.get_solver_settings()
        if settings:
            preset["solver"][backend.name] = settings
    return preset


def save(path, springs, description=""):
    """Save scene springs as a rig preset file.

    Args:
        path (str): File path.
        springs (list): :class:`registry.Spring` records.
        description (str, optional): Preset description.

    Returns:
        dict: The saved preset, or None when no spring could be saved (no
        file is written).
    """
    preset = collect(springs, description)
    if not preset["springs"]:
        mgear.log("No springs to save in the preset", mgear.sev_warning)
        return None
    write(path, preset)
    return preset


def apply_by_name(preset, namespace="", apply_solver=True):
    """Create or update springs from a preset, matching controls by name.

    Args:
        preset (dict): The preset.
        namespace (str, optional): Namespace to look the controls up in.
        apply_solver (bool, optional): Also apply the ``solver`` block to
            the scene solver settings.

    Returns:
        tuple: ``(springs, missing)``: the created or updated
        :class:`registry.Spring` records, and the control names that do
        not exist in the scene.
    """
    springs = []
    missing = []
    with utils.undo_chunk("springManagerApplyPreset"):
        for entry in preset.get("springs") or []:
            controls = resolve_controls(entry, namespace)
            absent = [name for name in controls if not cmds.objExists(name)]
            if absent or not controls:
                missing.extend(absent)
                continue
            backend = get_backend(entry.get("backend"))
            if not backend or not backend.is_available():
                mgear.log(
                    "Spring backend '{}' is not available, entry for {} "
                    "skipped".format(entry.get("backend"), controls[0]),
                    mgear.sev_warning,
                )
                continue
            spring = backend.from_preset(entry, controls)
            if spring:
                springs.append(spring)
        if apply_solver:
            for name, settings in (preset.get("solver") or {}).items():
                backend = get_backend(name)
                if backend and backend.is_available():
                    backend.set_solver_settings(settings)
    for name in missing:
        mgear.log("Preset control not found: {}".format(name), mgear.sev_warning)
    return springs, missing


def apply_values(preset, springs):
    """Apply only parameter values from a preset to springs.

    Args:
        preset (dict): The preset.
        springs (list): Target :class:`registry.Spring` records.

    Returns:
        int: Number of springs updated.
    """
    pairs = editable_springs(springs)
    values = match_values(
        preset, [(backend.name, spring.controls) for spring, backend in pairs]
    )
    count = 0
    with utils.undo_chunk("springManagerApplyValues"):
        for (spring, backend), params in zip(pairs, values):
            if params:
                backend.set_params([spring], params)
                count += 1
    if pairs and not count:
        mgear.log(
            "The preset has no values for the selected springs' solver",
            mgear.sev_warning,
        )
    return count
