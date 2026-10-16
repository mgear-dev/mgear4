"""Shifter guide read and export tests

Reading a guide from the scene (``setFromHierarchy``) and exporting it
(``get_guide_template_dict``) must give the same template dictionary as
before the guide read performance change. The expected dictionaries are
stored gzipped in ``data/``. To record them again with the current code::

    MGEAR_UPDATE_GUIDE_GOLDEN=1 mayapy -m pytest tests/test_mgear/test_shifter/test_guide_read.py
"""

import gzip
import json
import os

import pytest

DATA = os.path.join(os.path.dirname(__file__), "data")
UPDATE_ENV = "MGEAR_UPDATE_GUIDE_GOLDEN"
TEMPLATES = ("biped.sgt", "EPIC_metahuman_y_up.sgt")
# Rounding keeps the comparison stable across Maya versions.
DECIMALS = 6


def normalize(value):
    """Return a JSON-compatible copy of a value with rounded floats.

    Args:
        value (object): The value to normalize (dict, list, float...).

    Returns:
        object: The normalized value.
    """
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if isinstance(value, float):
        rounded = round(value, DECIMALS)
        return 0.0 if rounded == 0 else rounded
    return value


def first_difference(expected, actual, path="root"):
    """Return the path of the first difference between two values.

    Args:
        expected (object): The expected value.
        actual (object): The actual value.
        path (str, optional): Path of the values, used in the message.

    Returns:
        str: A message naming the first difference, or None if equal.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                return "{}[{!r}] missing".format(path, key)
            if key not in expected:
                return "{}[{!r}] unexpected".format(path, key)
            diff = first_difference(
                expected[key], actual[key], "{}[{!r}]".format(path, key)
            )
            if diff:
                return diff
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return "{} length {} != {}".format(path, len(expected), len(actual))
        for index, (exp, act) in enumerate(zip(expected, actual)):
            diff = first_difference(exp, act, "{}[{}]".format(path, index))
            if diff:
                return diff
        return None
    if expected != actual:
        return "{}: {!r} != {!r}".format(path, expected, actual)
    return None


def check_golden(name, data):
    """Compare data with a stored golden file, or record it.

    Args:
        name (str): Golden file name, without extension.
        data (object): The data to compare (normalized here).
    """
    path = os.path.join(DATA, name + ".json.gz")
    data = normalize(data)
    if os.environ.get(UPDATE_ENV):
        os.makedirs(DATA, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True)
        pytest.skip("Recorded {}".format(path))
    with gzip.open(path, "rt", encoding="utf-8") as f:
        expected = json.load(f)
    diff = first_difference(expected, data)
    assert diff is None, diff


@pytest.fixture
def import_template(rig_plugins, setup_path, monkeypatch):
    """Function importing a bundled guide template in a new scene.

    Returns:
        callable: Called with the template file name, returns the guide
            root node.
    """
    from maya import cmds

    import mgear
    import mgear.pymaya as pm
    from mgear.shifter import io

    monkeypatch.setattr(mgear, "log", lambda *args, **kwargs: None)

    def load(template):
        cmds.file(new=True, force=True)
        io.import_sample_template(template)
        return pm.PyNode("guide")

    return load


@pytest.mark.parametrize("template", TEMPLATES)
def test_read_and_export_unchanged(import_template, template):
    from mgear import shifter

    guide_root = import_template(template)
    rig = shifter.Rig()
    rig.guide.setFromHierarchy(guide_root)
    assert rig.guide.valid

    data = rig.guide.get_guide_template_dict()
    check_golden("guide_read_" + os.path.splitext(template)[0], data)


@pytest.mark.parametrize("template", TEMPLATES)
def test_control_buffer_data_unchanged(import_template, template):
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
