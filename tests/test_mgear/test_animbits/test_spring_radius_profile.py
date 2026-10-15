"""mgear.animbits.spring_manager.radius_profile test (pure logic)"""

import pytest


@pytest.fixture
def rp(setup_path):
    from mgear.animbits.spring_manager import radius_profile

    return radius_profile


# root r: a long branch l0-l1 and a short branch s0, ratios per joint
BRANCHED = [
    ("r", "l0", 0.0, 1 / 3.0),
    ("l0", "l1", 1 / 3.0, 2 / 3.0),
    ("l1", "l1_tip", 2 / 3.0, 1.0),
    ("r", "s0", 0.0, 0.5),
    ("s0", "s0_tip", 0.5, 1.0),
]


def test_paths_split_branches(rp):
    paths = rp.profile_paths(BRANCHED)
    assert sorted(paths) == [[0, 1, 2], [3, 4]]
    straight = [("a", "b", 0.0, 0.5), ("b", "b_tip", 0.5, 1.0)]
    assert rp.profile_paths(straight) == [[0, 1]]


def test_chain_joints(rp):
    joints = dict(rp.chain_joints(BRANCHED))
    assert joints["r"] == 0.0
    assert joints["s0"] == pytest.approx(0.5)
    assert joints["l1_tip"] == 1.0
    assert len(joints) == 6


def test_smoothing_reduces_neighbour_differences(rp):
    values = [1.0, 1.0, 3.0, 1.0, 1.0]

    def spread(items):
        return max(abs(b - a) for a, b in zip(items, items[1:]))

    assert rp.smooth_values(values, 0) == values
    once = rp.smooth_values(values, 1)
    four = rp.smooth_values(values, 4)
    assert spread(four) < spread(once) < spread(values)
    # short lists are kept
    assert rp.smooth_values([1.0, 2.0], 3) == [1.0, 2.0]


def test_sample_at_interpolates_and_clamps(rp):
    samples = [(0.2, 1.0), (0.6, 3.0)]
    assert rp.sample_at(samples, 0.4) == pytest.approx(2.0)
    assert rp.sample_at(samples, 0.0) == 1.0
    assert rp.sample_at(samples, 1.0) == 3.0


def test_joint_radii_branches_not_mixed(rp):
    # the long branch is thin (1), the short branch thick (3)
    samples = [
        [(0.1, 1.0), (0.2, 1.0)],
        [(0.4, 1.0), (0.6, 1.0)],
        [(0.8, 1.0), (0.9, 1.0)],
        [(0.1, 3.0), (0.4, 3.0)],
        [(0.6, 3.0), (0.9, 3.0)],
    ]
    radii = rp.joint_radii(BRANCHED, samples, passes=0)
    assert radii["l1"] == pytest.approx(1.0)
    assert radii["s0"] == pytest.approx(3.0)
    # the pivot: mean of the two paths
    assert radii["r"] == pytest.approx(2.0)


def test_joint_radii_skips_paths_without_samples(rp):
    samples = [[(0.1, 1.0)], [], [], [], []]
    radii = rp.joint_radii(BRANCHED, samples, passes=0)
    assert "s0" not in radii
    assert radii["l1_tip"] == pytest.approx(1.0)


def test_factor(rp):
    assert rp.gradient(2.0, 1.0, 0.5) == pytest.approx(1.5)
    assert rp.factor(3.0, 1.5) == pytest.approx(2.0)
    assert rp.factor(1000.0, 1.0) == rp.FACTOR_MAX
    assert rp.factor(0.0, 1.0) == rp.FACTOR_MIN
    assert rp.factor(1.0, 0.0) == 1.0


def test_resample_by_name_then_ratio(rp):
    items = [("a", 0.0, 1.0), ("b", 0.5, 2.0), ("c", 1.0, 1.0)]
    # same chain: matched by name
    assert rp.resample(items, [("a", 0.0), ("b", 0.5), ("c", 1.0)]) == {
        "a": 1.0,
        "b": 2.0,
        "c": 1.0,
    }
    # a longer chain: interpolated at the ratios
    joints = [("j{}".format(index), index / 4.0) for index in range(5)]
    factors = rp.resample(items, joints)
    assert [factors[joint] for joint, _ in joints] == pytest.approx(
        [1.0, 1.5, 2.0, 1.5, 1.0]
    )
    # equal ratios averaged
    assert rp.resample([("x", 0.5, 1.0), ("y", 0.5, 3.0)], [("z", 0.5)]) == {"z": 2.0}
    assert rp.resample([], joints) == {}


# ---------------------------------------------------------------------
# boneDynamicsNode
# ---------------------------------------------------------------------
TAIL_JOINTS = (
    ("tail0_ctl", False),
    ("tail1_ctl", False),
    ("tail2_ctl", False),
    ("tail2_ctl", True),
)


def _joint_radii(cmds, backend, spring):
    """Return the node radii at each joint, checking they meet.

    Returns:
        dict: ``{joint: radius}``.
    """
    radii = {}
    for section in backend.profile_sections(spring):
        for joint, _, attr in section.ends():
            value = cmds.getAttr(section.node + "." + attr)
            if joint in radii:
                # a bone's end radius is its child's root radius
                assert value == pytest.approx(radii[joint], abs=1e-4)
            radii[joint] = value
    return radii


def _profile_nodes(cmds, spring):
    from mgear.animbits.spring_manager.backends import bone_dynamics

    return [
        node
        for node in cmds.ls(spring.members, type="multiplyDivide")
        if node.endswith(tuple(bone_dynamics.RADIUS_PROFILES.values()))
    ]


def _factors(backend, spring):
    return {joint: value for joint, _, value in backend.radius_profile(spring)}


def _tube(cmds, radius_at, start=0.0, end=9.0, name="tube"):
    """A tube along X at height 10, its radius a function of X."""
    tube = cmds.polyCylinder(
        radius=1,
        height=end - start,
        subdivisionsAxis=24,
        subdivisionsHeight=int((end - start) * 4),
        constructionHistory=False,
        name=name,
    )[0]
    cmds.rotate(0, 0, -90, tube)
    cmds.move((start + end) * 0.5, 10, 0, tube)
    cmds.makeIdentity(tube, apply=True, translate=True, rotate=True)
    for vertex in cmds.ls(tube + ".vtx[*]", flatten=True):
        x, y, z = cmds.xform(vertex, query=True, translation=True)
        radius = radius_at(x)
        length = ((y - 10) ** 2 + z**2) ** 0.5 or 1.0
        cmds.xform(
            vertex,
            translation=(x, 10 + (y - 10) / length * radius, z / length * radius),
        )
    return tube


def _bulge(x):
    """Radius 1, with a radius 2 bulge around the tail1 joint (x 3)."""
    distance = abs(x - 3.0)
    if distance < 0.8:
        return 2.0
    if distance < 1.4:
        return 2.0 - (distance - 0.8) / 0.6
    return 1.0


def _tail_spring(cmds, bdn, namespace=""):
    from spring_helpers import build_tail_rig

    _, controls = build_tail_rig(cmds, namespace)
    cmds.currentTime(1)
    return bdn.create([controls[0]])[0], controls


def test_profile_multiplies_the_gradient(bdn):
    from maya import cmds

    spring, _ = _tail_spring(cmds, bdn)
    bdn.set_params([spring], {"springRadius": 2.0, "springTipRadius": 1.0})
    radii = _joint_radii(cmds, bdn, spring)
    assert [radii[joint] for joint in TAIL_JOINTS] == pytest.approx(
        [2.0, 2.0 - 1 / 3.0, 2.0 - 2 / 3.0, 1.0]
    )
    bdn.set_radius_profile(
        [spring],
        [
            (TAIL_JOINTS[0], 0.0, 1.5),
            (TAIL_JOINTS[1], 1 / 3.0, 1.0),
            (TAIL_JOINTS[2], 2 / 3.0, 1.0),
            (TAIL_JOINTS[3], 1.0, 0.5),
        ],
    )
    radii = _joint_radii(cmds, bdn, spring)
    assert radii[TAIL_JOINTS[0]] == pytest.approx(3.0)
    assert radii[TAIL_JOINTS[3]] == pytest.approx(0.5)
    # not keyable
    profiles = _profile_nodes(cmds, spring)
    assert len(profiles) == 6
    assert not any(cmds.getAttr(node + ".input2X", keyable=True) for node in profiles)

    bdn.clear_radius_profile([spring])
    assert set(_factors(bdn, spring).values()) == {1.0}
    assert _joint_radii(cmds, bdn, spring)[TAIL_JOINTS[0]] == pytest.approx(2.0)


def test_old_spring_gets_the_profile(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager.backends import bone_dynamics

    spring, _ = _tail_spring(cmds, bdn)
    # a spring built before the profile: the ramps drive the nodes
    for node in cmds.ls(spring.members, type="boneDynamicsNode"):
        for attr, suffix in bone_dynamics.RADIUS_RAMPS.items():
            cmds.connectAttr(node + suffix + ".output", node + "." + attr, force=True)
    cmds.delete(_profile_nodes(cmds, spring))
    nodes = cmds.ls(spring.members, type="boneDynamicsNode")
    for node in nodes:
        cmds.deleteAttr(node + "." + bone_dynamics.PROFILE_JOINTS_ATTR)
    # joints found by name
    assert set(_factors(bdn, spring).values()) == {1.0}
    assert len(bdn.radius_profile(spring)) == 4

    bdn.set_radius_profile([spring], [(TAIL_JOINTS[1], 1 / 3.0, 2.0)])
    assert _factors(bdn, spring)[TAIL_JOINTS[1]] == pytest.approx(2.0)
    assert len(_profile_nodes(cmds, spring)) == 6
    # the joints are stored now
    assert all(
        cmds.attributeQuery(bone_dynamics.PROFILE_JOINTS_ATTR, node=node, exists=True)
        for node in nodes
    )

    bake.delete([spring])
    assert not cmds.ls("*RadiusProfile*", "*radiusProfile*")


def test_fit_follows_a_bulge(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import fit

    spring, _ = _tail_spring(cmds, bdn)
    tube = _tube(cmds, _bulge)
    fit.fit_bone_radius(bdn, [spring], tube, fit.FitOptions(smooth=0))
    radii = _joint_radii(cmds, bdn, spring)
    assert radii[TAIL_JOINTS[1]] == pytest.approx(2.0, rel=0.15)
    assert radii[TAIL_JOINTS[0]] == pytest.approx(1.0, rel=0.15)
    assert radii[TAIL_JOINTS[3]] == pytest.approx(1.0, rel=0.15)

    # the tip radius set by hand: the gradient changes, the factors stay
    factors = _factors(bdn, spring)
    values = bdn.get_params(spring)
    root, tip = values["springRadius"], values["springTipRadius"] * 0.5
    bdn.set_params([spring], {"springTipRadius": tip})
    radii = _joint_radii(cmds, bdn, spring)
    for joint, ratio, value in bdn.radius_profile(spring):
        assert value == pytest.approx(factors[joint])
        assert radii[joint] == pytest.approx((root + (tip - root) * ratio) * value)


def test_fit_smoothing_and_line_only(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import fit

    spring, _ = _tail_spring(cmds, bdn)
    tube = _tube(cmds, _bulge)

    def spread():
        values = [_factors(bdn, spring)[joint] for joint in TAIL_JOINTS]
        return max(abs(b - a) for a, b in zip(values, values[1:]))

    fit.fit_bone_radius(bdn, [spring], tube, fit.FitOptions(smooth=0))
    sharp = spread()
    fit.fit_bone_radius(bdn, [spring], tube, fit.FitOptions(smooth=4))
    assert spread() < sharp

    # line only: Root / Tip Radius change, the factors don't
    factors = _factors(bdn, spring)
    cmds.delete(tube)
    thick = _tube(cmds, lambda x: 3.0, name="thick")
    fit.fit_bone_radius(bdn, [spring], thick, fit.FitOptions(profile=False))
    assert bdn.get_params(spring)["springRadius"] == pytest.approx(3.0, rel=0.1)
    assert _factors(bdn, spring) == pytest.approx(factors)


def test_fit_branches_not_mixed(bdn):
    from maya import cmds

    from spring_helpers import build_skirt

    from mgear.animbits.spring_manager import fit

    # left branch l0-l1 along +X (thin), right branch r0-r1 along -X (thick)
    root, _ = build_skirt(cmds)
    cmds.setAttr(cmds.listRelatives(root, parent=True)[0] + ".rotateY", 0)
    cmds.currentTime(1)
    spring = bdn.create([root])[0]
    thin = _tube(cmds, lambda x: 0.5, 0.0, 6.0, "thin")
    thick = _tube(cmds, lambda x: 1.5, -6.0, 0.0, "thick")
    mesh = cmds.polyUnite(thin, thick, constructionHistory=False, name="skirt")[0]
    fit.fit_bone_radius(bdn, [spring], mesh, fit.FitOptions(smooth=0))
    radii = _joint_radii(cmds, bdn, spring)
    assert radii[("l1_ctl", False)] == pytest.approx(0.5, rel=0.2)
    assert radii[("r1_ctl", False)] == pytest.approx(1.5, rel=0.2)


def test_profile_after_collider_removed(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    spring, controls = _tail_spring(cmds, bdn)
    bdn.set_params([spring], {"springRadius": 1.0, "springTipRadius": 1.0})
    bdn.set_radius_profile([spring], [(TAIL_JOINTS[0], 0.0, 2.0)])
    joints = [bdn.sim_joint(control) for control in controls]
    tube = _tube(cmds, lambda x: 0.7)
    created = fit.fit_capsules(tube, joints, fit.FitOptions())
    node = bdn.bone_node(joints[0])
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(0.7, rel=0.15)
    colliders.delete(created)
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(2.0)


def test_profile_rig_preset_round_trip(bdn):
    import json

    from maya import cmds

    from mgear.animbits.spring_manager import presets

    spring, _ = _tail_spring(cmds, bdn, "chr")
    items = [
        (TAIL_JOINTS[0], 0.0, 1.2),
        (TAIL_JOINTS[1], 1 / 3.0, 1.8),
        (TAIL_JOINTS[2], 2 / 3.0, 0.9),
        (TAIL_JOINTS[3], 1.0, 0.6),
    ]
    bdn.set_radius_profile([spring], items)
    preset = json.loads(json.dumps(presets.collect([spring])))
    assert len(preset["springs"][0]["radius_profile"]) == 4

    from spring_helpers import build_tail_rig

    build_tail_rig(cmds, "chr2")
    springs, missing = presets.apply_by_name(preset, "chr2:")
    assert not missing
    assert _factors(bdn, springs[0]) == pytest.approx(_factors(bdn, spring))

    # a preset without a profile leaves it alone
    del preset["springs"][0]["radius_profile"]
    presets.apply_by_name(preset, "chr2:")
    assert _factors(bdn, springs[0])[TAIL_JOINTS[1]] == pytest.approx(1.8)

    # an unprofiled spring saves no profile
    bdn.clear_radius_profile([spring])
    assert "radius_profile" not in presets.collect([spring])["springs"][0]


def test_profile_values_preset_on_a_longer_chain(bdn):
    from maya import cmds

    from spring_helpers import make_control

    from mgear.animbits.spring_manager import presets
    from mgear.animbits.spring_manager import radius_profile

    spring, _ = _tail_spring(cmds, bdn)
    items = [
        (TAIL_JOINTS[0], 0.0, 1.0),
        (TAIL_JOINTS[1], 1 / 3.0, 2.0),
        (TAIL_JOINTS[2], 2 / 3.0, 1.0),
        (TAIL_JOINTS[3], 1.0, 1.0),
    ]
    bdn.set_radius_profile([spring], items)
    preset = presets.build_values_preset(
        bdn.name, bdn.get_params(spring), extras=bdn.preset_extras(spring)
    )

    rig = cmds.createNode("transform", name="hair")
    controls = [make_control(cmds, "hair0", rig, (0, 20, 0))]
    for index in range(1, 6):
        controls.append(make_control(cmds, "hair%d" % index, controls[-1], (1.5, 0, 0)))
    target = bdn.create([controls[0]])[0]
    assert presets.apply_values(preset, [target]) == 1
    for _, ratio, value in bdn.radius_profile(target):
        expected = radius_profile.resample(items, [(("other", False), ratio)])
        assert value == pytest.approx(list(expected.values())[0])

    # a values preset on controls without a spring: created with the profile
    free = make_control(cmds, "free0", rig, (0, 30, 0))
    make_control(cmds, "free1", free, (3, 0, 0))
    created = presets.create_from_entry(bdn, [free], preset["springs"][0])
    assert len(created) == 1
    for _, ratio, value in bdn.radius_profile(created[0]):
        expected = radius_profile.resample(items, [(("other", False), ratio)])
        assert value == pytest.approx(list(expected.values())[0])
    assert max(value for _, _, value in bdn.radius_profile(created[0])) > 1.0
