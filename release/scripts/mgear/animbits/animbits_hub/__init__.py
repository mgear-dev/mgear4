"""Animbits Hub - quick animation tools in an overlay over the viewport.

A frameless, translucent overlay toggled with a hotkey (the
``mGear_animbitsHubToggle`` runtime command). Tools add rows to it
through :func:`register_tool`. The first tool is the Tweener: one slider
for the selection and one for each selection bookmark enabled for it.

Example:
    from mgear.animbits import animbits_hub
    animbits_hub.toggle()
"""

__version__ = "1.0.0"

from .registry import register_tool
from .registry import unregister_tool


def toggle(*args):
    """Show the hub when it is hidden, hide it when it is visible.

    Returns:
        HubOverlay: The hub window.
    """
    from . import overlay

    return overlay.toggle()


def show(*args):
    """Show the hub.

    Returns:
        HubOverlay: The hub window.
    """
    from . import overlay

    hub = overlay.get_hub()
    hub.show_hub()
    return hub


def hide(*args):
    """Hide the hub, when it exists."""
    from . import overlay

    hub = overlay.get_hub(create=False)
    if hub:
        hub.hide_hub()
