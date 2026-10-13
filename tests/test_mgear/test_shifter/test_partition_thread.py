"""Game Tools FBX partition thread tests

The partition thread runs the Maya batch export on a QThread. Maya commands
are not thread safe, and Maya 2027 rejects them off the main thread (e.g.
``cmds.about(os=True)`` raises ``TypeError: Flag 'os' must be passed a
boolean argument``), so nothing in the thread may call a Maya command.
"""

import os
import threading

import pytest


class MainThreadOnly(object):
    """Stand-in for ``maya.cmds`` failing on use outside the main thread.

    Makes the thread safety check independent of the Maya version: Maya 2026
    tolerates commands off the main thread, Maya 2027 does not.
    """

    def __init__(self, cmds):
        self.cmds = cmds
        self.thread_calls = []

    def __getattr__(self, name):
        if threading.current_thread() is not threading.main_thread():
            self.thread_calls.append(name)
            raise RuntimeError("maya.cmds.{} called off the main thread".format(name))
        return getattr(self.cmds, name)


class FakePopen(object):
    """Fake ``subprocess.Popen`` recording its arguments, exits with 0."""

    calls = []

    def __init__(self, args, **kwargs):
        FakePopen.calls.append((args, kwargs))
        self.stdout = iter(["Conditioned file: master.ma\n", "[Partitions]\n"])
        self.returncode = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def communicate(self):
        return "", ""

    def wait(self):
        return 0


@pytest.fixture
def partition_thread(setup_path, monkeypatch):
    """The partition_thread module, with guarded cmds and a fake Popen."""
    from maya import cmds
    from mgear.core import utils
    from mgear.shifter.game_tools_fbx import partition_thread

    guard = MainThreadOnly(cmds)
    monkeypatch.setattr(partition_thread, "cmds", guard)
    monkeypatch.setattr(utils, "cmds", guard)
    monkeypatch.setattr(partition_thread.subprocess, "Popen", FakePopen)
    FakePopen.calls = []
    partition_thread.guard = guard
    yield partition_thread
    del partition_thread.guard


@pytest.fixture
def export_config(tmp_path):
    """Export configuration with an existing master .ma file."""
    (tmp_path / "SK_Test.ma").write_text("//Maya ASCII scene\n")
    return {
        "geo_roots": ["Body_Geo"],
        "joint_root": "root",
        "file_path": str(tmp_path),
        "file_name": "SK_Test",
        "use_partitions": False,
    }


def run_thread(thread):
    """Run a PartitionThread on its own thread, return the completed args.

    Args:
        thread (PartitionThread): The thread to run.

    Returns:
        list: The (export_config, success) emitted by the completed signal.
    """
    from mgear.vendor.Qt import QtCore

    results = []
    thread.completed.connect(
        lambda config, success: results.append((config, success)),
        QtCore.Qt.DirectConnection,
    )
    thread.start()
    assert thread.wait(30000), "PartitionThread did not finish"
    return results


def test_export_runs_without_maya_commands_in_thread(
    partition_thread, export_config
):
    """The export succeeds on a QThread without calling any Maya command."""
    thread = partition_thread.PartitionThread(export_config)

    results = run_thread(thread)

    assert partition_thread.guard.thread_calls == []
    assert results == [(export_config, True)]
    assert len(FakePopen.calls) == 1


def test_export_launches_maya_batch_for_os(partition_thread, export_config):
    """The batch command is mayabatch on Windows and maya -batch elsewhere."""
    thread = partition_thread.PartitionThread(export_config)

    run_thread(thread)

    args, kwargs = FakePopen.calls[0]
    maya_bin = os.path.normpath(os.path.join(os.environ["MAYA_LOCATION"], "bin"))
    if os.name == "nt":
        assert kwargs["shell"] is True
        assert args.startswith('"{}'.format(os.path.join(maya_bin, "maya")))
        assert " -batch -script " in args
    else:
        assert kwargs["shell"] is False
        assert args[0].endswith(os.path.join("bin", "maya"))
        assert args[1:3] == ["-batch", "-script"]


def test_export_fails_without_master_file(partition_thread, export_config):
    """The export stops before launching Maya when the master file is missing."""
    os.remove(os.path.join(export_config["file_path"], "SK_Test.ma"))
    thread = partition_thread.PartitionThread(export_config)

    results = run_thread(thread)

    assert results == [(export_config, False)]
    assert FakePopen.calls == []


def test_init_data_saves_master_file(partition_thread, tmp_path):
    """init_data saves the master .ma and keeps the current scene name."""
    from maya import cmds

    cmds.file(new=True, force=True)
    scene_path = (tmp_path / "work.ma").as_posix()
    cmds.file(rename=scene_path)
    config = {"file_path": str(tmp_path), "file_name": "SK_Test.fbx"}
    thread = partition_thread.PartitionThread(config)

    thread.init_data()

    assert (tmp_path / "SK_Test.ma").is_file()
    assert cmds.file(query=True, sceneName=True) == scene_path
    cmds.file(new=True, force=True)
