"""Gimmick Joints window launcher, kept for shelf buttons and scripts."""

from . import ui


def mainUI(*args):
    """Show the Gimmick Joints window.

    Returns:
        ui.GimmickJointsUI: The window.
    """
    return ui.show()
