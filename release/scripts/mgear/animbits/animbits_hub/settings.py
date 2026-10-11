"""Persistent settings of the Animbits Hub.

Stored in the shared mGear user settings (``mGear_user_settings.ini``)
under the ``animbits_hub`` group.
"""

from mgear.core import pyqt

GROUP = "animbits_hub"

SHOW_NAMES_HOVER = "hover"
SHOW_NAMES_ALWAYS = "always"
SHOW_NAMES = (SHOW_NAMES_HOVER, SHOW_NAMES_ALWAYS)

PLACEMENT_CURSOR = "cursor"
PLACEMENT_FIXED = "fixed"
PLACEMENTS = (PLACEMENT_CURSOR, PLACEMENT_FIXED)

DEFAULT_SELECTION_COLOR = (0.60, 0.85, 0.60)

SCALE_MIN = 0.5
SCALE_MAX = 3.0
SCALE_STEP = 0.1


def clamp_scale(value):
    """Clamp a scale to the allowed range, rounded to the scale step.

    Args:
        value (float): The scale.

    Returns:
        float: The scale in [SCALE_MIN, SCALE_MAX], rounded to 0.1.
    """
    return round(min(max(float(value), SCALE_MIN), SCALE_MAX), 1)


def _to_floats(value, count):
    """Parse a comma separated string into floats, None when invalid."""
    if not value:
        return None
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        parts = str(value).split(",")
    try:
        floats = tuple(float(part) for part in parts)
    except ValueError:
        return None
    return floats if len(floats) == count else None


def _to_text(values):
    """Join numbers into a comma separated string."""
    return ",".join("{:g}".format(value) for value in values)


class HubSettings(object):
    """Typed access to the hub settings, with defaults.

    Every setter saves at once.

    Args:
        qsettings (QSettings, optional): Settings object. Defaults to the
            shared mGear user settings.
    """

    def __init__(self, qsettings=None):
        self._settings = qsettings or pyqt.get_user_settings()

    def _get(self, key):
        return self._settings.value("{}/{}".format(GROUP, key))

    def _set(self, key, value):
        self._settings.setValue("{}/{}".format(GROUP, key), value)
        self._settings.sync()

    @property
    def show_names(self):
        """str: ``"hover"`` or ``"always"``."""
        value = self._get("show_names")
        return value if value in SHOW_NAMES else SHOW_NAMES_HOVER

    @show_names.setter
    def show_names(self, value):
        if value not in SHOW_NAMES:
            raise ValueError("show_names must be one of {}".format(SHOW_NAMES))
        self._set("show_names", value)

    @property
    def placement(self):
        """str: ``"cursor"`` or ``"fixed"``."""
        value = self._get("placement")
        return value if value in PLACEMENTS else PLACEMENT_CURSOR

    @placement.setter
    def placement(self, value):
        if value not in PLACEMENTS:
            raise ValueError("placement must be one of {}".format(PLACEMENTS))
        self._set("placement", value)

    @property
    def fixed_pos(self):
        """tuple: ``(x, y)`` top-left corner of the fixed position, or None."""
        pos = _to_floats(self._get("fixed_pos"), 2)
        return tuple(int(v) for v in pos) if pos else None

    @fixed_pos.setter
    def fixed_pos(self, value):
        self._set("fixed_pos", _to_text(value) if value else "")

    @property
    def selection_color(self):
        """tuple: RGB 0-1 color of the selection row."""
        return _to_floats(self._get("selection_color"), 3) or DEFAULT_SELECTION_COLOR

    @selection_color.setter
    def selection_color(self, value):
        self._set("selection_color", _to_text(value))

    @property
    def scale(self):
        """float: Overlay scale, in [SCALE_MIN, SCALE_MAX]."""
        value = _to_floats(self._get("scale"), 1)
        return clamp_scale(value[0]) if value else 1.0

    @scale.setter
    def scale(self, value):
        self._set("scale", _to_text([clamp_scale(value)]))
