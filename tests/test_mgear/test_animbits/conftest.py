"""Fixtures shared by the Spring Manager tests."""

import os

import pytest

_PLATFORMS = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        os.pardir,
        os.pardir,
        "release",
        "platforms",
    )
)


@pytest.fixture
def scene(run_with_maya_standalone, setup_path):
    """New scene, playback from 1 to 30."""
    from maya import cmds

    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=1, maxTime=30)
    return cmds


@pytest.fixture
def bdn(scene):
    """The Bone Dynamics backend, skipped without the plug-in."""
    from mgear.animbits.spring_manager.backends import get_backend

    backend = get_backend("bone_dynamics")
    if not backend.is_available():
        pytest.skip("boneDynamicsNode plug-in not available")
    return backend


@pytest.fixture
def solvers(run_with_maya_standalone, setup_path):
    """The mgear_solvers plug-in of this repository, in a new scene.

    The plug-in built for the running Maya in ``release/platforms`` is
    loaded first, so tests run against the repository build.
    """
    from maya import cmds

    if not cmds.pluginInfo("mgear_solvers", query=True, loaded=True):
        version = cmds.about(majorVersion=True)
        path = os.path.join(
            _PLATFORMS, version, "windows", "x64", "plug-ins", "mgear_solvers.mll"
        )
        try:
            cmds.loadPlugin(path if os.path.exists(path) else "mgear_solvers")
        except RuntimeError:
            pytest.skip("mgear_solvers plug-in not available")
    cmds.file(new=True, force=True)
    return cmds
