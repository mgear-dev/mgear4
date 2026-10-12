"""Shifter Build Log.

Qt-based build log window with color-coded severity, filtering,
right-click file opening, log export, and log comparison.

Replaces the old MEL-based cmdScrollFieldReporter log window.
"""

import mgear

from maya import cmds

from .ui import BuildLogWindow


def log_window():
    """Show the build log window if logging is enabled.

    Drop-in replacement for the old MEL-based log window.
    Called by ``shifter.log_window()`` at build start. Skipped in batch
    mode (mayapy), where the window can't show: the log still prints.
    """
    if mgear.logMode and mgear.use_log_window and not cmds.about(batch=True):
        show_build_log()


def show_build_log():
    """Show the Qt build log window, creating it if needed.

    Returns:
        BuildLogWindow: The window instance.
    """
    return BuildLogWindow.show_window()


def clear_log():
    """Clear the live build log window's content, if one is open.

    Called at the start of every Shifter build so each build's log shows
    only that build's output. Does nothing when no window exists.
    """
    if BuildLogWindow._is_instance_alive():
        BuildLogWindow.get_instance().clear_log()


def get_instance():
    """Get the current build log window instance.

    Returns:
        BuildLogWindow: The singleton instance, or None.
    """
    return BuildLogWindow.get_instance()
