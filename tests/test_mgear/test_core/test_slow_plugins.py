"""mgear.core.utils slow plug-in detection tests"""

import os

import pytest


@pytest.fixture
def utils(setup_path, monkeypatch):
    """The mgear.core.utils module, with MGEAR_SLOW_PLUGINS unset."""
    from mgear.core import utils

    monkeypatch.delenv(utils.SLOW_PLUGINS_ENV, raising=False)
    return utils


def test_default_list(utils):
    assert utils.get_slow_plugins() == ("bluePencil",)


def test_env_extends_defaults(utils, monkeypatch):
    value = "studioNodes, ,bluePencil{}otherPlugin,".format(os.pathsep)
    monkeypatch.setenv(utils.SLOW_PLUGINS_ENV, value)
    assert utils.get_slow_plugins() == ("bluePencil", "studioNodes", "otherPlugin")


def test_loaded_check(utils, blue_pencil):
    blue_pencil()
    assert utils.get_loaded_slow_plugins() == ("bluePencil",)


def test_nothing_loaded(utils):
    assert utils.get_loaded_slow_plugins(["no_such_plugin_a"]) == ()


def test_unknown_name_is_ignored(utils, blue_pencil):
    blue_pencil()
    names = ["no_such_plugin_a", "bluePencil"]
    assert utils.get_loaded_slow_plugins(names) == ("bluePencil",)


def test_message(utils):
    source = "loaded by custom step: post/import_SHAPES.py"
    message = utils.slow_plugin_message("bluePencil", source)
    assert "bluePencil" in message
    assert source in message
    assert 'cmds.unloadPlugin("bluePencil")' in message
    assert "requires" in message


def test_summary_moved_to_shifter(utils):
    """The summary and the build texts are Shifter build wording."""
    from mgear import shifter

    names = ("slow_plugins_summary", "SLOW_PLUGIN_BEFORE_BUILD", "SLOW_PLUGIN_BY_STEP")
    assert not [name for name in names if hasattr(utils, name)]
    assert shifter.SLOW_PLUGIN_BEFORE_BUILD == "loaded before the build started"


def test_is_plugin_loaded(utils, blue_pencil):
    from maya import cmds

    assert not utils.is_plugin_loaded("bluePencil")
    assert not cmds.pluginInfo("bluePencil", query=True, loaded=True)
    blue_pencil()
    assert utils.is_plugin_loaded("bluePencil")
    assert not utils.is_plugin_loaded("no_such_plugin_a")


def test_empty_names_checks_nothing(utils, blue_pencil):
    blue_pencil()
    assert utils.get_loaded_slow_plugins([]) == ()
