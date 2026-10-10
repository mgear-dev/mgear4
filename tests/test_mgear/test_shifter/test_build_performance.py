"""Shifter build performance regression tests

The default tests count operations instead of measuring time, so they are
stable across machines. The wall-clock test only runs when the
``MGEAR_PERF_BIPED_BASELINE`` environment variable holds the biped build time
in seconds measured before the build performance change on the same machine,
e.g. with ``tests/perf/profile_build.py biped.sgt --no-profile``.
"""

import builtins
import os
import time

import pytest

# Nodes and joints the biped build creates (the default scene nodes differ
# between Maya versions, so they are not counted).
BIPED_BUILD_NODES = 2094
BIPED_JOINTS = 124
# A biped build made 610,044 hasattr calls before the pymaya string-method
# shims moved to the class, and about 3,900 after.
BIPED_MAX_HASATTR = 10000
PERF_BASELINE_ENV = "MGEAR_PERF_BIPED_BASELINE"


@pytest.fixture
def biped_guide(rig_plugins, setup_path, monkeypatch):
    """The bundled biped guide template, imported in a new scene."""
    from maya import cmds

    import mgear
    from mgear.shifter import io

    cmds.file(new=True, force=True)
    io.import_sample_template("biped.sgt")
    cmds.select("guide")
    monkeypatch.setattr(mgear, "log", lambda *args, **kwargs: None)
    return cmds


def test_biped_build_output_and_cost(biped_guide, monkeypatch, count_calls):
    from mgear import shifter

    before = len(biped_guide.ls())
    with monkeypatch.context() as patch:
        calls = count_calls(builtins, "hasattr", patcher=patch)
        shifter.Rig().buildFromSelection()

    assert len(biped_guide.ls()) - before == BIPED_BUILD_NODES
    assert len(biped_guide.ls(type="joint")) == BIPED_JOINTS
    assert len(calls) < BIPED_MAX_HASATTR


@pytest.mark.perf
def test_biped_build_time(biped_guide):
    baseline = os.environ.get(PERF_BASELINE_ENV)
    if not baseline:
        pytest.skip("Set {} to run the timing test".format(PERF_BASELINE_ENV))

    from mgear import shifter

    start = time.perf_counter()
    shifter.Rig().buildFromSelection()
    elapsed = time.perf_counter() - start

    assert elapsed < 0.7 * float(baseline)
