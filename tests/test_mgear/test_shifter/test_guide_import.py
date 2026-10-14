"""Shifter guide template import tests"""


def _guide_template():
    """Draw a control_01 + arm_2jnt_01 guide and return its template."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide
    from mgear.shifter import io

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    root = pm.PyNode("control_C0_root")
    guide.Rig().drawNewComponent(root, "arm_2jnt_01", showUI=False)
    return io.get_guide_template_dict(pm.PyNode("guide"))


def test_import_clears_selection(rig_plugins, setup_path):
    """Importing a template leaves nothing selected."""
    from maya import cmds
    from mgear.shifter import io

    conf = _guide_template()
    cmds.file(new=True, force=True)
    io.import_guide_template(conf=conf)
    assert cmds.objExists("arm_C0_root")
    assert cmds.ls(selection=True) == []


def test_partial_import_clears_selection(rig_plugins, setup_path):
    """Adding a component from a template leaves nothing selected."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import io

    conf = _guide_template()
    cmds.select("control_C0_root")
    io.import_partial_guide(
        partial="arm_C0", initParent=pm.PyNode("control_C0_root"), conf=conf
    )
    assert cmds.objExists("arm_C1_root")
    assert cmds.ls(selection=True) == []
