"""Shifter builds in batch mode (mayapy): no main window, no dialogs."""


def test_no_ui_in_batch(setup_path):
    from maya import cmds
    from mgear.core import pyqt
    from mgear.shifter import build_log
    from mgear.vendor.Qt import QtWidgets

    assert cmds.about(batch=True)
    assert pyqt.maya_main_window() is None
    assert not pyqt.can_show_ui()
    assert pyqt.showDialog(QtWidgets.QDialog) is None
    # the build log only prints in batch mode, on every build
    for _ in range(2):
        assert build_log.show_build_log() is None


def test_failing_step_stops_build_without_dialog(build_rig, tmp_path, monkeypatch):
    from maya import cmds
    from mgear.shifter import custom_step_widget

    def no_dialog(*args, **kwargs):
        raise AssertionError("the error dialog opened in batch mode")

    monkeypatch.setattr(custom_step_widget, "CustomStepErrorDialog", no_dialog)
    step = tmp_path / "failing_step.py"
    step.write_text("raise RuntimeError('step failed')\n")
    later = tmp_path / "later_step.py"
    later.write_text(
        "from maya import cmds\ncmds.createNode('transform', name='later_step_ran')\n"
    )
    rig = build_rig(post_step="{},{}".format(step, later))
    assert rig.stopBuild
    assert not cmds.objExists("later_step_ran")


def test_repeated_builds_with_log_window(build_rig, monkeypatch):
    import mgear
    from maya import cmds

    monkeypatch.setattr(mgear, "logMode", True)
    monkeypatch.setattr(mgear, "use_log_window", True)
    for _ in range(2):
        build_rig()
        assert cmds.objExists("arm_C0_root")
