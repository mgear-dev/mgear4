"""Shifter guide import options dialog tests"""

import pytest

_COMPONENTS = [
    {"name": "control_C0", "comp_type": "control_01", "parent": None},
    {"name": "arm_C0", "comp_type": "arm_2jnt_01", "parent": "control_C0"},
    {"name": "leg_C0", "comp_type": "leg_2jnt_01", "parent": None},
]


@pytest.fixture
def make_dialog(qt_app, setup_path):
    from mgear.shifter import guide_import_dialog

    dialogs = []

    def make(target_name=None, allow_build=True):
        dialog = guide_import_dialog.GuideImportDialog(
            "biped.sgt",
            components=_COMPONENTS,
            target_name=target_name,
            allow_build=allow_build,
        )
        dialogs.append(dialog)
        return dialog

    yield make
    for dialog in dialogs:
        dialog.deleteLater()


def _labels(dialog):
    from mgear.vendor.Qt import QtWidgets

    return sorted(b.text() for b in dialog.findChildren(QtWidgets.QPushButton))


def test_no_target(make_dialog):
    dialog = make_dialog()
    assert _labels(dialog) == ["Build", "Cancel", "Import"]

    dialog = make_dialog(allow_build=False)
    assert _labels(dialog) == ["Cancel", "Import"]


def test_target_buttons_and_tooltips(make_dialog):
    from mgear.vendor.Qt import QtWidgets

    dialog = make_dialog(target_name="spine_C0_root")
    assert _labels(dialog) == sorted(
        [
            "Import",
            "Build",
            "Cancel",
            "Add",
            "Add && Snap",
            "Partial...",
            "Select All",
            "Deselect All",
            "Back",
            "Add Selected",
            "Add Selected && Snap",
        ]
    )
    for button in dialog.findChildren(QtWidgets.QPushButton):
        assert button.toolTip(), button.text()
    for button in (
        dialog.add_btn,
        dialog.add_snap_btn,
        dialog.partial_btn,
        dialog.add_selected_btn,
        dialog.add_selected_snap_btn,
    ):
        assert "spine_C0_root" in button.toolTip()
    assert not dialog.findChildren(QtWidgets.QComboBox)


def test_choice_results(make_dialog):
    from mgear.shifter import io

    dialog = make_dialog(target_name="spine_C0_root")
    assert dialog.get_result() == (io.IMPORT_CANCEL, None, False)
    dialog.add_snap_btn.click()
    assert dialog.get_result() == (io.IMPORT_ADD, None, True)

    dialog = make_dialog(target_name="spine_C0_root")
    dialog.build_btn.click()
    assert dialog.get_result() == (io.IMPORT_BUILD, None, False)

    dialog = make_dialog()
    dialog.import_btn.click()
    assert dialog.get_result() == (io.IMPORT_NEW, None, False)

    dialog = make_dialog()
    dialog.cancel_btn.click()
    assert dialog.get_result() == (io.IMPORT_CANCEL, None, False)


def test_partial_page(make_dialog):
    from mgear.shifter import io

    dialog = make_dialog(target_name="spine_C0_root")
    assert dialog.stack.currentIndex() == 0

    dialog.partial_btn.click()
    assert dialog.stack.currentIndex() == 1
    assert not dialog.add_selected_btn.isEnabled()
    assert not dialog.add_selected_snap_btn.isEnabled()

    dialog.back_btn.click()
    assert dialog.stack.currentIndex() == 0
    assert dialog.result() == 0

    dialog.partial_btn.click()
    dialog.checklist.set_checked(["control_C0"])
    # Checking a component checks its children
    assert dialog.checklist.get_selected_components() == [
        "control_C0",
        "arm_C0",
    ]
    assert dialog.checklist.get_root_components() == ["control_C0"]
    assert dialog.add_selected_btn.isEnabled()

    dialog.add_selected_snap_btn.click()
    assert dialog.get_result() == (io.IMPORT_ADD, ["control_C0"], True)


def test_checklist_select_all(qt_app, setup_path):
    from mgear.shifter import guide_import_dialog

    checklist = guide_import_dialog.ComponentChecklist(_COMPONENTS)
    changed = []
    checklist.selection_changed.connect(lambda: changed.append(True))
    checklist.select_all()
    assert checklist.get_root_components() == ["control_C0", "leg_C0"]
    checklist.deselect_all()
    assert checklist.get_selected_components() == []
    assert len(changed) == 2
    checklist.deleteLater()


def test_import_partial_dialog_api(qt_app, setup_path):
    from mgear.shifter.guide_template_manager import widgets

    dialog = widgets.ImportPartialDialog(_COMPONENTS)
    dialog.checklist.set_checked(["leg_C0"])
    assert dialog.get_selected_components() == ["leg_C0"]
    assert dialog.get_root_components() == ["leg_C0"]
    assert dialog.get_action() == widgets.ImportPartialDialog.IMPORT
    dialog.deleteLater()


def test_checklist_filter(qt_app, setup_path):
    from mgear.shifter import guide_import_dialog

    checklist = guide_import_dialog.ComponentChecklist(_COMPONENTS)
    items = checklist._item_map
    assert checklist.filter_input.toolTip()

    # Name match: the parent stays visible for the hierarchy
    checklist.filter_input.setText("ARM")
    assert [n for n, i in items.items() if not i.isHidden()] == [
        "control_C0",
        "arm_C0",
    ]

    # Select All only checks the matches, not the parents shown for context
    checklist.select_all()
    assert checklist.get_selected_components() == ["arm_C0"]

    # Type match
    checklist.set_filter("leg_2jnt")
    assert [n for n, i in items.items() if not i.isHidden()] == ["leg_C0"]

    # Clearing the filter shows all and keeps the check state
    checklist.filter_input.clear()
    assert not any(i.isHidden() for i in items.values())
    assert checklist.get_selected_components() == ["arm_C0"]

    checklist.set_filter("arm")
    checklist.deselect_all()
    assert checklist.get_selected_components() == []
    checklist.deleteLater()


def test_no_help_button(make_dialog):
    from mgear.vendor.Qt import QtCore

    dialog = make_dialog(target_name="spine_C0_root")
    flags = dialog.windowFlags()
    assert not flags & QtCore.Qt.WindowContextHelpButtonHint
