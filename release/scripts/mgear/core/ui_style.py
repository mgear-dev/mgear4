"""Shared UI style for mGear tools: colour roles and metrics.

Tools ask for a semantic role ("primary", "text_error", ...) instead of
writing hex values, so every tool uses the same colours. Maya keeps its
native look: roles are applied per widget, never as a window stylesheet.

See ``UI_STYLE_GUIDE.md`` at the repository root for when to use each role.

Example:
    >>> from mgear.core import ui_style
    >>> ui_style.set_role(build_button, "primary")
    >>> ui_style.set_role(status_label, "text_error")
"""

from mgear.core import pyqt

from mgear.vendor.Qt import QtGui

ROLE_PROPERTY = "uiRole"

BUTTON_ROLES = ("primary", "secondary", "danger")
TEXT_ROLES = ("text_hint", "text_success", "text_warning", "text_error")

ROLES = {
    # Single main action of a section: Create, Apply, Build, Import.
    "primary": "#4a7c4e",
    "primary_pressed": "#3a6c3e",
    # Alternative emphasised action: Convert, Add & Snap.
    "secondary": "#4a6b8c",
    # Destructive action: Delete, Remove All.
    "danger": "#8c4a4a",
    # Selected or checked state.
    "selection": "#5285a6",
    # Status line and hint text.
    "text_hint": "#888888",
    "text_success": "#66cc66",
    "text_warning": "#e6a03c",
    "text_error": "#cc6666",
    # Rich tooltip title.
    "tooltip_accent": pyqt.TOOLTIP_COLOR,
}

# Spacing scale, in 96 DPI pixels. Pass through scaled() before use.
XS = 2
S = 4
M = 6
L = 10

# Section body margins (left, top, right, bottom), as CollapsibleWidget.
SECTION_MARGINS = (4, 2, 4, 2)
BUTTON_HEIGHT_PRIMARY = 32


def color(role):
    """Return the colour of a role.

    Args:
        role (str): Role name from ``ROLES``.

    Returns:
        QtGui.QColor: The role colour.

    Raises:
        ValueError: The role is unknown.
    """
    if role not in ROLES:
        raise ValueError("Unknown UI role: {}".format(role))
    return QtGui.QColor(ROLES[role])


def role_stylesheet(role):
    """Return the stylesheet that set_role applies for a role.

    Args:
        role (str): A button role or a text role.

    Returns:
        str: The stylesheet.

    Raises:
        ValueError: The role is not a button or text role.
    """
    if role in TEXT_ROLES:
        return "color: {};".format(ROLES[role])
    if role not in BUTTON_ROLES:
        raise ValueError("Not a button or text UI role: {}".format(role))

    base = color(role)
    if role == "primary":
        pressed = color("primary_pressed")
    else:
        pressed = base.darker(115)
    return (
        "QPushButton, QToolButton {{ background-color: {0}; }}\n"
        "QPushButton:hover, QToolButton:hover {{ background-color: {1}; }}\n"
        "QPushButton:pressed, QToolButton:pressed "
        "{{ background-color: {2}; }}"
    ).format(base.name(), base.lighter(115).name(), pressed.name())


def set_role(widget, role):
    """Style a widget with a role.

    Sets the ``uiRole`` property and replaces the widget stylesheet, so do
    not combine it with a stylesheet of your own on the same widget.

    Args:
        widget (QtWidgets.QWidget): A button for button roles, a label for
            text roles.
        role (str): A button role or a text role.

    Raises:
        ValueError: The role is not a button or text role.
    """
    widget.setStyleSheet(role_stylesheet(role))
    widget.setProperty(ROLE_PROPERTY, role)


def scaled(*values):
    """Scale values by the screen DPI and round them, for Qt setters.

    Args:
        *values (int): Values in 96 DPI pixels.

    Returns:
        tuple: The scaled int values.

    Example:
        >>> layout.setContentsMargins(*ui_style.scaled(*ui_style.SECTION_MARGINS))
    """
    return tuple(int(round(pyqt.dpi_scale(value))) for value in values)
