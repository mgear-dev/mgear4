"""Menu builder used by the dag menu sections."""

import contextlib

from maya import cmds


def wrap_command(command):
    """Wrap a menu command so it ignores the arguments sent by Maya.

    Maya calls menu item commands with the item check state. The wrapped
    command is called without arguments, so use functools.partial to bind
    its arguments.

    Args:
        command (callable): Command to run.

    Returns:
        callable: The wrapped command.
    """

    def run(*args):
        return command()

    return run


class MenuBuilder(object):
    """Adds items to a Maya menu.

    Dividers are deferred until the next item is added, so a menu never
    starts or ends with a divider and never has two dividers in a row.

    Args:
        parent_menu (str): Maya menu (or submenu) to fill.
    """

    def __init__(self, parent_menu):
        self.parent_menu = parent_menu
        self._has_items = False
        self._pending_divider = False

    def _flush_divider(self):
        if self._pending_divider:
            cmds.menuItem(parent=self.parent_menu, divider=True)
            self._pending_divider = False

    def divider(self):
        """Add a divider before the next item, if any items were added."""
        if self._has_items:
            self._pending_divider = True

    def item(self, label, command=None, image=None, **kwargs):
        """Add a menu item.

        Args:
            label (str): Item label.
            command (callable, optional): Called without arguments when the
                item is clicked.
            image (str, optional): Item icon.
            **kwargs: Extra cmds.menuItem flags. i.e: radioButton=True

        Returns:
            str: The menu item.
        """
        self._flush_divider()
        flags = {"parent": self.parent_menu, "label": label}
        if command is not None:
            flags["command"] = wrap_command(command)
        if image:
            flags["image"] = image
        flags.update(kwargs)
        self._has_items = True
        return cmds.menuItem(**flags)

    @contextlib.contextmanager
    def submenu(self, label, image=None, radio=False):
        """Add a submenu and yield its builder.

        Args:
            label (str): Submenu label.
            image (str, optional): Submenu icon.
            radio (bool, optional): Group the submenu items as radio buttons.

        Yields:
            MenuBuilder: Builder of the submenu.
        """
        self._flush_divider()
        flags = {
            "parent": self.parent_menu,
            "label": label,
            "subMenu": True,
            "tearOff": False,
        }
        if image:
            flags["image"] = image
        menu = cmds.menuItem(**flags)
        self._has_items = True
        if radio:
            cmds.radioMenuItemCollection(parent=menu)
        yield MenuBuilder(menu)
