"""Fixtures shared by the Shifter build tests."""

import pytest


@pytest.fixture
def build_rig(rig_plugins, setup_path):
    """Function building a small Shifter rig in a new scene.

    The guide has a ``control_C0`` root with an ``arm_C0`` (arm_2jnt_01)
    below it.

    Returns:
        callable: Called with ``data_collector_path`` (str, optional) to turn
            the data collector on and ``post_step`` (str, optional) as the
            path of a post custom step. Returns the built shifter.Rig.
    """

    def build(data_collector_path=None, post_step=None):
        from maya import cmds

        import mgear.pymaya as pm
        from mgear import shifter
        from mgear.shifter import guide

        cmds.file(new=True, force=True)
        guide.Rig().drawNewComponent(None, "control_01", showUI=False)
        root = pm.PyNode("control_C0_root")
        guide.Rig().drawNewComponent(root, "arm_2jnt_01", showUI=False)
        if data_collector_path:
            cmds.setAttr("guide.data_collector", True)
            cmds.setAttr(
                "guide.data_collector_path",
                data_collector_path,
                type="string",
            )
        if post_step:
            cmds.setAttr("guide.doPostCustomStep", True)
            cmds.setAttr("guide.postCustomStep", post_step, type="string")
        cmds.select("guide")
        rig = shifter.Rig()
        rig.buildFromSelection()
        cmds.select(clear=True)
        return rig

    return build


@pytest.fixture
def curve_data_calls(setup_path, count_calls):
    """Record the controls passed to curve.collect_curve_data.

    Only per-control calls (the component build data collection) are
    recorded. The build also makes one ``collect_curve_data(objs=[])`` call
    of its own, which is ignored.
    """
    from mgear.core import curve

    return count_calls(
        curve,
        "collect_curve_data",
        record=lambda args, kwargs: args[0] if args else None,
    )
