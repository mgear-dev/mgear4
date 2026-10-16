"""mgear.core.ui_style roles and metrics, ActionBar and StatusLine test"""

import pytest


def test_roles_are_valid_colors(qt_app):
    from mgear.core import pyqt
    from mgear.core import ui_style

    for role in ui_style.ROLES:
        assert ui_style.color(role).isValid(), role
    for role in ui_style.BUTTON_ROLES + ui_style.TEXT_ROLES:
        assert role in ui_style.ROLES

    # Values are the colours tools already use.
    assert ui_style.ROLES["primary"] == "#4a7c4e"
    assert ui_style.ROLES["primary_pressed"] == "#3a6c3e"
    assert ui_style.ROLES["tooltip_accent"] == pyqt.TOOLTIP_COLOR
    assert ui_style.color("text_error").name() == "#cc6666"


def test_unknown_role(qt_app):
    from mgear.vendor.Qt import QtWidgets
    from mgear.core import ui_style

    with pytest.raises(ValueError):
        ui_style.color("brand")
    # Known roles that can't style a widget are refused too.
    with pytest.raises(ValueError):
        ui_style.set_role(QtWidgets.QPushButton(), "selection")


def test_set_role_button(qt_app):
    from mgear.vendor.Qt import QtWidgets
    from mgear.core import ui_style

    button = QtWidgets.QPushButton("Build")
    ui_style.set_role(button, "primary")
    assert button.property(ui_style.ROLE_PROPERTY) == "primary"
    sheet = button.styleSheet()
    assert "#4a7c4e" in sheet
    assert "#3a6c3e" in sheet
    assert ":hover" in sheet

    # Changing role replaces the stylesheet.
    ui_style.set_role(button, "danger")
    assert button.property(ui_style.ROLE_PROPERTY) == "danger"
    assert "#8c4a4a" in button.styleSheet()
    assert "#4a7c4e" not in button.styleSheet()


def test_set_role_text(qt_app):
    from mgear.vendor.Qt import QtWidgets
    from mgear.core import ui_style

    label = QtWidgets.QLabel()
    ui_style.set_role(label, "text_error")
    assert label.styleSheet() == "color: #cc6666;"


def test_metrics(qt_app):
    from mgear.core import ui_style

    assert (ui_style.XS, ui_style.S, ui_style.M, ui_style.L) == (2, 4, 6, 10)
    assert ui_style.SECTION_MARGINS == (4, 2, 4, 2)
    assert ui_style.BUTTON_HEIGHT_PRIMARY == 32
    values = ui_style.scaled(4, 10)
    assert len(values) == 2
    assert all(isinstance(v, int) for v in values)
    assert values[0] >= 4 and values[1] >= 10


def test_action_button(qt_app):
    from mgear.core import ui_style
    from mgear.core import widgets

    button = widgets.action_button("Build", "secondary", tooltip="Build it")
    assert button.text() == "Build"
    assert button.property(ui_style.ROLE_PROPERTY) == "secondary"
    assert not button.autoDefault()
    assert button.minimumHeight() == ui_style.scaled(32)[0]
    assert button.toolTip() == "Build it"


def test_action_bar_order(qt_app):
    from mgear.core import ui_style
    from mgear.core import widgets

    bar = widgets.ActionBar()
    cancel = bar.add_button("Cancel", role=None)
    build = bar.add_button("Build")
    assert cancel.property(ui_style.ROLE_PROPERTY) is None
    assert build.property(ui_style.ROLE_PROPERTY) == "primary"
    assert bar.main_layout.indexOf(cancel) < bar.main_layout.indexOf(build)

    bar.resize(400, 50)
    bar.show()
    qt_app.processEvents()
    assert build.geometry().left() > cancel.geometry().left()
    bar.close()


def test_status_line(qt_app):
    from mgear.core import ui_style
    from mgear.core import widgets

    status = widgets.StatusLine()
    assert status.property(ui_style.ROLE_PROPERTY) == "text_hint"

    status.set_message("Done", "text_success")
    assert status.text() == "Done"
    assert status.property(ui_style.ROLE_PROPERTY) == "text_success"
    assert "#66cc66" in status.styleSheet()

    status.clear()
    assert status.text() == ""
    assert status.property(ui_style.ROLE_PROPERTY) == "text_hint"
