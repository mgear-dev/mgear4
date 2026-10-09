"""mgear.animbits.spring_manager test"""

import json
import os

import pytest


@pytest.fixture
def sm(solvers):
    """Spring Manager modules, in a new scene with mgear_solvers loaded."""
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager import constants
    from mgear.animbits.spring_manager import presets
    from mgear.animbits.spring_manager import registry
    from mgear.animbits.spring_manager.backends import get_backend

    class Modules(object):
        pass

    modules = Modules()
    modules.bake = bake
    modules.constants = constants
    modules.presets = presets
    modules.registry = registry
    modules.classic = get_backend("classic")
    return modules


def _chain(name="arm", namespace=""):
    """Build a 3 control chain along +Y, the first control keyed in tx.

    Returns:
        list: Control names.
    """
    from maya import cmds

    if namespace and not cmds.namespace(exists=namespace):
        cmds.namespace(add=namespace)
    prefix = namespace + ":" if namespace else ""
    parent = cmds.createNode("transform", name=prefix + name + "_grp")
    controls = []
    for index in range(3):
        parent = cmds.createNode(
            "transform", name="{}{}{}_ctl".format(prefix, name, index), parent=parent
        )
        if index:
            cmds.setAttr(parent + ".ty", 2)
        controls.append(cmds.ls(parent)[0])
    cmds.setKeyframe(controls[0], attribute="tx", time=1, value=0)
    cmds.setKeyframe(controls[0], attribute="tx", time=10, value=10)
    return controls


# ---------------------------------------------------------------------
# Presets: pure helpers
# ---------------------------------------------------------------------
def test_param_tooltips(sm):
    from mgear.animbits.spring_manager.backends import get_backends

    for backend in get_backends():
        for spec in backend.param_specs():
            assert spec.tooltip, (backend.name, spec.attr)


def test_namespace_helpers(sm):
    from mgear.core import node_remap

    presets = sm.presets
    assert node_remap.get_namespace("|grp|chr:sub:arm_ctl") == "chr:sub:"
    assert node_remap.get_namespace("arm_ctl") == ""
    assert node_remap.add_namespace("arm_ctl", "chr") == "chr:arm_ctl"
    assert node_remap.add_namespace("arm_ctl", "chr:") == "chr:arm_ctl"
    assert node_remap.add_namespace("arm_ctl", "") == "arm_ctl"
    assert node_remap.common_namespace([]) == (None, [])
    assert node_remap.common_namespace(["a:x", "|g|a:y"]) == ("a:", ["a:"])
    assert node_remap.common_namespace(["b:x", "a:y"]) == (None, ["a:", "b:"])
    entry = {"controls": ["arm_ctl"]}
    assert presets.resolve_controls(entry, "chr2") == ["chr2:arm_ctl"]
    assert presets.resolve_controls(entry, "") == ["arm_ctl"]


def test_preset_v1_conversion(sm):
    v1 = {
        "nodes": ["ns:arm_L0_fk0_ctl", "ns:tail_ctl"],
        "namespaces": ["ns:"],
        "configs": {
            "ns:arm_L0_fk0_ctl": {
                "node": "arm_L0_fk0_ctl",
                "namespace": "ns:",
                "direction": "x",
                "springRotationalDamping": 0.2,
                "springSetupMembers": [None],
            },
            "ns:tail_ctl": {"direction": "ambiguous"},
        },
    }
    preset = sm.presets.normalize(v1)
    assert preset["version"] == 2
    assert preset["namespaces"] == ["ns"]
    first, second = preset["springs"]
    assert first["backend"] == "classic"
    assert first["controls"] == ["arm_L0_fk0_ctl"]
    assert first["options"]["direction"] == "x"
    assert first["params"] == {"springRotationalDamping": 0.2}
    assert second["options"]["direction"] == "auto"


def test_preset_unknown_block_and_invalid(sm, tmp_path):
    data = sm.presets.new_preset()
    data["foo"] = {"bar": 1}
    path = str(tmp_path / "unknown.spg")
    with open(path, "w") as stream:
        json.dump(data, stream)
    preset = sm.presets.read(path)
    assert preset["foo"] == {"bar": 1}
    assert sm.presets.apply_by_name(preset) == ([], [])

    with pytest.raises(ValueError):
        sm.presets.normalize({"something": 1})


def test_match_values_and_libraries(sm, tmp_path):
    presets = sm.presets
    single = presets.build_preset(
        [
            {
                "backend": "classic",
                "controls": [],
                "params": {"springRigScale": 4.0, "a": 1.0},
            }
        ]
    )
    targets = [("classic", ["x"]), ("classic", ["y"])]
    assert presets.match_values(single, targets) == [{"a": 1.0}, {"a": 1.0}]
    # entries of another solver are ignored
    assert presets.match_values(single, [("other", ["x"])]) == [{}]
    multi = presets.build_preset(
        [
            {"controls": ["ns:a_ctl"], "params": {"v": 1.0}},
            {"controls": ["b_ctl"], "params": {"v": 2.0, "msg": [None]}},
        ]
    )
    assert multi["springs"][0]["controls"] == ["a_ctl"]
    # non numeric values are never stored
    assert multi["springs"][1]["params"] == {"v": 2.0}
    assert presets.match_values(multi, [(None, ["ns2:b_ctl"]), (None, ["c_ctl"])]) == [
        {"v": 2.0},
        {},
    ]

    # libraries: missing folders give nothing, factory presets exist
    assert presets.list_presets(str(tmp_path / "missing")) == []
    names = [name for name, _ in presets.list_presets(presets.factory_folder())]
    assert "Soft" in names
    for _, path in presets.list_presets(presets.factory_folder()):
        assert presets.read(path)["springs"]


# ---------------------------------------------------------------------
# Classic backend
# ---------------------------------------------------------------------
def test_classic_create_batch_undo(sm):
    from maya import cmds

    controls = _chain()
    springs = sm.classic.create(controls)
    assert len(springs) == 3
    assert len(sm.registry.list_springs()) == 3
    network = springs[0].node
    assert cmds.getAttr(network + ".mgearSpring") == "classic"
    assert springs[0].controls == [controls[0]]

    cmds.undo()
    assert sm.registry.list_springs() == []
    assert not cmds.ls("*sprg*")
    assert not cmds.attributeQuery(
        "springTotalIntensity", node=controls[0], exists=True
    )


def test_classic_auto_direction_and_skip(sm):
    from maya import cmds

    controls = _chain()
    spring = sm.classic.create([controls[0]])[0]
    assert cmds.getAttr(spring.node + ".direction") == "y"
    # leaf control: direction from the parent
    leaf = sm.classic.create([controls[2]])[0]
    assert cmds.getAttr(leaf.node + ".direction") == "y"
    # existing spring is skipped
    assert sm.classic.create([controls[0]]) == []
    assert len(sm.registry.list_springs()) == 2


def test_classic_animation_preserved(sm):
    from maya import cmds

    controls = _chain()
    frames = (1, 5, 10)
    expected = _sample(controls[0] + ".tx", frames)
    sm.classic.create([controls[0]], params={"springTotalIntensity": 0.0})
    assert _sample(controls[0] + ".tx", frames) == pytest.approx(expected, abs=1e-3)


def test_classic_params(sm):
    from maya import cmds

    controls = _chain()
    springs = sm.classic.create(controls[:2])
    sm.classic.set_params(springs, {"springRotationalDamping": 0.2, "bad": 1})
    for spring in springs:
        assert sm.classic.get_params(spring)[
            "springRotationalDamping"
        ] == pytest.approx(0.2)
    cmds.undo()
    for spring in springs:
        assert sm.classic.get_params(spring)[
            "springRotationalDamping"
        ] == pytest.approx(0.5)

    # clamped to the range
    sm.classic.set_params(springs[:1], {"springRotationalDamping": 3.0})
    assert sm.classic.get_params(springs[0])[
        "springRotationalDamping"
    ] == pytest.approx(1.0)

    # animated parameter: keyed at the current time
    plug = controls[0] + ".springTotalIntensity"
    cmds.setKeyframe(plug, time=1, value=1.0)
    cmds.currentTime(10)
    sm.classic.set_params(springs[:1], {"springTotalIntensity": 0.5})
    assert cmds.keyframe(plug, query=True, time=(10, 10), valueChange=True) == [
        pytest.approx(0.5)
    ]


def test_classic_delete(sm):
    from maya import cmds

    controls = _chain()
    cmds.setAttr(controls[1] + ".rz", 15)
    springs = sm.classic.create(controls[:2])
    cmds.currentTime(5)
    sm.bake.delete(springs)
    assert sm.registry.list_springs() == []
    assert not cmds.ls("*sprg*")
    assert not cmds.ls(type="mgear_springNode")
    assert not cmds.ls(type="network")
    # animation and static values given back
    assert cmds.listConnections(controls[0] + ".tx", source=True)
    assert cmds.getAttr(controls[1] + ".rz") == pytest.approx(15.0)
    assert cmds.getAttr(controls[1] + ".ty") == pytest.approx(2.0)
    assert not cmds.attributeQuery("springRigScale", node=controls[0], exists=True)


# ---------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------
def test_registry_ignores_other_spring_nodes(sm):
    from maya import cmds

    controls = _chain()
    spring = sm.classic.create([controls[0]])[0]
    # an unrelated spring node, e.g. from a Shifter component
    cmds.createNode("mgear_springNode", name="shifterSpring")
    other = cmds.createNode("transform", name="uiHost")
    cmds.addAttr(other, longName="damping", attributeType="float")
    cmds.connectAttr(other + ".damping", "shifterSpring.damping")

    assert sm.registry.list_springs() == [spring]
    for member in spring.members:
        assert sm.registry.spring_from_node(member) == spring
    assert sm.registry.spring_from_node(controls[0]) == spring
    assert sm.registry.spring_from_node(other) is None


def _legacy_setup(control):
    """Build a minimal setup like the previous Spring Manager."""
    from maya import cmds

    parent = cmds.listRelatives(control, parent=True)[0]
    root = cmds.createNode("transform", name=control + "_sprg_root", parent=parent)
    driver = cmds.createNode("transform", name=control + "_sprg_driver", parent=root)
    cmds.addAttr(
        control, longName="springSetupMembers", attributeType="message", multi=True
    )
    cmds.addAttr(control, longName="springTotalIntensity", attributeType="float")
    cmds.connectAttr(root + ".message", control + ".springSetupMembers[0]")
    cmds.connectAttr(driver + ".message", control + ".springSetupMembers[1]")
    for attr in ("translateX", "translateY", "translateZ"):
        curves = cmds.listConnections(control + "." + attr, source=True) or []
        for curve in curves:
            cmds.connectAttr(curve + ".output", root + "." + attr, force=True)
            cmds.disconnectAttr(curve + ".output", control + "." + attr)
    cmds.parentConstraint(driver, control)
    return root


def test_legacy_detect_and_delete(sm):
    from maya import cmds

    controls = _chain()
    root = _legacy_setup(controls[0])
    springs = sm.registry.list_springs()
    assert len(springs) == 1 and springs[0].legacy
    assert sm.registry.spring_from_node(root) == springs[0]
    # legacy springs are hidden from the solver menu and not editable
    from mgear.animbits.spring_manager.backends import get_backends

    assert "legacy" not in [backend.name for backend in get_backends()]
    assert not springs[0].legacy or sm.presets.collect(springs)["springs"] == []

    sm.bake.delete(springs)
    assert not cmds.objExists(root)
    assert sm.registry.list_springs() == []
    assert cmds.listConnections(controls[0] + ".tx", source=True)
    assert not cmds.attributeQuery("springSetupMembers", node=controls[0], exists=True)


# ---------------------------------------------------------------------
# Presets in the scene
# ---------------------------------------------------------------------
def test_preset_round_trip_with_namespace(sm, tmp_path):
    from maya import cmds

    controls = _chain(namespace="chr")
    springs = sm.classic.create(controls[:2], options={"direction": "z"})
    sm.classic.set_params(springs, {"springRotationalDamping": 0.25})
    path = str(tmp_path / "arm.spg")
    preset = sm.presets.save(path, springs)
    assert preset["namespaces"] == ["chr"]
    assert preset["springs"][0]["controls"] == ["arm0_ctl"]
    assert "springSetupMembers" not in preset["springs"][0]["params"]

    # apply to a second character
    _chain(namespace="chr2")
    preset = sm.presets.read(path)
    created, missing = sm.presets.apply_by_name(preset, "chr2:")
    assert missing == []
    assert [s.controls for s in created] == [["chr2:arm0_ctl"], ["chr2:arm1_ctl"]]
    assert cmds.getAttr(created[0].node + ".direction") == "z"
    assert sm.classic.get_params(created[0])[
        "springRotationalDamping"
    ] == pytest.approx(0.25)

    # applying again updates instead of creating
    sm.classic.set_params(created, {"springRotationalDamping": 0.9})
    again, _ = sm.presets.apply_by_name(preset, "chr2:")
    assert again == created
    assert len(sm.registry.list_springs()) == 4
    assert sm.classic.get_params(created[0])[
        "springRotationalDamping"
    ] == pytest.approx(0.25)

    # missing controls are reported
    _, missing = sm.presets.apply_by_name(preset, "nope:")
    assert missing == ["nope:arm0_ctl", "nope:arm1_ctl"]


def test_preset_empty_save_and_apply_values(sm, tmp_path):
    controls = _chain()
    path = str(tmp_path / "empty.spg")
    assert sm.presets.save(path, []) is None
    assert not os.path.exists(path)

    springs = sm.classic.create(controls)
    soft = dict(sm.presets.list_presets(sm.presets.factory_folder()))["Soft"]
    preset = sm.presets.read(soft)
    sm.classic.set_params(springs, {"springRigScale": 3.0})
    assert sm.presets.apply_values(preset, springs) == 3
    for spring in springs:
        params = sm.classic.get_params(spring)
        assert params["springRotationalStiffness"] == pytest.approx(0.3)
        assert params["springRigScale"] == pytest.approx(3.0)


# ---------------------------------------------------------------------
# Bake
# ---------------------------------------------------------------------
def _sample(plug, frames):
    from maya import cmds

    values = []
    for frame in frames:
        cmds.currentTime(frame)
        values.append(cmds.getAttr(plug))
    return values


def test_bake_and_delete(sm):
    from maya import cmds

    controls = _chain()
    springs = sm.classic.create([controls[0]], options={"direction": "y"})
    cmds.currentTime(0)
    expected = _sample(controls[0] + ".rz", range(1, 21))
    assert sm.bake.bake(springs, start=1, end=20)
    assert sm.registry.list_springs() == []
    assert not cmds.ls("*sprg*")
    times = cmds.keyframe(controls[0] + ".rz", query=True, timeChange=True)
    assert times == [float(frame) for frame in range(1, 21)]
    # bakeResults evaluates the start frame in its own order, so the spring
    # starts from another state than the playback: the first two frames are
    # skipped, the others differ slightly until the motion settles
    assert _sample(controls[0] + ".rz", range(3, 21)) == pytest.approx(
        expected[2:], rel=0.1, abs=1.0
    )


def test_bake_preroll_and_keep(sm):
    from maya import cmds

    controls = _chain()
    cmds.setKeyframe(controls[0], attribute="tx", time=-10, value=-20)
    springs = sm.classic.create([controls[0]], options={"direction": "y"})
    assert sm.bake.bake(springs, start=1, end=10, preroll=10, delete_springs=False)
    times = cmds.keyframe(controls[0] + ".rz", query=True, timeChange=True)
    assert min(times) == 1.0
    # the preroll moved the spring before frame 1
    assert cmds.getAttr(controls[0] + ".rz", time=1) != pytest.approx(0.0)

    # kept and marked baked; baking again does nothing
    kept = sm.registry.list_springs()
    assert len(kept) == 1 and kept[0].state == "baked"
    assert not sm.bake.bake(kept, start=1, end=10)
    sm.bake.delete(kept)
    assert cmds.keyframe(controls[0] + ".rz", query=True, keyframeCount=True) == 10


# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------
def test_ui_workflow(sm, clean_settings, tmp_path):
    from maya import cmds

    from mgear.animbits.spring_manager import ui
    from mgear.core import callbackManager
    from mgear.vendor.Qt import QtCore

    controls = _chain()
    window = ui.SpringManager()
    window.solver_combo.setCurrentIndex(window.solver_combo.findData("classic"))
    try:
        # create from selection
        cmds.select(clear=True)
        window.create_springs({"direction": "auto"})
        assert sm.registry.list_springs() == []
        cmds.select(controls[:2])
        window.create_springs({"direction": "auto"})
        assert window.spring_tree.topLevelItemCount() == 2

        # Maya selection -> rows and panel
        cmds.select(controls[0])
        window.on_maya_selection_changed()
        assert len(window.selected_springs()) == 1
        assert window.params_status.text() == "Editing 1 spring(s)."

        # mixed values
        springs = sm.registry.list_springs()
        sm.classic.set_params(springs[:1], {"springRotationalDamping": 0.2})
        cmds.select(controls[:2])
        window.on_maya_selection_changed()
        assert window.param_widgets["springRotationalDamping"].isMixed()

        # a slider drag is one undo step
        widget = window.param_widgets["springRotationalStiffness"]
        widget.slider.setSliderDown(True)
        widget.sliderPressed.emit()
        for position in (600, 800, 900):
            widget.slider.setValue(position)
        widget.slider.setSliderDown(False)
        for spring in springs:
            assert sm.classic.get_params(spring)[
                "springRotationalStiffness"
            ] == pytest.approx(0.9)
        cmds.undo()
        for spring in springs:
            assert sm.classic.get_params(spring)[
                "springRotationalStiffness"
            ] == pytest.approx(0.5)

        # list -> Maya selection
        window.spring_tree.clearSelection()
        window.spring_tree.topLevelItem(1).setSelected(True)
        assert cmds.ls(selection=True) == [controls[1]]

        # generic factory preset applied to the selection
        window.library_combo.setCurrentIndex(0)
        pyqt_model = window.preset_proxy
        window.search_le.setText("soft")
        assert pyqt_model.rowCount() == 1
        window.preset_view.selectionModel().select(
            pyqt_model.index(0, 0),
            QtCore.QItemSelectionModel.ClearAndSelect,
        )
        cmds.select(controls)
        window.apply_preset()
        assert len(sm.registry.list_springs()) == 3
        for spring in sm.registry.list_springs():
            assert sm.classic.get_params(spring)[
                "springRotationalStiffness"
            ] == pytest.approx(0.3)
        # the factory library is read only
        assert not window.save_btn.isEnabled()
    finally:
        window.shutdown()
        window.deleteLater()
    namespace = window.callbacks.namespace
    assert not [
        name
        for name in callbackManager.RECORDED_CALLBACKS
        if str(namespace) in str(name)
    ]


def test_preset_types_and_files(sm, tmp_path):
    presets = sm.presets
    values = presets.build_values_preset(
        "classic", {"springRotationalDamping": 0.3}, "Soft look"
    )
    assert presets.preset_type(values) == "values"
    assert "Classic values preset" in presets.describe(values)
    assert presets.describe(values).startswith("Soft look")

    rig = presets.build_preset([{"backend": "classic", "controls": ["ns:a_ctl"]}])
    assert presets.preset_type(rig) == "rig"
    assert "a_ctl" in presets.describe(rig)

    # older files without type: derived from the stored controls
    untyped = {"version": 2, "springs": [{"controls": []}]}
    assert presets.preset_type(untyped) == "values"
    for _, path in presets.list_presets(presets.factory_folder()):
        assert presets.preset_type(presets.read(path)) == "values"

    # rename and delete move the thumbnail too
    path = presets.preset_path(str(tmp_path), "soft")
    presets.write(path, values)
    with open(presets.thumbnail_path(path), "wb") as stream:
        stream.write(b"png")
    new_path = presets.rename(path, "softer")
    assert os.path.exists(presets.thumbnail_path(new_path))
    assert not os.path.exists(presets.thumbnail_path(path))
    with pytest.raises(OSError):
        presets.write(path, values)
        presets.rename(path, "softer")
    presets.set_description(new_path, "Changed")
    assert presets.read(new_path)["description"] == "Changed"
    presets.remove(new_path)
    assert not os.path.exists(new_path)
    assert not os.path.exists(presets.thumbnail_path(new_path))


def test_arrow_param_and_capture(sm):
    from maya import cmds

    from mgear.core import utils

    controls = _chain()
    spring = sm.classic.create([controls[0]], params={"springDirectionVis": False})[0]
    assert cmds.getAttr(controls[0] + ".springDirectionVis") is False
    sm.classic.set_params([spring], {"springDirectionVis": True})
    assert sm.classic.get_params(spring)["springDirectionVis"] is True
    # display switch: not taken from values presets
    values = sm.presets.build_values_preset("classic", {"springDirectionVis": False})
    assert sm.presets.entry_values(values["springs"][0]) == {}
    # no viewport in batch mode
    assert utils.capture_active_view("unused.png") is None


def test_ui_layout_filter_and_bool(sm, clean_settings):
    from maya import cmds

    from mgear.animbits.spring_manager import ui

    controls = _chain()
    window = ui.SpringManager()
    window.solver_combo.setCurrentIndex(window.solver_combo.findData("classic"))
    try:
        cmds.select(controls)
        window.create_springs({"direction": "auto"})

        # collapsing every section shows the trailing spacer
        assert window.expander.isHidden()
        for section in window.sections:
            section.set_expanded(False)
        assert not window.expander.isHidden()
        window.springs_section.set_expanded(True)
        assert not window.expander.isHidden()
        window.presets_section.set_expanded(True)
        assert window.expander.isHidden()

        # the springs list height follows the grip, within its range
        window.spring_grip.set_target_height(220)
        assert window.spring_tree.height() == 220
        window.spring_grip.set_target_height(5)
        assert window.spring_tree.height() == window.spring_grip._minimum

        # springs filter
        window.spring_search_le.setText("arm1*")
        visible = [
            item.text(0) for item in window._items.values() if not item.isHidden()
        ]
        assert visible == ["arm1_ctl"]
        window.spring_search_le.clear()

        # check box parameter, mixed then committed
        springs = sm.registry.list_springs()
        sm.classic.set_params(springs[:1], {"springDirectionVis": False})
        cmds.select(controls)
        window.on_maya_selection_changed()
        arrow = window.param_widgets["springDirectionVis"]
        assert arrow.isMixed()
        arrow.click()
        for spring in springs:
            assert sm.classic.get_params(spring)["springDirectionVis"] is True
    finally:
        window.shutdown()
        window.deleteLater()


def test_param_value_helpers(sm):
    from mgear.animbits.spring_manager.backends import clamp
    from mgear.animbits.spring_manager.backends import values_differ

    constants = sm.constants
    vector = constants.param(
        "v", "V", (0, 0, 0), "G", minimum=-1, maximum=1, kind=constants.PARAM_VECTOR
    )
    integer = constants.param("i", "I", 5, "G", maximum=10, kind=constants.PARAM_INT)
    assert clamp(vector, (2, -3, 0.5)) == (1, -1, 0.5)
    assert clamp(integer, 7.6) == 8
    assert values_differ([0.5, 0.5]) is False
    assert values_differ([(0, 1, 0), (0, 1, 0.1)]) is True
    assert values_differ([True, False]) is True


def test_bake_to_layer_keeps_animation(sm):
    from maya import cmds

    controls = _chain()
    springs = sm.classic.create([controls[0]], options={"direction": "y"})
    assert sm.bake.bake(springs, start=1, end=10, destination_layer="springBake")
    assert sm.registry.list_springs() == []
    assert cmds.animLayer("springBake", query=True, exists=True)
    # original curve on the base layer, baked rotation in the layer
    from mgear.core import anim_utils

    base_plug = anim_utils.layer_base_plug(controls[0] + ".tx")
    assert cmds.nodeType(cmds.listConnections(base_plug, source=True)[0]).startswith(
        "animCurve"
    )
    layer_curves = cmds.animLayer("springBake", query=True, animCurves=True)
    assert any("rotate" in curve for curve in layer_curves)
    # the layer holds the simulation, not a constant value
    values = [
        value
        for curve in layer_curves
        if "rotate" in curve
        for value in cmds.keyframe(curve, query=True, valueChange=True)
    ]
    assert max(values) - min(values) > 1


def test_registry_kinds(sm):
    from maya import cmds

    controls = _chain()
    spring = sm.classic.create([controls[0]])[0]
    solver = sm.registry.create_network(
        "solver_net", "classic", [], None, kind=sm.constants.KIND_SOLVER
    )
    assert sm.registry.list_springs() == [spring]
    assert sm.registry.list_shared(sm.constants.KIND_SOLVER) == [solver]
    assert sm.registry.list_shared(sm.constants.KIND_SOLVER, "other") == []
    assert sm.registry.spring_from_node(solver) is None
    sm.bake.delete([spring])
    assert cmds.objExists(solver)


def test_ui_create_panels(sm, clean_settings):
    from mgear.animbits.spring_manager import ui
    from mgear.animbits.spring_manager import ui_panels

    window = ui.SpringManager()
    window.solver_combo.setCurrentIndex(window.solver_combo.findData("classic"))
    try:
        panel = window.create_stack.currentWidget()
        assert isinstance(panel, ui_panels.ClassicCreatePanel)
        assert window.solver_section.isHidden()
        options = []
        panel.createRequested.connect(options.append)
        panel.direction_buttons["-y"].click()
        assert options == [{"direction": "-y"}]
    finally:
        window.shutdown()
        window.deleteLater()
