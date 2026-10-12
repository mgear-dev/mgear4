"""Bookmarks Tool.

Save and recall object/component selections and isolate visibility
states in Maya. Bookmarks persist in the scene and can be exported
to .sbk files. The data layer is ``mgear.core.selection_bookmarks``.

Example:
    from mgear.animbits import bookmarks
    bookmarks.show()
"""

__version__ = "1.0.0"

from maya import cmds

from .ui import BookmarksUI

_window = None


def show(*args):
    """Show the Bookmarks Tool UI.

    Returns:
        BookmarksUI: The UI instance.
    """
    global _window

    control = BookmarksUI.TOOL_NAME + "WorkspaceControl"
    if cmds.workspaceControl(control, query=True, exists=True):
        cmds.workspaceControl(control, edit=True, close=True)
        cmds.deleteUI(control, control=True)

    _window = BookmarksUI()
    _window.show(dockable=True)
    return _window


def drop_file(file_path):
    """Open the Bookmarks window and load a .sbk file dropped on Maya.

    Args:
        file_path (str): Bookmarks (.sbk) file path.

    Returns:
        BookmarksUI: The window.
    """
    window = show()
    window.load_file(file_path)
    return window
