"""Fixtures shared by the Spring Manager tests."""

import pytest


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
