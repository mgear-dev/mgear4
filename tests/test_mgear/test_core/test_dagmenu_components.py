"""Tests for the Shifter component items of the dag menu."""

import os

import pytest

FIXTURE_TYPE = "dagmenu_fixture_01"
BROKEN_TYPE = "dagmenu_broken_01"

FIXTURE_HOOK = """
import os

LOG = os.path.join(os.path.dirname(__file__), "register.log")


def build(builder, ctx):
    builder.item("Fixture Tool", lambda: None)


def register(registry):
    with open(LOG, "a") as log_file:
        log_file.write("register\\n")
    registry.register_section("fixture_tool", build)
"""

BROKEN_HOOK = """
import os

with open(os.path.join(os.path.dirname(__file__), "import.log"), "a") as f:
    f.write("import\\n")

raise RuntimeError("broken component hook")
"""


@pytest.fixture
def components(dagmenu):
    """The dag menu components module, with empty caches."""
    from mgear.core.dagmenu import components

    components.clear_cache()
    yield components
    components.clear_cache()
    for comp_type in (FIXTURE_TYPE, BROKEN_TYPE):
        dagmenu.unregister_section("control", "{}.fixture_tool".format(comp_type))


@pytest.fixture
def component_path(components, tmp_path, monkeypatch):
    """A custom component folder with a fixture and a broken dagmenu hook.

    Returns:
        pathlib.Path: The component folder.
    """
    from mgear import shifter

    for comp_type, hook in ((FIXTURE_TYPE, FIXTURE_HOOK), (BROKEN_TYPE, BROKEN_HOOK)):
        folder = tmp_path / comp_type
        folder.mkdir()
        (folder / "__init__.py").write_text("")
        (folder / "dagmenu.py").write_text(hook)
    monkeypatch.setenv("MGEAR_SHIFTER_COMPONENT_PATH", str(tmp_path))
    monkeypatch.setattr(shifter, "_component_directories_cache", None)
    return tmp_path


def _set_comp_type(cmds, node, comp_type):
    cmds.setAttr("{}.ctl_comp_type".format(node), comp_type, type="string")


def _log_lines(path):
    if not os.path.exists(str(path)):
        return []
    with open(str(path)) as log_file:
        return log_file.read().split()


# =============================================================================
# component type
# =============================================================================


def test_new_rig_controls_have_comp_type(components, shifter_rig):
    cmds = shifter_rig
    for ctl in ("arm_C0_fk0_ctl", "arm_C0_ik_ctl", "arm_C0_upv_ctl"):
        assert cmds.getAttr(ctl + ".ctl_comp_type") == "arm_2jnt_01"
    assert cmds.getAttr("control_C1_ctl.ctl_comp_type") == "control_01"
    # guide root lookups by comp_type must not see rig controls
    assert not cmds.attributeQuery("comp_type", node="arm_C0_fk0_ctl", exists=True)


def test_comp_type_from_attribute(components, shifter_rig):
    assert components.get_comp_type("arm_C0_fk0_ctl") == "arm_2jnt_01"
    assert components.get_comp_type("global_C0_ctl") is None


def test_comp_type_guide_data_fallback(components, shifter_rig):
    cmds = shifter_rig
    cmds.deleteAttr("arm_C0_fk0_ctl.ctl_comp_type")
    cmds.deleteAttr("control_C1_ctl.ctl_comp_type")
    assert components.get_comp_type("arm_C0_fk0_ctl") == "arm_2jnt_01"
    assert components.get_comp_type("control_C1_ctl") == "control_01"


def test_comp_type_fallback_namespace(components, namespaced_rig):
    cmds = namespaced_rig
    cmds.deleteAttr("char:arm_C0_fk0_ctl.ctl_comp_type")
    assert components.get_comp_type("char:arm_C0_fk0_ctl") == "arm_2jnt_01"


def test_comp_type_fallback_longest_prefix(components, shifter_rig, monkeypatch):
    cmds = shifter_rig
    monkeypatch.setattr(
        components,
        "_get_guide_comp_types",
        lambda root: {"arm_L0": "short_type", "arm_L0_extra_L0": "long_type"},
    )
    ctl = cmds.createNode("transform", name="arm_L0_extra_L0_fk0_ctl", parent="rig")
    other = cmds.createNode("transform", name="arm_L0_fk0_ctl", parent="rig")
    lonely = cmds.createNode("transform", name="leg_L0_fk0_ctl", parent="rig")
    assert components.get_comp_type(ctl) == "long_type"
    assert components.get_comp_type(other) == "short_type"
    assert components.get_comp_type(lonely) is None


def _set_guide_data_type(cmds, comp_type):
    data = cmds.getAttr("rig.guide_data").replace('"arm_2jnt_01"', comp_type)
    cmds.setAttr("rig.guide_data", data, type="string")


def test_comp_type_cache_per_rig(components, shifter_rig):
    from mgear import shifter

    cmds = shifter_rig
    cmds.deleteAttr("arm_C0_fk0_ctl.ctl_comp_type")
    assert components.get_comp_type("arm_C0_fk0_ctl") == "arm_2jnt_01"
    # the guide data is not read again for the same rig
    _set_guide_data_type(cmds, '"arm_2jnt_99"')
    assert components.get_comp_type("arm_C0_fk0_ctl") == "arm_2jnt_01"

    # a rebuilt rig is a new node, its guide data is parsed
    cmds.delete("rig")
    cmds.select("guide")
    shifter.Rig().buildFromSelection()
    cmds.deleteAttr("arm_C0_fk0_ctl.ctl_comp_type")
    _set_guide_data_type(cmds, '"arm_2jnt_98"')
    assert components.get_comp_type("arm_C0_fk0_ctl") == "arm_2jnt_98"


# =============================================================================
# component hooks
# =============================================================================


def _right_click(dagmenu, cmds, recorder, node):
    recorder.clear()
    cmds.select(node)
    dagmenu.build_menu("menu", node)
    return recorder.paths(dividers=False)


def test_hook_adds_section_after_builtins(
    dagmenu, components, component_path, shifter_rig, menu_recorder
):
    cmds = shifter_rig
    _set_comp_type(cmds, "arm_C0_fk0_ctl", FIXTURE_TYPE)
    paths = _right_click(dagmenu, cmds, menu_recorder, "arm_C0_fk0_ctl")
    assert paths[-1] == "Fixture Tool"
    assert paths[-2] == "X-Ray CTL Toggle"


def test_hook_imported_once(
    dagmenu, components, component_path, shifter_rig, menu_recorder
):
    cmds = shifter_rig
    for ctl in ("arm_C0_fk0_ctl", "arm_C0_fk1_ctl"):
        _set_comp_type(cmds, ctl, FIXTURE_TYPE)
    for ctl in ("arm_C0_fk0_ctl", "arm_C0_fk1_ctl", "arm_C0_fk0_ctl"):
        assert "Fixture Tool" in _right_click(dagmenu, cmds, menu_recorder, ctl)
    log = component_path / FIXTURE_TYPE / "register.log"
    assert _log_lines(log) == ["register"]


def test_hook_scoped_to_component(
    dagmenu, components, component_path, shifter_rig, menu_recorder
):
    cmds = shifter_rig
    _set_comp_type(cmds, "arm_C0_fk0_ctl", FIXTURE_TYPE)
    _right_click(dagmenu, cmds, menu_recorder, "arm_C0_fk0_ctl")
    paths = _right_click(dagmenu, cmds, menu_recorder, "control_C1_ctl")
    assert "Fixture Tool" not in paths
    assert "X-Ray CTL Toggle" in paths


def test_hooks_searched_once(
    dagmenu, components, component_path, shifter_rig, menu_recorder, monkeypatch
):
    from mgear import shifter

    cmds = shifter_rig
    scans = []
    get_directories = shifter.getComponentDirectories

    def counting_get_directories():
        scans.append(1)
        return get_directories()

    monkeypatch.setattr(shifter, "getComponentDirectories", counting_get_directories)
    for _ in range(3):
        paths = _right_click(dagmenu, cmds, menu_recorder, "control_C1_ctl")
        assert "X-Ray CTL Toggle" in paths
    assert len(scans) == 1
    assert set(components.get_component_hooks()) == {FIXTURE_TYPE, BROKEN_TYPE}


def test_no_hooks_skips_comp_type(dagmenu, components, shifter_rig, monkeypatch):
    monkeypatch.setattr(components, "get_component_hooks", lambda: {})
    monkeypatch.setattr(
        components, "get_comp_type", lambda node: pytest.fail("comp type queried")
    )
    shifter_rig.select("arm_C0_fk0_ctl")
    dagmenu.build_menu("menu", "arm_C0_fk0_ctl")


def test_broken_hook(dagmenu, components, component_path, shifter_rig, menu_recorder):
    cmds = shifter_rig
    _set_comp_type(cmds, "arm_C0_fk0_ctl", BROKEN_TYPE)
    for _ in range(2):
        paths = _right_click(dagmenu, cmds, menu_recorder, "arm_C0_fk0_ctl")
        assert paths[-1] == "X-Ray CTL Toggle"
    log = component_path / BROKEN_TYPE / "import.log"
    assert _log_lines(log) == ["import"]
