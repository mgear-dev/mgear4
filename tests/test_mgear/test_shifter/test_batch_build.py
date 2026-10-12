"""Shifter builds in batch mode (mayapy): no main window, no dialogs."""

import pytest


def test_maya_main_window_is_none_in_batch(setup_path):
    from maya import cmds
    from mgear.core import pyqt

    assert cmds.about(batch=True)
    assert pyqt.maya_main_window() is None


def test_build_log_window_skipped_in_batch(setup_path, monkeypatch):
    import mgear
    from mgear.shifter import build_log

    shown = []
    monkeypatch.setattr(build_log, "show_build_log", lambda: shown.append(True))
    monkeypatch.setattr(mgear, "logMode", True)
    monkeypatch.setattr(mgear, "use_log_window", True)
    build_log.log_window()
    assert shown == []


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
