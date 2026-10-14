"""Shifter build slow plug-in warning tests"""

import pytest

STEP = """import mgear.shifter.custom_step as cstp
from maya import cmds


class CustomShifterStep(cstp.customShifterMainStep):
    def setup(self):
        self.name = "{name}"

    def run(self):
        {body}
"""
LOAD = 'cmds.loadPlugin("bluePencil", quiet=True)'
DONE = "= SHIFTER BUILD RIG DONE"


@pytest.fixture
def log(setup_path, monkeypatch):
    """List of (message, severity) logged with mgear.log."""
    import mgear

    records = []

    def record(message, severity=mgear.sev_comment, *args, **kwargs):
        records.append((str(message), severity))

    monkeypatch.setattr(mgear, "log", record)
    return records


@pytest.fixture
def make_step(tmp_path):
    """Function writing a custom step file, returns its path."""

    def make(name, body="pass"):
        path = tmp_path / "{}.py".format(name)
        path.write_text(STEP.format(name=name, body=body))
        return str(path)

    return make


def _slow_warnings(log):
    import mgear

    return [
        message
        for message, severity in log
        if severity == mgear.sev_warning and message.startswith("Slow plug-in '")
    ]


def _summary(log):
    """The slow plug-in summary logged right after the build time line."""
    messages = [message for message, _ in log] + [""]
    done = next((i for i, m in enumerate(messages) if DONE in m), None)
    if done is not None and messages[done + 1].startswith("Slow plug-ins detected"):
        return messages[done + 1]
    return None


def test_loaded_before_build(build_rig, blue_pencil, log):
    from maya import cmds

    blue_pencil()
    build_rig()
    warnings = _slow_warnings(log)
    assert len(warnings) == 1
    assert "(loaded before the build started)" in warnings[0]
    assert cmds.pluginInfo("bluePencil", query=True, loaded=True)
    assert "  - bluePencil: loaded before the build started" in _summary(log)


def test_loaded_by_custom_step(build_rig, blue_pencil, log, make_step):
    noop = make_step("noop_step")
    loader = make_step("load_bp_step", LOAD)
    build_rig(post_step="{},{}".format(noop, loader))
    warnings = _slow_warnings(log)
    assert len(warnings) == 1
    assert "loaded by custom step: {}".format(loader) in warnings[0]
    summary = _summary(log).splitlines()
    assert summary[1] == "  - bluePencil: loaded by custom step: {}".format(loader)


def test_reported_once_per_build(build_rig, blue_pencil, log, make_step):
    blue_pencil()
    steps = [make_step("step_{}".format(i), LOAD) for i in range(3)]
    build_rig(pre_step=steps[0], post_step=",".join(steps[1:]))
    assert len(_slow_warnings(log)) == 1
    assert len(_summary(log).splitlines()) == 3


def test_no_slow_plugins(build_rig, blue_pencil, log, make_step):
    build_rig(post_step=make_step("noop_step"))
    assert _slow_warnings(log) == []
    assert _summary(log) is None
    assert any(DONE in message for message, _ in log)


def test_loaded_outside_custom_steps(build_rig, blue_pencil, log, monkeypatch):
    from mgear.shifter import component

    step_05 = component.Main.step_05

    def loading_step_05(self):
        blue_pencil()
        return step_05(self)

    monkeypatch.setattr(component.Main, "step_05", loading_step_05)
    build_rig()
    summary = _summary(log).splitlines()
    assert summary[1] == (
        "  - bluePencil: loaded during the build (not by a custom step)"
    )


def test_cancelled_build_has_no_summary(build_rig, blue_pencil, log, monkeypatch):
    from mgear.shifter import custom_step_widget

    def load_and_stop(step, step_dict):
        blue_pencil()
        return True  # stop the build, like "Stop Build" in the error dialog

    monkeypatch.setattr(custom_step_widget, "runStep", load_and_stop)
    build_rig(pre_step="pre/stop_step.py")
    warnings = _slow_warnings(log)
    assert len(warnings) == 1
    assert "loaded by custom step: pre/stop_step.py" in warnings[0]
    assert _summary(log) is None
    assert not any(DONE in message for message, _ in log)


def test_build_from_dict(rig_plugins, blue_pencil, log, monkeypatch):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear import shifter
    from mgear.shifter import guide
    from mgear.shifter import io

    monkeypatch.setattr(shifter, "log_window", lambda: None)
    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    cmds.select("guide")
    conf = io.get_template_from_selection()
    cmds.file(new=True, force=True)
    pm.select(clear=True)

    blue_pencil()
    shifter.Rig().buildFromDict(conf)
    warnings = _slow_warnings(log)
    assert len(warnings) == 1
    assert "(loaded before the build started)" in warnings[0]
    assert "  - bluePencil: loaded before the build started" in _summary(log)


def test_summary_lines_in_order(setup_path):
    from mgear import shifter

    found = {
        "bluePencil": shifter.SLOW_PLUGIN_BEFORE_BUILD,
        "studioNodes": shifter.SLOW_PLUGIN_BY_STEP.format("post/a.py"),
    }
    lines = shifter._slow_plugins_summary(found).splitlines()
    assert lines[0].startswith("Slow plug-ins detected in this build")
    assert lines[1] == "  - bluePencil: loaded before the build started"
    assert lines[2] == "  - studioNodes: loaded by custom step: post/a.py"
    assert "Unload them" in lines[-1]


def test_summary_empty(setup_path):
    from mgear import shifter

    assert shifter._slow_plugins_summary({}) == ""


def test_build_texts(setup_path):
    from mgear import shifter

    assert shifter.SLOW_PLUGIN_BY_STEP.format("a.py") == "loaded by custom step: a.py"
    assert shifter.SLOW_PLUGIN_DURING_BUILD == (
        "loaded during the build (not by a custom step)"
    )
