"""Tests for mgear.core.dagmenu, the mGear right-click viewport menu."""

import pytest

# Labels of the control menu on the shifter_rig fixture, dividers excluded.
# Every control of that rig shares global_C0_ctl as UI host, so they all get
# the same menu.
CONTROL_MENU_LABELS = (
    "Select host",
    "Switch arm to Fk",
    "Switch arm to Fk + Key",
    "Range switch",
    "Select child controls",
    "Reset",
    "Reset Option",
    "Reset Option/Reset all",
    "Reset Option/Reset all below",
    "Reset Option/Reset To BindPose",
    "Reset Option/Reset All SRT",
    "Reset Option/Reset translate",
    "Reset Option/Reset rotate",
    "Reset Option/Reset scale",
    "Mirror",
    "Mirror all below",
    "Flip",
    "Flip all below",
    "Rotate Order switch",
    "Rotate Order switch/xyz",
    "Rotate Order switch/yzx",
    "Rotate Order switch/zxy",
    "Rotate Order switch/xzy",
    "Rotate Order switch/yxz",
    "Rotate Order switch/zyx",
    "Parent arm ik",
    "Parent arm ik/control_C0_ctl",
    "Parent arm ik/control_C1_ctl",
    "Parent arm ik/++ Space Transfer ++",
    "Parent control ik",
    "Parent control ik/control_C0_ctl",
    "Parent control ik/arm_C0_root",
    "Parent control ik/++ Space Transfer ++",
    "Select all controls",
    "Keyframe child controls",
    "X-Ray CTL Toggle",
)

GUIDE_MENU_LABELS = (
    "Settings",
    "Build From Selection",
    "Duplicate",
    "Duplicate Symme",
    "Guide Manager",
    "Export Guide From Selection",
    "Update Guide",
    "Update Selected Components Type",
    "Reload Components",
    "X-Ray Guide Toggle",
)


@pytest.mark.parametrize(
    "control",
    ("arm_C0_fk0_ctl", "arm_C0_ik_ctl", "control_C1_ctl", "control_C0_ctl"),
)
def test_control_menu_snapshot(dagmenu, shifter_rig, menu_recorder, control):
    cmds = shifter_rig
    cmds.select(control)
    dagmenu.mgear_dagmenu_fill("menu", cmds.ls(control, long=True)[0])
    assert tuple(menu_recorder.paths(dividers=False)) == CONTROL_MENU_LABELS


def test_guide_menu_snapshot(dagmenu, shifter_rig, menu_recorder):
    cmds = shifter_rig
    cmds.select("|guide|control_C0_root")
    dagmenu.mgear_dagmenu_guide_fill("menu", "|guide|control_C0_root")
    assert tuple(menu_recorder.paths(dividers=False)) == GUIDE_MENU_LABELS


# =============================================================================
# registry
# =============================================================================


class FakeBuilder(object):
    """Builder recording labels and section starts."""

    def __init__(self):
        self.calls = []

    def divider(self):
        self.calls.append("|")

    def item(self, label, command=None, image=None, **kwargs):
        self.calls.append(label)


def _labels_section(*labels):
    def build(builder, ctx):
        for label in labels:
            builder.item(label)

    return build


@pytest.fixture
def registry(setup_path):
    """An empty dag menu Registry."""
    from mgear.core.dagmenu.registry import Registry

    return Registry()


def test_registry_order(registry):
    registry.register_section("ctx", "b", 200, _labels_section("B"))
    registry.register_section("ctx", "a", 100, _labels_section("A"))
    registry.register_section("ctx", "c", 650, _labels_section("C"))
    registry.register_section("other", "x", 1, _labels_section("X"))
    builder = FakeBuilder()
    registry.build(builder, None, "ctx")
    assert builder.calls == ["|", "A", "|", "B", "|", "C"]


def test_registry_poll_hides_section(registry):
    registry.register_section("ctx", "a", 100, _labels_section("A"))
    registry.register_section(
        "ctx", "b", 200, _labels_section("B"), poll=lambda ctx: False
    )
    builder = FakeBuilder()
    registry.build(builder, None, "ctx")
    assert builder.calls == ["|", "A"]


def test_registry_replace_and_unregister(registry):
    registry.register_section("ctx", "a", 100, _labels_section("Old"))
    registry.register_section("ctx", "a", 100, _labels_section("New"))
    builder = FakeBuilder()
    registry.build(builder, None, "ctx")
    assert builder.calls == ["|", "New"]

    registry.unregister_section("ctx", "a")
    builder = FakeBuilder()
    registry.build(builder, None, "ctx")
    assert builder.calls == []


def test_registry_failing_section_is_isolated(registry):
    def broken(builder, ctx):
        raise RuntimeError("broken section")

    registry.register_section("ctx", "a", 100, _labels_section("A"))
    registry.register_section("ctx", "b", 200, broken)
    registry.register_section(
        "ctx", "c", 300, _labels_section("C"), poll=lambda ctx: 1 / 0
    )
    registry.register_section("ctx", "d", 400, _labels_section("D"))
    builder = FakeBuilder()
    registry.build(builder, None, "ctx")
    assert [c for c in builder.calls if c != "|"] == ["A", "D"]


def test_registry_detect_priority(registry):
    registry.register_context("low", lambda ctx: True, priority=1)
    registry.register_context("high", lambda ctx: True, priority=10)
    registry.register_context("none", lambda ctx: False, priority=100)
    assert registry.detect(None) == "high"


def test_registry_detect_no_match(registry):
    registry.register_context("none", lambda ctx: False)
    registry.register_context("broken", lambda ctx: 1 / 0, priority=5)
    assert registry.detect(None) is None


# =============================================================================
# builder dividers
# =============================================================================


def _check_dividers(paths):
    """Assert no leading, trailing or consecutive dividers in each menu."""
    menus = {}
    for path in paths:
        parent, _, label = path.rpartition("/")
        menus.setdefault(parent, []).append(label)
    for parent, labels in menus.items():
        assert labels[0] != "---", parent
        assert labels[-1] != "---", parent
        for first, second in zip(labels, labels[1:]):
            assert not (first == "---" and second == "---"), parent


def test_builder_dividers(setup_path, menu_recorder):
    from mgear.core.dagmenu.builder import MenuBuilder

    builder = MenuBuilder("menu")
    builder.divider()
    builder.divider()
    builder.divider()
    builder.item("A")
    builder.divider()
    builder.divider()
    builder.item("B")
    with builder.submenu("Sub") as sub:
        sub.divider()
        sub.item("C")
        sub.divider()
    builder.divider()
    builder.divider()
    assert menu_recorder.paths() == ["A", "---", "B", "Sub", "Sub/C"]


def test_builder_command_ignores_maya_args(setup_path, menu_recorder):
    from mgear.core.dagmenu.builder import MenuBuilder

    calls = []
    MenuBuilder("menu").item("A", lambda: calls.append(1))
    menu_recorder.entry("A")["command"](False)
    assert calls == [1]


# =============================================================================
# registration API on the rig
# =============================================================================


@pytest.fixture
def clean_registry(dagmenu):
    """Remove the test sections and contexts after the test."""
    yield dagmenu
    dagmenu.unregister_section("control", "my_tool")
    dagmenu.unregister_section("joint", "joint_tool")
    dagmenu.REGISTRY.unregister_context("joint")


def test_register_section_order(clean_registry, shifter_rig, menu_recorder):
    dagmenu = clean_registry
    dagmenu.register_section(
        "control",
        "my_tool",
        650,
        lambda builder, ctx: builder.item("My Tool", lambda: None),
    )
    shifter_rig.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "arm_C0_fk0_ctl")
    paths = menu_recorder.paths(dividers=False)
    index = paths.index("My Tool")
    assert paths[index - 1] == "Rotate Order switch/zyx"
    assert paths[index + 1] == "Parent arm ik"


def test_register_context(clean_registry, shifter_rig, menu_recorder):
    dagmenu = clean_registry
    cmds = shifter_rig
    dagmenu.register_context(
        "joint", lambda ctx: cmds.nodeType(ctx.node) == "joint", priority=10
    )
    dagmenu.register_section(
        "joint",
        "joint_tool",
        100,
        lambda builder, ctx: builder.item("Joint Tool", lambda: None),
    )
    joint = cmds.createNode("joint", name="test_jnt")
    assert dagmenu.build_menu("menu", joint) == "joint"
    assert menu_recorder.paths() == ["Joint Tool"]


def test_no_context_for_plain_node(dagmenu, shifter_rig, menu_recorder):
    cube = shifter_rig.polyCube(name="plain_cube")[0]
    assert dagmenu.build_menu("menu", cube) is None
    assert menu_recorder.paths() == []


def test_control_menu_has_clean_dividers(dagmenu, shifter_rig, menu_recorder):
    shifter_rig.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "arm_C0_fk0_ctl")
    _check_dividers(menu_recorder.paths())


def test_guide_menu_has_clean_dividers(dagmenu, shifter_rig, menu_recorder):
    shifter_rig.select("|guide|control_C0_root")
    dagmenu.mgear_dagmenu_guide_fill("menu", "|guide|control_C0_root")
    _check_dividers(menu_recorder.paths())


def test_menu_context_arm_fk(dagmenu, shifter_rig):
    from mgear.core.dagmenu.context import MenuContext

    ctx = MenuContext("arm_C0_fk0_ctl", selection=["arm_C0_fk0_ctl"])
    assert ctx.ui_host == "global_C0_ctl"
    assert ctx.ikfk_attrs == [("arm_blend", "_blend")]
    assert ctx.space_attrs == [
        ("global_C0_ctl", "arm_ikref"),
        ("global_C0_ctl", "control_ikref"),
    ]
    assert ctx.rig_root == "rig"
    assert "arm_C0_fk1_ctl" in ctx.child_controls
    assert "arm_C0_ik_ctl" in ctx.all_controls


# =============================================================================
# Maya override
# =============================================================================


@pytest.fixture
def maya_menus(dagmenu, monkeypatch):
    """Fake Maya menus, as Maya UI is not available in batch.

    Returns:
        dict: Menu name to post menu command, plus the evaluated MEL in
            "__mel__" and the cleared menus in "__cleared__".
    """
    from maya import cmds

    menus = {
        "MayaWindow|dagMenu": "buildObjectMenuItemsNow MayaWindow|dagMenu",
        "MayaWindow|otherMenu": "otherCommand",
        "__mel__": [],
        "__cleared__": [],
    }
    prefix = 'menu -edit -postMenuCommand "'

    def menu(name, query=False, edit=False, **kwargs):
        if query:
            return menus[name]
        if edit and "postMenuCommand" in kwargs:
            menus[name] = kwargs["postMenuCommand"]
        if edit and kwargs.get("deleteAllItems"):
            menus["__cleared__"].append(name)

    def eval_mel(command):
        menus["__mel__"].append(command)
        if command.startswith(prefix):
            mel_command, _, name = command[len(prefix) :].partition('"')
            menus[name] = mel_command

    monkeypatch.setattr(
        cmds,
        "lsUI",
        lambda **kwargs: ["MayaWindow|dagMenu", "MayaWindow|otherMenu"],
    )
    monkeypatch.setattr(cmds, "menu", menu)
    monkeypatch.setattr(dagmenu.mel, "eval", eval_mel)
    monkeypatch.setattr(cmds, "optionVar", lambda **kwargs: None)
    return menus


def test_toggle_restores_maya_menu(dagmenu, maya_menus):
    from functools import partial

    dagmenu.run(True)
    command = maya_menus["MayaWindow|dagMenu"]
    assert isinstance(command, partial)
    assert command.func is dagmenu.mgear_dagmenu_callback
    assert maya_menus["MayaWindow|otherMenu"] == "otherCommand"

    dagmenu.run(False)
    assert (
        maya_menus["MayaWindow|dagMenu"] == "buildObjectMenuItemsNow MayaWindow|dagMenu"
    )


def test_callback_builds_control_menu(dagmenu, shifter_rig, menu_recorder, maya_menus):
    shifter_rig.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_callback("dagMenu", "MayaWindow")
    assert maya_menus["__cleared__"] == ["dagMenu"]
    assert tuple(menu_recorder.paths(dividers=False)) == CONTROL_MENU_LABELS
    assert maya_menus["__mel__"] == []


def test_callback_falls_back_to_maya(dagmenu, shifter_rig, menu_recorder, maya_menus):
    cmds = shifter_rig
    cmds.select(cmds.polyCube(name="plain_cube")[0])
    dagmenu.mgear_dagmenu_callback("dagMenu", "MayaWindow")
    assert maya_menus["__mel__"] == ["buildObjectMenuItemsNow dagMenu"]
    assert maya_menus["__cleared__"] == []
    assert menu_recorder.paths() == []


def test_legacy_fill_matches_build_menu(dagmenu, shifter_rig, menu_recorder):
    shifter_rig.select("control_C1_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "control_C1_ctl")
    legacy = menu_recorder.paths()
    menu_recorder.clear()
    assert dagmenu.build_menu("menu", "control_C1_ctl") == "control"
    assert menu_recorder.paths() == legacy


def test_import_does_not_load_shifter(scripts_path):
    import subprocess
    import sys

    code = (
        "import sys\n"
        "sys.path.insert(0, {!r})\n"
        "import maya.standalone\n"
        "maya.standalone.initialize(name='python')\n"
        "import mgear.core.dagmenu\n"
        "loaded = [m for m in ('mgear.shifter', "
        "'mgear.compatible.compatible_comp_dagmenu') if m in sys.modules]\n"
        "print('LOADED=' + ','.join(loaded))\n"
    ).format(scripts_path)
    output = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
    ).stdout
    lines = [line for line in output.splitlines() if line.startswith("LOADED=")]
    assert lines == ["LOADED="]


# =============================================================================
# bug fix regressions
# =============================================================================


def test_ikfk_switch_restores_blend_between_components(
    dagmenu, shifter_rig, monkeypatch
):
    from mgear.core import anim_utils
    from mgear.core.dagmenu.sections import control

    cmds = shifter_rig
    cmds.setAttr("global_C0_ctl.arm_blend", 0.0)
    component = (
        {
            "ik_control": "arm_C0_ik_ctl",
            "pole_vector": "arm_C0_upv_ctl",
            "ik_rot": None,
        },
        ["arm_C0_fk0_ctl", "arm_C0_fk1_ctl", "arm_C0_fk2_ctl"],
    )
    monkeypatch.setattr(
        anim_utils,
        "get_ikfk_components",
        lambda ui_host, attr: ([], {}, [component, component]),
    )
    seen = []

    def fake_match(**kwargs):
        # the real match switches the blend, as a match would
        seen.append(cmds.getAttr("global_C0_ctl.arm_blend"))
        cmds.setAttr("global_C0_ctl.arm_blend", 1.0)

    monkeypatch.setattr(anim_utils, "ikFkMatch_with_namespace", fake_match)
    control.switch_ikfk("global_C0_ctl", "arm_blend")
    assert seen == [0.0, 0.0]


def test_xray_uses_clicked_control(dagmenu, shifter_rig, menu_recorder):
    cmds = shifter_rig
    cmds.setAttr("rig.ctl_x_ray", False)
    cmds.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "arm_C0_fk0_ctl")
    command = menu_recorder.entry("X-Ray CTL Toggle")["command"]

    # another node selected when the command runs
    cmds.select(cmds.polyCube(name="plain_cube")[0])
    command(False)
    assert cmds.getAttr("rig.ctl_x_ray") is True

    cmds.select(clear=True)
    command(False)
    assert cmds.getAttr("rig.ctl_x_ray") is False


def test_space_attrs_must_be_enum(dagmenu, shifter_rig, menu_recorder):
    cmds = shifter_rig
    cmds.addAttr(
        "arm_C0_fk0_ctl", longName="myPref", attributeType="float", keyable=True
    )
    cmds.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "arm_C0_fk0_ctl")
    paths = menu_recorder.paths(dividers=False)
    assert not [p for p in paths if "myP" in p]
    # the float attribute doesn't hide the ui host switches
    assert "Switch arm to Fk" in paths
    assert "Parent arm ik" in paths


def test_switch_space_command(dagmenu, shifter_rig, menu_recorder):
    cmds = shifter_rig
    cmds.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "arm_C0_fk0_ctl")
    matrix = cmds.xform("arm_C0_ik_ctl", query=True, matrix=True, worldSpace=True)
    menu_recorder.entry("Parent arm ik/control_C1_ctl")["command"](False)
    assert cmds.getAttr("global_C0_ctl.arm_ikref") == 1
    new_matrix = cmds.xform("arm_C0_ik_ctl", query=True, matrix=True, worldSpace=True)
    assert new_matrix == pytest.approx(matrix, abs=1e-4)


def test_reset_commands(dagmenu, shifter_rig, menu_recorder):
    cmds = shifter_rig
    cmds.setAttr("arm_C0_fk0_ctl.translateX", 2.0)
    cmds.setAttr("arm_C0_fk0_ctl.rotateY", 30.0)
    cmds.select("arm_C0_fk0_ctl")
    dagmenu.mgear_dagmenu_fill("menu", "arm_C0_fk0_ctl")
    menu_recorder.entry("Reset Option/Reset rotate")["command"](False)
    assert cmds.getAttr("arm_C0_fk0_ctl.rotateY") == pytest.approx(0.0)
    assert cmds.getAttr("arm_C0_fk0_ctl.translateX") == pytest.approx(2.0)
    menu_recorder.entry("Reset")["command"](False)
    assert cmds.getAttr("arm_C0_fk0_ctl.translateX") == pytest.approx(0.0)
