"""Shifter guide read and export tests

Reading a guide from the scene (``setFromHierarchy``) and exporting it
(``get_guide_template_dict``) must give the same template dictionary as
before the guide read performance change. The expected dictionaries are
stored gzipped in ``data/`` (see the ``check_golden`` fixture). To record
them again with the current code::

    MGEAR_UPDATE_GOLDEN=1 mayapy -m pytest tests/test_mgear/test_shifter/test_guide_read.py
"""

import os

import pytest

TEMPLATES = ("biped.sgt", "EPIC_metahuman_y_up.sgt")


@pytest.mark.parametrize("template", TEMPLATES)
def test_read_and_export_unchanged(import_template, check_golden, template):
    from mgear import shifter

    guide_root = import_template(template)
    rig = shifter.Rig()
    rig.guide.setFromHierarchy(guide_root)
    assert rig.guide.valid

    data = rig.guide.get_guide_template_dict()
    check_golden("guide_read_" + os.path.splitext(template)[0], data)


@pytest.mark.parametrize("template", TEMPLATES)
def test_control_buffer_data_unchanged(import_template, check_golden, template):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.core import curve

    import_template(template)
    buffers = [
        pm.PyNode(name)
        for name in cmds.listRelatives("controllers_org", children=True)
        if name.endswith("_controlBuffer")
    ]
    assert buffers
    data = curve.collect_curve_data(objs=buffers)
    check_golden("ctl_buffers_" + os.path.splitext(template)[0], data)


def test_read_does_not_list_all_descendants(import_template, count_calls):
    from maya import cmds

    from mgear import shifter

    guide_root = import_template("biped.sgt")
    calls = count_calls(
        cmds,
        "listRelatives",
        record=lambda args, kwargs: (
            args if kwargs.get("allDescendents") or kwargs.get("ad") else None
        ),
    )
    shifter.Rig().guide.setFromHierarchy(guide_root)

    # Guide element lookups use the name lookup when names are unique.
    assert calls == []


@pytest.fixture
def spine_guide(import_template):
    """The biped ``spine_C0_root`` and an unread guide object for it.

    The spine has two FCurve parameters (``st_profile``, ``sq_profile``)
    and two colour compound parameters (``RGB_fk``, ``RGB_ik``).

    Returns:
        tuple: (root node, component guide object)
    """
    import mgear.pymaya as pm
    from mgear import shifter

    import_template("biped.sgt")
    root = pm.PyNode("spine_C0_root")
    comp_guide = shifter.Rig().guide.getComponentGuide(root.getAttr("comp_type"))
    # setFromHierarchy sets the root before reading (FCurve sampling uses it)
    comp_guide.root = root
    comp_guide.model = root.getParent(generations=-1)
    return root, comp_guide


def test_param_read_queries(spine_guide, count_calls):
    import mgear.pymaya as pm

    root, comp_guide = spine_guide
    queries = count_calls(pm, "attributeQuery")
    connections = count_calls(pm, "listConnections")
    comp_guide.setParamDefValuesFromProperty(root)

    assert queries == []
    # only the two connected FCurve parameters are queried one by one
    assert len(connections) == 2
    assert comp_guide.valid
    assert comp_guide.values["comp_name"] == "spine"
    assert len(comp_guide.values["st_profile"]) > 1


def test_param_read_connected_compound(spine_guide):
    from maya import cmds

    root, comp_guide = spine_guide
    cmds.connectAttr("persp.translate", "spine_C0_root.RGB_fk")
    # a connection on a child only doesn't make the compound connected
    child = cmds.attributeQuery("RGB_ik", node="spine_C0_root", listChildren=True)
    cmds.connectAttr("top.translateX", "spine_C0_root." + child[0])
    comp_guide.setParamDefValuesFromProperty(root)

    assert str(comp_guide.values["RGB_fk"]).split("|")[-1] == "persp"
    assert tuple(comp_guide.values["RGB_ik"]) == (0, 0.25, 1)
    assert comp_guide.paramDefs["RGB_fk"].value is None


def test_param_read_missing_parameter(spine_guide, monkeypatch):
    from maya import cmds

    import mgear

    root, comp_guide = spine_guide
    messages = []
    monkeypatch.setattr(mgear, "log", lambda *args, **kwargs: messages.append(args))
    cmds.deleteAttr("spine_C0_root.joint_rot_offset_x")
    comp_guide.setParamDefValuesFromProperty(root)

    assert not comp_guide.valid
    assert any("joint_rot_offset_x" in str(m[0]) for m in messages)


def test_locator_transforms_are_separate_copies(import_template):
    from mgear import shifter

    guide_root = import_template("biped.sgt")
    rig = shifter.Rig()
    rig.guide.setFromHierarchy(guide_root)
    comp_guide = rig.guide.components["spine_C0"]

    # symmetrize replaces the dict entries, the lists keep their own values
    assert comp_guide.tra["root"] == comp_guide.atra[0]
    assert comp_guide.tra["root"] is not comp_guide.atra[0]
    assert comp_guide.pos["root"] == comp_guide.apos[0]
    assert comp_guide.pos["root"] is not comp_guide.apos[0]


def test_export_progress_redraw_is_throttled(import_template, monkeypatch, tmp_path):
    import contextlib

    import mgear.pymaya as pm
    from mgear.core import utils
    from mgear.shifter import io

    import_template("biped.sgt")
    steps = []
    bars = []

    @contextlib.contextmanager
    def fake_progress_bar(status, max_value, interruptable=False, redraw_interval=None):
        bars.append(redraw_interval)
        yield lambda status=None: steps.append(status)

    monkeypatch.setattr(utils, "main_progress_bar", fake_progress_bar)
    pm.select("guide")
    path = str(tmp_path / "biped_export.sgt")
    io.export_guide_template(path)

    with open(path) as f:
        exported = f.read()
    assert '"components_list"' in exported
    # the bar redraws at most every 0.1s, not after each component
    assert bars == [0.1]
    # one step per component, plus the control buffer collection
    assert len(steps) == 38 + 1
    assert steps[0].startswith("Exporting: ")
