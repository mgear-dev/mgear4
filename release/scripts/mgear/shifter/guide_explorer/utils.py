"""Qt-free helpers of the Guide Explorer: guide scene state and blueprint cache."""

import os

from mgear.shifter import guide as shifter_guide
from mgear.shifter import utils as shifter_utils

# Parsed blueprint components, by resolved path: (mtime, components dict)
_blueprint_cache = {}


class GuideSceneState(object):
    """What the Guide Explorer tree shows of the scene guide.

    Tells whether the guide or its components changed since the tree was
    last built, so scene callbacks only rebuild the tree when needed. The
    names read by the last update are kept for the rebuild.

    Attributes:
        guide (str): Long name of the guide root, None without a guide.
        components (list of str): Long names of the component roots, in
            tree order.
        snapshot (tuple of str): The guide root uuid followed by the
            component root uuids. Empty without a guide, None before the
            first update.
    """

    def __init__(self):
        self.guide = None
        self.components = []
        self.snapshot = None

    def update(self):
        """Read the scene guide and its components again.

        Returns:
            bool: True if the snapshot differs from the previous one.
        """
        self.guide = shifter_utils.get_guide_root_name()
        if self.guide:
            self.components = shifter_utils.get_component_root_names(self.guide)
            snapshot = shifter_utils.get_uuids([self.guide] + self.components)
        else:
            self.components = []
            snapshot = ()
        changed = snapshot != self.snapshot
        self.snapshot = snapshot
        return changed


def load_blueprint_components(path):
    """Return the components of a blueprint guide, reading the file once.

    The parsed file is cached by its resolved path and read again only when
    its modification time changes.

    Args:
        path (str): Blueprint path, as stored on the guide.

    Returns:
        dict: The blueprint ``components_dict``, empty if the file can't be
            loaded.
    """
    resolved = shifter_guide.resolve_blueprint_path(path)
    if not resolved:
        return {}
    mtime = os.path.getmtime(resolved)
    cached = _blueprint_cache.get(resolved)
    if cached and cached[0] == mtime:
        return cached[1]
    conf = shifter_guide.load_blueprint_guide(resolved) or {}
    components = conf.get("components_dict", {})
    _blueprint_cache[resolved] = (mtime, components)
    return components
