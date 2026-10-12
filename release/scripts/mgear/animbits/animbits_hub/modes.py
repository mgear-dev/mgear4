"""Slider modes of the Animbits Hub tweener.

Every mode blends each attribute from a value ``a`` (weight 0) to a value
``b`` (weight 1) with ``anim_utils.apply_blend``. A mode only decides how
the cache is built and how the slider position maps to a weight. No Qt
code, so it is tested without a window.
"""

from mgear.core import anim_utils

TWEEN = "tween"
DEFAULT = "default"
MIRROR = "mirror"
BUFFER = "buffer"
PUSH = "push"


class SliderMode(object):
    """A slider mode: its look, its help and its slider mapping.

    Args:
        mode_id (str): Mode id, saved in the hub settings.
        label (str): Two letter label, shown on the handle.
        title (str): Mode name, shown in tooltips.
        text (str): What the mode does.
        bullets (tuple): Usage notes for the tooltip.
        color (str): Tooltip title color.
        weight_from_fraction (callable): Maps the slider fraction (0 at the
            left square, 0.5 at the center, 1 at the right square) to the
            blend weight.
        build_cache (callable): Returns the ``(plug, a, b, animated)``
            cache of a list of nodes. None for the buffer mode, which
            needs the stored values (see ``buffers.buffer_values``).
    """

    def __init__(
        self,
        mode_id,
        label,
        title,
        text,
        bullets,
        color,
        weight_from_fraction,
        build_cache,
    ):
        self.mode_id = mode_id
        self.label = label
        self.title = title
        self.text = text
        self.bullets = bullets
        self.color = color
        self.weight_from_fraction = weight_from_fraction
        self.build_cache = build_cache


def _relative(fraction):
    return 2.0 * fraction - 1.0


def _tween_cache(nodes):
    return [
        (plug, prev, next_, True)
        for plug, prev, next_ in anim_utils.get_tween_cache(nodes)
    ]


MODES = (
    SliderMode(
        TWEEN,
        "TW",
        "Tween Machine",
        "Pick an in-between pose. The left end matches the previous key, "
        "the right end the next key.",
        (
            "The left side leans on the previous key.",
            "The right side leans on the next key.",
            "Click a tick to key that percentage.",
        ),
        "#f2d16b",
        lambda fraction: fraction,
        _tween_cache,
    ),
    SliderMode(
        DEFAULT,
        "BD",
        "Blend to Default",
        "Blend the pose toward the default values of the controls.",
        (
            "The right side moves toward the default values.",
            "The left side exaggerates the difference.",
            "Animated attributes are keyed, the others are set.",
        ),
        "#7fc97f",
        _relative,
        anim_utils.get_default_cache,
    ),
    SliderMode(
        MIRROR,
        "BM",
        "Blend to Mirror",
        "Match the pose to the opposite side. Center controls move toward symmetry.",
        (
            "The right side moves toward the mirrored pose.",
            "The left side exaggerates the difference.",
            "Animated attributes are keyed, the others are set.",
        ),
        "#3fa7c9",
        _relative,
        anim_utils.get_mirror_cache,
    ),
    SliderMode(
        BUFFER,
        "BB",
        "Blend to Buffer",
        "Blend the pose toward a pose stored with the buffer button on the "
        "left of the row.",
        (
            "Click the circle to store the pose, Ctrl+click to clear it.",
            "The right side moves toward the stored pose.",
            "Works on other characters: controls are matched by name.",
        ),
        "#c77fd9",
        _relative,
        None,
    ),
    SliderMode(
        PUSH,
        "PP",
        "Push / Pull",
        "Exaggerate or soften the pose relative to the in-between of its "
        "previous and next keys.",
        (
            "Drag right to push the pose further.",
            "Drag left to pull it back to the in-between.",
            "Only attributes with keys on both sides.",
        ),
        "#e8705a",
        lambda fraction: 2.0 * fraction,
        anim_utils.get_push_cache,
    ),
)

MODE_IDS = tuple(mode.mode_id for mode in MODES)
_BY_ID = {mode.mode_id: mode for mode in MODES}


def get_mode(mode_id):
    """Return a mode by id, the tween mode for unknown ids.

    Args:
        mode_id (str): The mode id.

    Returns:
        SliderMode: The mode.
    """
    return _BY_ID.get(mode_id, _BY_ID[TWEEN])
