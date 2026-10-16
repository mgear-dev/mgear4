"""Shifter guide template merge tests: dict merge and build time templates"""

import copy
import json

import pytest

PRE_STEP = r"""import mgear.shifter.custom_step as cstp


class CustomShifterStep(cstp.customShifterMainStep):
    def setup(self):
        self.name = "add_templates"

    def run(self):
        added = self.add_guide_template(
            "arm_C0_wrist", path=r"{template}", snap=True
        )
        with open(r"{out}", "w") as f:
            f.write(str(added))
"""


def _draw_guide():
    """Draw a control_01 + arm_2jnt_01 guide in a new scene."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import guide

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    root = pm.PyNode("control_C0_root")
    guide.Rig().drawNewComponent(root, "arm_2jnt_01", showUI=False)


def _guide_dict():
    import mgear.pymaya as pm
    from mgear.shifter import io

    return io.get_guide_template_dict(pm.PyNode("guide"))


@pytest.fixture
def dicts(rig_plugins, setup_path):
    """Guide dict (control + arm) and a template dict with a control."""
    from maya import cmds

    from mgear.shifter import guide

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    template = _guide_dict()
    _draw_guide()
    return _guide_dict(), template


def _translation(matrix):
    return list(matrix[3][:3])


# Resolve ----------------------------------------------------------------------


def test_resolve_guide_element(setup_path):
    from mgear.shifter import io

    guide_dict = {
        "components_dict": {
            "arm_L0": {},
            "index_L0": {},
            "index_metacarpal_L0": {},
        }
    }
    assert io.resolve_guide_element(guide_dict, "arm_L0_wrist") == (
        "arm_L0",
        "wrist",
    )
    assert io.resolve_guide_element(guide_dict, "arm_L0_root") == (
        "arm_L0",
        "root",
    )
    assert io.resolve_guide_element(guide_dict, "index_metacarpal_L0_root") == (
        "index_metacarpal_L0",
        "root",
    )
    with pytest.raises(ValueError, match="tail_C0_root"):
        io.resolve_guide_element(guide_dict, "tail_C0_root")


# Merge ------------------------------------------------------------------------


def test_merge_whole_template(dicts):
    from mgear.shifter import io

    guide_dict, _ = dicts
    before = copy.deepcopy(guide_dict)
    template = copy.deepcopy(guide_dict)

    merged = io.merge_guide_template(guide_dict, template, "arm_C0_wrist")

    assert merged["components_list"] == [
        "control_C0",
        "arm_C0",
        "control_C1",
        "arm_C1",
    ]
    comps = merged["components_dict"]
    assert comps["control_C1"]["parent_fullName"] == "arm_C0"
    assert comps["control_C1"]["parent_localName"] == "wrist"
    assert comps["control_C1"]["param_values"]["comp_index"] == 1
    assert comps["arm_C1"]["parent_fullName"] == "control_C1"
    assert comps["arm_C1"]["param_values"]["comp_index"] == 1
    assert comps["control_C1"]["child_components"] == ["arm_C1"]
    assert "control_C1" in comps["arm_C0"]["child_components"]
    # Without snap the template positions are kept
    assert comps["control_C1"]["pos"]["root"] == pytest.approx(
        comps["control_C0"]["pos"]["root"]
    )
    # Inputs unchanged
    assert guide_dict == before
    assert template == before


def test_merge_partial(dicts):
    from mgear.shifter import io

    guide_dict, _ = dicts
    merged = io.merge_guide_template(
        guide_dict, guide_dict, "control_C0_root", partial=["arm_C0"]
    )
    assert merged["components_list"] == ["control_C0", "arm_C0", "arm_C1"]
    arm = merged["components_dict"]["arm_C1"]
    assert arm["parent_fullName"] == "control_C0"
    assert arm["parent_localName"] == "root"


def test_merge_snap(dicts):
    from mgear.shifter import io

    guide_dict, template = dicts
    wrist = _translation(guide_dict["components_dict"]["arm_C0"]["tra"]["wrist"])
    t_comp = template["components_dict"]["control_C0"]
    offset = [w - r for w, r in zip(wrist, _translation(t_comp["tra"]["root"]))]

    merged = io.merge_guide_template(guide_dict, template, "arm_C0_wrist", snap=True)
    comp = merged["components_dict"]["control_C1"]
    assert _translation(comp["tra"]["root"]) == pytest.approx(wrist)
    assert comp["pos"]["root"] == pytest.approx(wrist)
    for key, matrix in comp["tra"].items():
        expected = [v + o for v, o in zip(_translation(t_comp["tra"][key]), offset)]
        assert _translation(matrix) == pytest.approx(expected)
    for vector, t_vector in zip(comp["apos"], t_comp["apos"]):
        expected = [v + o for v, o in zip(t_vector, offset)]
        assert vector == pytest.approx(expected)


def test_merge_ctl_buffers(dicts):
    from mgear.shifter import io

    guide_dict, _ = dicts
    template = copy.deepcopy(guide_dict)

    def buffer(name):
        return {
            "shapes_names": [name + "Shape"],
            "shapes": {name + "Shape": {"points": []}},
            "crv_color": 17,
        }

    existing = "arm_C0_fk0_ctl_controlBuffer"
    guide_dict["ctl_buffers_dict"] = {
        "curves_names": [existing],
        existing: buffer(existing),
    }
    template["ctl_buffers_dict"] = copy.deepcopy(guide_dict["ctl_buffers_dict"])

    merged = io.merge_guide_template(
        guide_dict, template, "control_C0_root", partial=["arm_C0"]
    )
    buffers = merged["ctl_buffers_dict"]
    new = "arm_C1_fk0_ctl_controlBuffer"
    assert buffers["curves_names"] == [existing, new]
    assert buffers[new]["shapes_names"] == [new + "Shape"]
    assert list(buffers[new]["shapes"]) == [new + "Shape"]
    assert buffers[existing]["shapes_names"] == [existing + "Shape"]
    assert guide_dict["ctl_buffers_dict"]["curves_names"] == [existing]


def test_merge_unknown_target(dicts):
    from mgear.shifter import io

    guide_dict, template = dicts
    with pytest.raises(ValueError, match="leg_C0_root"):
        io.merge_guide_template(guide_dict, template, "leg_C0_root")


# Build time templates ---------------------------------------------------------


@pytest.fixture
def merge_step(dicts, tmp_path):
    """Write the control template and a pre step that adds it.

    Returns:
        tuple: The step path, the file the step writes its result to, and
            the guide dict of the scene guide.
    """
    guide_dict, template = dicts
    template_path = tmp_path / "control.sgt"
    template_path.write_text(json.dumps(template))
    out = tmp_path / "added.txt"
    step = tmp_path / "add_templates.py"
    step.write_text(PRE_STEP.format(template=template_path, out=out))
    return str(step), out, guide_dict


def _wrist_position(guide_dict):
    return _translation(guide_dict["components_dict"]["arm_C0"]["tra"]["wrist"])


def _stored_components(rig_node="rig"):
    from maya import cmds

    data = json.loads(cmds.getAttr(rig_node + ".guide_data"))
    return data["components_list"], data


def _world_pos(node):
    from maya import cmds

    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def test_scene_build_merge(merge_step):
    from maya import cmds

    from mgear import shifter

    step, out, guide_dict = merge_step
    cmds.setAttr("guide.doPreCustomStep", True)
    cmds.setAttr("guide.preCustomStep", step, type="string")

    for _ in range(2):
        if cmds.objExists("rig"):
            cmds.delete("rig")
        cmds.select("guide")
        shifter.Rig().buildFromSelection()
        assert out.read_text() == "True"
        assert cmds.objExists("control_C1_ctl")
        # Rebuilding doesn't pile up copies
        assert not cmds.objExists("control_C2_ctl")
        assert _world_pos("control_C1_ctl") == pytest.approx(
            _wrist_position(guide_dict), abs=1e-4
        )
        # The scene guide and the stored guide are the original guide
        guide_nodes = cmds.listRelatives("guide", allDescendents=True)
        assert "control_C1_root" not in guide_nodes
        assert _stored_components()[0] == ["control_C0", "arm_C0"]


def test_dict_build_merge(merge_step):
    from maya import cmds

    from mgear import shifter

    step, out, guide_dict = merge_step
    cmds.setAttr("guide.doPreCustomStep", True)
    cmds.setAttr("guide.preCustomStep", step, type="string")
    conf = _guide_dict()

    cmds.file(new=True, force=True)
    shifter.Rig().buildFromDict(conf)
    assert out.read_text() == "True"
    assert cmds.objExists("control_C1_ctl")
    assert _world_pos("control_C1_ctl") == pytest.approx(
        _wrist_position(guide_dict), abs=1e-4
    )
    components, stored = _stored_components()
    assert components == ["control_C0", "arm_C0"]

    # Building from the stored guide adds the template once
    cmds.file(new=True, force=True)
    shifter.Rig().buildFromDict(stored)
    assert cmds.objExists("control_C1_ctl")
    assert not cmds.objExists("control_C2_ctl")


def test_build_without_merge_unchanged(build_rig):
    from maya import cmds

    rig = build_rig()
    assert rig.source_guide_dict is None
    assert _stored_components()[0] == ["control_C0", "arm_C0"]
    assert not cmds.objExists("control_C1_ctl")


def test_post_step_call_ignored(merge_step):
    from maya import cmds

    from mgear import shifter

    step, out, _ = merge_step
    cmds.setAttr("guide.doPostCustomStep", True)
    cmds.setAttr("guide.postCustomStep", step, type="string")
    cmds.select("guide")
    shifter.Rig().buildFromSelection()
    assert out.read_text() == "False"
    assert not cmds.objExists("control_C1_ctl")


# Custom step template ---------------------------------------------------------


def test_add_guide_templates_template(setup_path, tmp_path):
    from mgear.shifter import custom_step_templates

    names = dict(custom_step_templates.get_template_names())
    assert names["add_guide_templates"] == "Add Guide Templates"
    code = custom_step_templates.get_template_content("add_guide_templates", "addHands")
    for name in ("hand_L.sgt", "hand_R.sgt", "trex.sgt"):
        (tmp_path / name).write_text("{}")

    class Builder(object):
        def __init__(self):
            self.calls = []

        def add_guide_template(self, target, **kwargs):
            self.calls.append((target, kwargs))
            return True

    builder = Builder()
    namespace = {"__file__": str(tmp_path / "addHands.py")}
    exec(compile(code, "addHands.py", "exec"), namespace)
    step = namespace["CustomShifterStep"]({"mgearBuilder": builder})
    step.setup()
    assert step.name == "addHands"
    step.run()
    assert [c[0] for c in builder.calls] == [
        "arm_L0_wrist",
        "arm_R0_wrist",
        "spine_C0_root",
    ]
    assert builder.calls[0][1]["path"] == str(tmp_path / "hand_L.sgt")
    assert builder.calls[0][1]["snap"] is True
    assert builder.calls[0][1]["partial"] is None
    # Partial example
    assert builder.calls[2][1]["partial"] == ["tail_C0"]
