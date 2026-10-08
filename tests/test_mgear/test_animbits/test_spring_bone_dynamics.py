"""mgear.animbits.spring_manager Bone Dynamics backend, proxies and solver test"""

import sys

import pytest

from spring_helpers import build_skirt
from spring_helpers import build_tail_rig
from spring_helpers import simulate


def _flat(sampled):
    return [
        value for frame in sorted(sampled) for item in sampled[frame] for value in item
    ]


# ---------------------------------------------------------------------
# Proxies and solver node (no boneDynamicsNode needed)
# ---------------------------------------------------------------------
def test_proxy_follows_animation_at_zero_intensity(scene):
    from mgear.animbits.spring_manager import chain
    from mgear.animbits.spring_manager import proxy

    cmds = scene
    root, branches = build_skirt(cmds)
    cmds.setKeyframe(branches[1][1], attribute="tx", time=1, value=0)
    cmds.setKeyframe(branches[1][1], attribute="tx", time=10, value=1)
    controls = [root] + [control for branch in branches for control in branch]
    frames = (1, 5, 10)
    before = _flat(simulate(cmds, controls, frames, "matrix"))

    holder = cmds.createNode("transform", name="holder")
    cmds.addAttr(holder, longName="intensity", defaultValue=0)
    cmds.addAttr(holder, longName="pose", defaultValue=0)
    tree = chain.build_tree(root, proxy.control_children)
    assert [node.name for node in tree.walk()][:2] == [root, branches[0][0]]
    rig = proxy.build(tree, "skirt", holder + ".intensity", holder + ".pose")
    after = _flat(simulate(cmds, controls, frames, "matrix"))
    assert after == pytest.approx(before, abs=1e-4)
    # proxy joints: clean orients, xyz, no rotate
    for joint in list(rig["sim"].values()) + list(rig["target"].values()):
        assert cmds.getAttr(joint + ".rotateOrder") == 0
    # one section per branch bone and per bone, tips included
    assert len(rig["sections"]) == 6


def test_branch_policy_drivers(scene):
    from mgear.animbits.spring_manager import chain
    from mgear.animbits.spring_manager import proxy

    cmds = scene
    root, _ = build_skirt(cmds)
    holder = cmds.createNode("transform", name="holder")
    cmds.addAttr(holder, longName="intensity", defaultValue=1)
    cmds.addAttr(holder, longName="pose", defaultValue=0)
    tree = chain.build_tree(root, proxy.control_children)
    rig = proxy.build(
        tree, "skirt", holder + ".intensity", holder + ".pose", policy=chain.AVERAGE
    )
    constraint = rig["constraints"][root]
    # average: both branch bones (target and sim) drive the root control
    targets = cmds.parentConstraint(constraint, query=True, targetList=True)
    assert len(targets) == 4


def test_solver_defaults(scene):
    from mgear.animbits.spring_manager import constants
    from mgear.animbits.spring_manager import registry
    from mgear.animbits.spring_manager import solver

    cmds = scene
    node = solver.get_solver()
    assert solver.get_solver() == node
    assert registry.list_shared(constants.KIND_SOLVER) == [node]
    assert registry.list_springs() == []
    assert cmds.getAttr(node + ".gravity")[0] == pytest.approx((0, -980, 0))
    assert solver.get_start_frame() == 1
    cmds.currentUnit(time="ntsc")
    solver.sync_fps()
    assert cmds.getAttr(node + ".fps") == 30

    cmds.file(new=True, force=True)
    cmds.upAxis(axis="z")
    cmds.currentUnit(linear="m")
    try:
        assert solver.default_gravity() == pytest.approx((0, 0, -9.8))
    finally:
        cmds.currentUnit(linear="cm")
        cmds.upAxis(axis="y")


def test_presets_tree_data(setup_path):
    from mgear.animbits.spring_manager import chain
    from mgear.core import node_remap

    tree = chain.tree_from_data(
        {"name": "|rig|ns:a", "children": [{"name": "ns:b", "children": []}]}
    )
    data = chain.rename_tree_data(chain.tree_to_data(tree), node_remap.short_name)
    assert data == {
        "name": "a",
        "children": [{"name": "b", "children": []}],
    }


# ---------------------------------------------------------------------
# boneDynamicsNode
# ---------------------------------------------------------------------
def test_bdn_create_simulate_delete(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager import registry

    rig, controls = build_tail_rig(cmds)
    frames = list(range(1, 11))
    animated = simulate(cmds, controls, frames)
    springs = bdn.create([controls[0]], {"springGravity": 1.0})
    assert len(springs) == 1
    assert len(cmds.ls(type="boneDynamicsNode")) == 3
    simulated = simulate(cmds, controls, frames)
    # the root follows the animation, the tail lags and droops
    assert simulated[10][0] == pytest.approx(animated[10][0], abs=1e-3)
    assert simulated[10][2][1] < animated[10][2][1] - 0.1

    # zero intensity: back to the animation
    bdn.set_params(springs, {"springTotalIntensity": 0.0})
    simulated = simulate(cmds, controls, frames)
    assert _flat({10: simulated[10]}) == pytest.approx(
        _flat({10: animated[10]}), abs=1e-3
    )

    bake.delete(springs)
    assert registry.list_springs() == []
    assert not cmds.ls(type="boneDynamicsNode")
    assert not cmds.ls("*sprg*")
    assert cmds.listConnections(controls[1] + ".rz", source=True)
    assert not cmds.attributeQuery("springDamping", node=controls[0], exists=True)
    # the shared solver stays
    assert cmds.objExists("mgearSpringSolver")


def test_bdn_ramps(bdn):
    from maya import cmds

    _, controls = build_tail_rig(cmds)
    bdn.create([controls[0]], {"springDamping": 0.2, "springDampingTip": 2.0})
    nodes = sorted(cmds.ls(type="boneDynamicsNode"))
    damping = sorted(cmds.getAttr(node + ".damping") for node in nodes)
    assert damping == pytest.approx([0.2, 0.2 * (1 + 1 / 3.0), 0.2 * (1 + 2 / 3.0)])


def test_bdn_bake_preroll_and_layer(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager import solver

    _, controls = build_tail_rig(cmds)
    springs = bdn.create([controls[0]], {"springGravity": 1.0})
    assert bake.bake(springs, start=1, end=20, preroll=5, destination_layer="sim")
    assert solver.get_start_frame() == 1
    assert cmds.animLayer("sim", query=True, exists=True)
    curves = cmds.animLayer("sim", query=True, animCurves=True)
    assert any("tail2" in curve for curve in curves)
    assert not cmds.ls(type="boneDynamicsNode")


def test_bdn_target_modes(bdn):
    from maya import cmds

    _, controls = build_tail_rig(cmds)
    spring = bdn.create([controls[0]])[0]
    targets = [
        joint
        for joint in cmds.ls(type="joint", long=True)
        if "_target_" in joint and joint.endswith("tail1_ctl_bone_jnt")
    ]
    assert targets

    cmds.currentTime(1)
    bdn.set_target_mode([spring], "captured")
    bdn.capture_pose([spring])
    cmds.currentTime(10)
    captured = cmds.getAttr(targets[0] + ".rotateZ")
    assert captured == pytest.approx(0.0, abs=1e-3)

    bdn.set_target_mode([spring], "animation")
    animated = cmds.getAttr(targets[0] + ".rotateZ")
    assert animated == pytest.approx(30.0, abs=1e-3)

    bdn.set_target_mode([spring], "blend")
    cmds.setAttr(controls[0] + ".springTargetBlend", 0.5)
    assert cmds.getAttr(targets[0] + ".rotateZ") == pytest.approx(15.0, abs=0.5)
    assert bdn.target_mode(spring) == "blend"

    with pytest.raises(ValueError):
        bdn.set_target_mode([spring], "external", ["only_one"])


def test_bdn_split_wind_visualizer(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager import registry

    root, _ = build_skirt(cmds)
    springs = bdn.create([root], options={"split": True, "visualizer": True})
    assert len(springs) == 2
    visualizers = cmds.ls(type="boneDynamicsVisualizer", long=True)
    assert len(visualizers) == 4
    # tidy outliner: under the spring proxy groups, not the world
    assert all("_sprg_grp|" in shape for shape in visualizers)

    # turbulence seed: shared by default, seed + bone index per bone
    settings = springs[0].settings_node
    nodes = cmds.ls(springs[0].members, type="boneDynamicsNode")
    cmds.setAttr(settings + ".springTurbulenceSeed", 7)
    seeds = {cmds.getAttr(node + ".turbulenceSeed") for node in nodes[:2]}
    assert seeds == {7}
    cmds.setAttr(settings + ".springTurbulenceSeedPerBone", True)
    seeds = [cmds.getAttr(node + ".turbulenceSeed") for node in nodes[:2]]
    assert len(set(seeds)) == 2 and min(seeds) > 7

    wind = bdn.create_wind()
    bdn.connect_wind(springs, wind)
    node = cmds.ls(type="boneDynamicsNode")[0]
    assert cmds.listConnections(node + ".additionalForce", source=True)
    bake.delete(springs[:1])
    assert cmds.objExists(wind)
    assert len(registry.list_springs()) == 1
    bdn.set_visualizer(springs[1:], False)
    assert len(cmds.ls(type="boneDynamicsVisualizer")) == 0


def test_bdn_rig_preset_round_trip(bdn, tmp_path):
    from maya import cmds

    from mgear.animbits.spring_manager import presets
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds, "chr")
    springs = bdn.create(
        [controls[0]],
        {"springElasticity": 77.0},
        {"target_mode": "captured", "tip_length": 0.5},
    )
    path = str(tmp_path / "tail.spg")
    preset = presets.save(path, springs)
    entry = preset["springs"][0]
    assert entry["controls"][0] == "tail0_ctl"
    assert entry["options"]["tree"]["name"] == "tail0_ctl"
    assert "bone_dynamics" in preset["solver"]

    build_tail_rig(cmds, "chr2")
    created, missing = presets.apply_by_name(presets.read(path), "chr2:")
    assert missing == []
    assert len(created) == 1
    assert bdn.target_mode(created[0]) == "captured"
    assert bdn.get_params(created[0])["springElasticity"] == pytest.approx(77.0)
    assert len(created[0].controls) == 3
    assert len(registry.list_springs()) == 2


def test_bdn_never_imports_bdn(bdn):
    assert "bdn" not in sys.modules


def test_delete_members_keeps_shared_nodes(scene):
    from mgear.animbits.spring_manager import constants
    from mgear.animbits.spring_manager import registry

    cmds = scene
    shared = registry.create_network("shared", "test", [], None, kind="solver")
    owned = cmds.createNode("multiplyDivide", name="sharedOwned")
    registry.add_members(shared, [owned])
    cmds.addAttr(shared, longName="value", attributeType="double")

    control = cmds.createNode("transform", name="ctl")
    network = registry.create_network("spring", "test", [control], control)
    user = cmds.createNode("multiplyDivide", name="springUser")
    cmds.connectAttr(shared + ".value", user + ".input1X")
    cmds.connectAttr(owned + ".outputX", user + ".input2X")
    registry.add_members(network, [user])
    registry.delete_members(network)
    assert not cmds.objExists(user)
    assert cmds.objExists(shared) and cmds.objExists(owned)
    assert registry.list_shared(constants.KIND_SOLVER) == [shared]
