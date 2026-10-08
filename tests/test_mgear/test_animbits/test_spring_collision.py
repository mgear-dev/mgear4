"""mgear.animbits.spring_manager collision: assignment, colliders, fit"""

import json
import re

import pytest

from spring_helpers import build_skirt
from spring_helpers import build_tail_rig


def _connected(cmds, node, array):
    """Return the indices of a boneDynamicsNode collider array with inputs."""
    pattern = re.compile(r"\.{}\[(\d+)\]".format(array))
    connections = (
        cmds.listConnections(
            node, source=True, destination=False, plugs=True, connections=True
        )
        or []
    )
    return sorted(
        {
            int(match.group(1))
            for match in (pattern.search(plug) for plug in connections[::2])
            if match
        }
    )


def _joint(cmds, name, position, parent=None):
    joint = cmds.createNode("joint", name=name, parent=parent)
    cmds.xform(joint, worldSpace=True, translation=position)
    return joint


def test_wind_assignment_queries(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import constants
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds)
    root, _ = build_skirt(cmds)
    springs = bdn.create([controls[0]]) + bdn.create([root])
    wind = bdn.create_wind()
    bdn.connect_wind(springs, wind)
    network = registry.list_shared(constants.KIND_WIND)[0]
    assert set(registry.assigned_springs(network)) == set(springs)
    assert registry.shared_of(springs[0], constants.KIND_WIND) == [network]
    assert bdn.wind_of(springs[0]) == wind

    # exclusive: a second wind replaces the first
    other = bdn.create_wind("wind2")
    bdn.connect_wind(springs[:1], other)
    assert bdn.wind_of(springs[0]) == other
    assert registry.assigned_springs(network) == springs[1:]
    node = cmds.ls(springs[0].members, type="boneDynamicsNode")[0]
    source = cmds.listConnections(node + ".additionalForce", source=True)
    assert source and source[0].startswith("wind2")

    bdn.disconnect_wind(springs[:1])
    assert bdn.wind_of(springs[0]) is None
    assert not cmds.listConnections(node + ".additionalForce", source=True)


def test_delete_shared_unassigns(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import constants
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds)
    springs = bdn.create([controls[0]])
    wind = bdn.create_wind()
    bdn.connect_wind(springs, wind)
    network = registry.list_shared(constants.KIND_WIND)[0]
    registry.delete_shared(network)
    assert not cmds.objExists(network)
    assert bdn.wind_of(springs[0]) is None
    node = cmds.ls(springs[0].members, type="boneDynamicsNode")[0]
    assert not cmds.listConnections(node + ".additionalForce", source=True)


def test_collider_create_on_driver(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders

    head = _joint(cmds, "head_jnt", (0, 15, 0))
    network = colliders.create(colliders.SPHERE, head, dimensions={"radius": 5})
    transform = colliders.collider_transform(network)
    assert cmds.ls(transform, long=True)[0].startswith("|" + colliders.GROUP + "|")
    assert not cmds.listRelatives(head, children=True)
    assert colliders.driver(network) == head
    assert colliders.get_dimensions(network) == {"radius": 5}
    assert cmds.xform(
        transform, query=True, worldSpace=True, translation=True
    ) == pytest.approx([0, 15, 0])
    cmds.setAttr(head + ".translateX", 4)
    assert cmds.xform(
        transform, query=True, worldSpace=True, translation=True
    ) == pytest.approx([4, 15, 0])
    assert colliders.collider_from_node(transform) == network
    assert colliders.list_colliders() == [network]
    with pytest.raises(ValueError):
        colliders.create("cube")


def test_collider_assign_resize_and_packing(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds)
    spring = bdn.create([controls[0]])[0]
    nodes = cmds.ls(spring.members, type="boneDynamicsNode")
    head = _joint(cmds, "head_jnt", (0, 15, 0))
    first = colliders.create(colliders.SPHERE, head, dimensions={"radius": 5})
    second = colliders.create(colliders.SPHERE, head, name="second")
    capsule = colliders.create(colliders.CAPSULE, head)
    for network in (first, second, capsule):
        registry.assign(network, [spring])
    for node in nodes:
        assert len(_connected(cmds, node, "sphereCollider")) == 2
        assert len(_connected(cmds, node, "capsuleColliderInput")) == 1

    # live resize
    colliders.set_dimensions(first, {"radius": 8})
    radii = [
        cmds.getAttr("{}.sphereCollider[{}].sphereColRadius".format(nodes[0], index))
        for index in _connected(cmds, nodes[0], "sphereCollider")
    ]
    assert 8 in radii

    # no gaps after unassign
    registry.unassign(first, [spring])
    for node in nodes:
        assert _connected(cmds, node, "sphereCollider") == [0]
        assert cmds.getAttr(node + ".sphereCollider", multiIndices=True) == [0]
    source = cmds.listConnections(
        nodes[0] + ".sphereCollider[0].sphereColRadius", source=True
    )
    assert source and source[0].startswith("second")


def test_collider_lifetime(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds)
    root, _ = build_skirt(cmds)
    springs = bdn.create([controls[0]]) + bdn.create([root])
    collider = colliders.create(colliders.PLANE)
    registry.assign(collider, springs)
    bake.delete(springs[:1])
    assert cmds.objExists(colliders.collider_transform(collider))
    assert registry.assigned_springs(collider) == springs[1:]

    nodes = cmds.ls(springs[1].members, type="boneDynamicsNode")
    assert _connected(cmds, nodes[0], "infinitePlaneCollider") == [0]
    transform = colliders.collider_transform(collider)
    other = colliders.create(colliders.SPHERE)
    colliders.delete([collider])
    assert not cmds.objExists(collider)
    assert not cmds.objExists(transform)
    # the shared group and the other colliders are kept
    assert cmds.objExists(colliders.GROUP)
    assert cmds.objExists(colliders.collider_transform(other))
    assert not _connected(cmds, nodes[0], "infinitePlaneCollider")


def test_mesh_collider_proxy_and_as_is(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds)
    spring = bdn.create([controls[0]])[0]
    body = cmds.polySphere(name="body", radius=5, constructionHistory=False)[0]
    faces = cmds.polyEvaluate(body, face=True)

    proxied = colliders.create_mesh(body, proxy=True, reduce_percent=50)
    proxy = colliders.collider_transform(proxied)
    assert cmds.ls(proxy, long=True)[0].startswith("|" + colliders.GROUP + "|")
    assert cmds.polyEvaluate(proxy, face=True) < faces
    assert cmds.polyEvaluate(body, face=True) == faces
    assert colliders.source_mesh(proxied) == body
    assert colliders.proxy_settings(proxied)["proxy"] is True

    as_is = colliders.create_mesh(body, proxy=False)
    assert colliders.collider_transform(as_is).split("|")[-1] == body
    registry.assign(proxied, [spring])
    registry.assign(as_is, [spring])
    node = cmds.ls(spring.members, type="boneDynamicsNode")[0]
    assert len(_connected(cmds, node, "meshCollider")) == 2

    # deleting the as-is collider keeps the user's mesh
    colliders.delete([as_is, proxied])
    assert cmds.objExists(body)
    assert not cmds.objExists(proxy)
    assert not _connected(cmds, node, "meshCollider")


def test_mirror_colliders(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    left = _joint(cmds, "arm_L0_fk0_jnt", (5, 10, 0))
    right = _joint(cmds, "arm_R0_fk0_jnt", (-5, 10, 0))
    network = colliders.create(
        colliders.CAPSULE,
        left,
        dimensions={"height": 4, "radiusA": 1, "radiusB": 2},
    )
    transform = colliders.collider_transform(network)
    cmds.xform(transform, worldSpace=True, translation=(6, 11, 1))
    cmds.xform(transform, worldSpace=True, rotation=(0, 0, -45))

    mirrored = colliders.mirror([network])
    assert len(mirrored) == 1
    target = mirrored[0]
    assert colliders.driver(target) == right
    assert "_R0_" in colliders.label(target)
    assert colliders.get_dimensions(target) == colliders.get_dimensions(network)
    matrix = colliders.get_world_matrix(target)
    assert matrix[12:15] == pytest.approx([-6, 11, 1])
    # local Y (the capsule axis) mirrored across YZ
    source = colliders.get_world_matrix(network)
    assert matrix[4:7] == pytest.approx([-source[4], source[5], source[6]])

    # updated, not duplicated
    colliders.set_dimensions(network, {"radiusA": 3})
    assert colliders.mirror([network]) == [target]
    assert colliders.get_dimensions(target)["radiusA"] == 3
    assert len(colliders.list_colliders()) == 2
    assert registry.assigned_springs(target) == []


def test_pick_ground_height(scene):
    from maya import cmds

    from mgear.animbits.spring_manager import solver
    from mgear.core import mesh

    floor = cmds.polyPlane(width=10, height=10, constructionHistory=False)[0]
    cmds.move(0, 5, 0, floor)
    box = cmds.polyCube(constructionHistory=False)[0]
    cmds.move(0, 5.5, 0, box)
    assert mesh.get_lowest_point([floor, box]) == pytest.approx(5)
    assert mesh.get_lowest_point([box + ".vtx[0]"]) == pytest.approx(5)
    assert mesh.get_lowest_point([]) is None
    cmds.select(floor, box)
    assert solver.pick_ground_height() == pytest.approx(5)
    settings = solver.get_settings()
    assert settings["ground_height"] == pytest.approx(5)


def test_bone_volume_ramp(bdn):
    from maya import cmds

    _, controls = build_tail_rig(cmds)
    spring = bdn.create(
        [controls[0]],
        {
            "springRadius": 2.0,
            "springTipRadius": 1.0,
            "springBoneAsCapsule": True,
            "springMeshCutoff": 25.0,
        },
    )[0]
    nodes = sorted(
        cmds.ls(spring.members, type="boneDynamicsNode"),
        key=lambda node: cmds.getAttr(node + ".rootRadius"),
        reverse=True,
    )
    # three sections: root radius 2, tip radius 1, linear in between
    roots = [cmds.getAttr(node + ".rootRadius") for node in nodes]
    ends = [cmds.getAttr(node + ".radius") for node in nodes]
    assert roots == pytest.approx([2.0, 2.0 - 1 / 3.0, 2.0 - 2 / 3.0])
    assert ends == pytest.approx([2.0 - 1 / 3.0, 2.0 - 2 / 3.0, 1.0])
    assert all(cmds.getAttr(node + ".boneAsCapsule") for node in nodes)
    assert cmds.getAttr(nodes[0] + ".meshColCutoff") == pytest.approx(25.0)


def test_bone_volume_single_section(bdn):
    from maya import cmds

    control = cmds.circle(name="single_ctl", constructionHistory=False)[0]
    spring = bdn.create([control], {"springRadius": 2.0, "springTipRadius": 1.0})[0]
    node = cmds.ls(spring.members, type="boneDynamicsNode")[0]
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(2.0)
    assert cmds.getAttr(node + ".radius") == pytest.approx(1.0)


def _skinned_cylinder(cmds, radius=2.0):
    """Cylinder along Y from 0 to 12, skinned to joints at 0, 5 and 10.

    The last joint is inside the mesh, like a head joint.
    """
    cylinder = cmds.polyCylinder(
        name="body",
        radius=radius,
        height=12,
        subdivisionsAxis=24,
        subdivisionsHeight=24,
        constructionHistory=False,
    )[0]
    cmds.move(0, 6, 0, cylinder)
    cmds.makeIdentity(cylinder, apply=True, translate=True)
    cmds.select(clear=True)
    joints = [
        cmds.joint(name="spine%d_jnt" % index, position=(0, 5 * index, 0))
        for index in range(3)
    ]
    cmds.skinCluster(joints, cylinder, toSelectedBones=True, maximumInfluences=1)
    return cylinder, joints


def test_chain_parts(scene):
    from maya import cmds

    from mgear.animbits.spring_manager import fit

    _, joints = _skinned_cylinder(cmds)
    segments, ends = fit.chain_parts(joints)
    long_names = cmds.ls(joints, long=True)
    assert segments == [(long_names[0], long_names[1]), (long_names[1], long_names[2])]
    assert ends == [long_names[2]]
    # skipping a joint links its selected ancestor
    segments, ends = fit.chain_parts([joints[0], joints[2]])
    assert segments == [(long_names[0], long_names[2])]


@pytest.mark.parametrize("method", ["skin", "raycast"])
def test_fit_capsules(bdn, method):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    cylinder, joints = _skinned_cylinder(cmds)
    options = fit.FitOptions(method=method, end_spheres=False)
    created = fit.fit_capsules(cylinder, joints[:2], options)
    assert len(created) == 1
    capsule = created[0]
    assert colliders.collider_type(capsule) == colliders.CAPSULE
    assert colliders.driver(capsule) == joints[0]
    dims = colliders.get_dimensions(capsule)
    assert dims["height"] == pytest.approx(5.0)
    assert dims["radiusA"] == pytest.approx(2.0, rel=0.1)
    assert dims["radiusB"] == pytest.approx(2.0, rel=0.1)
    # capsule axis convention: centred, +Y towards the end joint
    matrix = colliders.get_world_matrix(capsule)
    assert matrix[12:15] == pytest.approx([0, 2.5, 0], abs=1e-4)
    assert matrix[4:7] == pytest.approx([0, 1, 0], abs=1e-4)


def test_fit_capsules_end_spheres(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    cylinder, joints = _skinned_cylinder(cmds)
    created = fit.fit_capsules(cylinder, joints, fit.FitOptions())
    types = sorted(colliders.collider_type(network) for network in created)
    assert types == ["capsule", "capsule", "sphere"]
    sphere = [n for n in created if colliders.collider_type(n) == "sphere"][0]
    assert colliders.driver(sphere) == joints[2]
    assert 1.5 < colliders.get_dimensions(sphere)["radius"] < 3.0

    cmds.undo()
    assert not colliders.list_colliders()
    created = fit.fit_capsules(cylinder, joints, fit.FitOptions(end_spheres=False))
    assert {colliders.collider_type(n) for n in created} == {"capsule"}


def test_fit_sphere(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    ball = cmds.polySphere(
        radius=3, subdivisionsAxis=24, subdivisionsHeight=24, constructionHistory=False
    )[0]
    cmds.move(1, 2, 3, ball)
    network = fit.fit_sphere(vertices=[ball + ".vtx[*]"])
    assert colliders.get_dimensions(network)["radius"] == pytest.approx(3.0, rel=0.1)
    assert colliders.get_world_matrix(network)[12:15] == pytest.approx(
        [1, 2, 3], abs=0.05
    )
    assert colliders.driver(network) is None

    head = _joint(cmds, "head_jnt", (1, 2, 3))
    network = fit.fit_sphere(mesh=ball, joint=head)
    assert colliders.driver(network) == head
    assert colliders.get_dimensions(network)["radius"] == pytest.approx(3.0, rel=0.1)
    with pytest.raises(ValueError):
        fit.fit_sphere()


def _tail_in_tube(cmds, bdn):
    """A 3 control tail spring inside a tapered tube.

    The tail controls are at x 0, 3, 6 (rig at origin on frame 1): the
    virtual tip is at x 9. The tube radius goes from 2 at x 0 to 0.5 at x 9.

    Returns:
        tuple: ``(spring, controls, tube)``.
    """
    _, controls = build_tail_rig(cmds)
    cmds.currentTime(1)
    spring = bdn.create([controls[0]])[0]
    tube = cmds.polyCylinder(
        radius=1,
        height=9,
        subdivisionsAxis=24,
        subdivisionsHeight=18,
        constructionHistory=False,
    )[0]
    cmds.rotate(0, 0, -90, tube)
    cmds.move(4.5, 10, 0, tube)
    cmds.makeIdentity(tube, apply=True, translate=True, rotate=True)
    for vertex in cmds.ls(tube + ".vtx[*]", flatten=True):
        x, y, z = cmds.xform(vertex, query=True, translation=True)
        radius = 2.0 - 1.5 * x / 9.0
        length = ((y - 10) ** 2 + z**2) ** 0.5 or 1.0
        cmds.xform(
            vertex,
            translation=(x, 10 + (y - 10) / length * radius, z / length * radius),
        )
    return spring, controls, tube


def test_fit_bone_radius(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import fit

    spring, _, tube = _tail_in_tube(cmds, bdn)
    # the visualizer also reads the radius plugs: it must not be mistaken
    # for the ramps
    bdn.set_visualizer([spring], True)
    result = fit.fit_bone_radius(bdn, [spring], tube)
    root, tip = result[spring]
    assert root == pytest.approx(2.0, rel=0.1)
    assert tip == pytest.approx(0.5, abs=0.1)
    values = bdn.get_params(spring)
    assert values["springRadius"] == pytest.approx(root)
    assert values["springTipRadius"] == pytest.approx(tip)
    assert values["springBoneAsCapsule"]


def _collider_rig(cmds, namespace):
    """A tail rig in a namespace with a spine joint for colliders."""
    rig, controls = build_tail_rig(cmds, namespace)
    spine = _joint(cmds, namespace + ":spine_C0_jnt", (0, 8, 0), rig)
    return controls, spine


def test_collider_preset_round_trip(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import presets
    from mgear.animbits.spring_manager import registry

    controls, spine = _collider_rig(cmds, "chr")
    spring = bdn.create([controls[0]])[0]
    capsule = colliders.create(
        colliders.CAPSULE, spine, dimensions={"height": 3, "radiusA": 1.5}
    )
    cmds.setAttr(colliders.collider_transform(capsule) + ".translateY", 0.5)
    registry.assign(capsule, [spring])

    preset = presets.collect([spring])
    assert preset["colliders"] == [
        {
            "name": "spine_C0_jnt_capsuleCol",
            "type": "capsule",
            "driver": "spine_C0_jnt",
            "offset": pytest.approx(colliders.get_offset(capsule)),
            "dimensions": colliders.get_dimensions(capsule),
        }
    ]
    assert preset["assignments"] == {"spine_C0_jnt_capsuleCol": ["tail0_ctl"]}
    assert "Colliders: 1" in presets.describe(preset)
    preset = json.loads(json.dumps(preset))

    controls2, spine2 = _collider_rig(cmds, "chr2")
    springs, missing = presets.apply_by_name(preset, "chr2:")
    assert not missing
    target = [
        network
        for network in colliders.list_colliders()
        if colliders.label(network) == "chr2_spine_C0_jnt_capsuleCol"
    ]
    assert len(target) == 1
    assert colliders.driver(target[0]) == spine2
    assert colliders.get_dimensions(target[0]) == colliders.get_dimensions(capsule)
    assert colliders.get_offset(target[0]) == pytest.approx(
        colliders.get_offset(capsule)
    )
    assert registry.assigned_springs(target[0]) == springs

    # applied again: updated, not duplicated
    count = len(colliders.list_colliders())
    presets.apply_by_name(preset, "chr2:")
    assert len(colliders.list_colliders()) == count


def test_collider_preset_missing_driver_and_off(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import presets
    from mgear.animbits.spring_manager import registry

    controls, spine = _collider_rig(cmds, "chr")
    spring = bdn.create([controls[0]])[0]
    for kind_type in (colliders.SPHERE, colliders.PLANE):
        registry.assign(colliders.create(kind_type, spine), [spring])
    preset = presets.collect([spring])
    assert len(preset["colliders"]) == 2

    # another rig without the spine joint: springs applied, colliders skipped
    build_tail_rig(cmds, "other")
    count = len(colliders.list_colliders())
    springs, missing = presets.apply_by_name(preset, "other:")
    assert springs and not missing
    assert len(colliders.list_colliders()) == count

    # colliders off
    _collider_rig(cmds, "chr3")
    springs, _ = presets.apply_by_name(preset, "chr3:", apply_colliders=False)
    assert springs
    assert len(colliders.list_colliders()) == count

    # values presets carry no colliders
    values = presets.build_values_preset(bdn, bdn.get_params(spring))
    assert not values["colliders"] and not values["assignments"]


def test_colliders_section_ui(bdn, clean_settings):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry
    from mgear.animbits.spring_manager import ui
    from mgear.vendor.Qt import QtCore

    _, controls = build_tail_rig(cmds)
    spring = bdn.create([controls[0]])[0]
    sphere = colliders.create(colliders.SPHERE, name="head_sphereCol")
    window = ui.SpringManager()
    try:
        _, section, panel = window.backend_sections[0]
        window.solver_combo.setCurrentIndex(window.solver_combo.findData("classic"))
        assert section.isHidden()
        window.solver_combo.setCurrentIndex(
            window.solver_combo.findData("bone_dynamics")
        )
        assert not section.isHidden()
        window.scene_changed()
        assert panel.table.rowCount() == 1
        assert panel.table.columnCount() == 1
        assert panel.collider_list.count() == 1

        # check a cell assigns, uncheck unassigns
        panel.table.item(0, 0).setCheckState(QtCore.Qt.Checked)
        assert registry.assigned_springs(sphere) == [spring]
        panel.table.item(0, 0).setCheckState(QtCore.Qt.Unchecked)
        assert registry.assigned_springs(sphere) == []
        panel._assign_all()
        assert registry.assigned_springs(sphere) == [spring]
        assert panel.table.item(0, 0).checkState() == QtCore.Qt.Checked

        # create from selection, in the list after the action
        head = _joint(cmds, "head_jnt", (0, 15, 0))
        cmds.select(head)
        panel._create(colliders.CAPSULE)
        assert panel.collider_list.count() == 2
        assert panel.table.columnCount() == 2
    finally:
        window.shutdown()
        window.deleteLater()


def test_fit_on_controls(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    cylinder, joints = _skinned_cylinder(cmds)
    controls = []
    parent = None
    for index, joint in enumerate(joints):
        control = cmds.circle(name="spine%d_ctl" % index, constructionHistory=False)[0]
        if parent:
            control = cmds.parent(control, parent)[0]
        cmds.xform(
            control,
            worldSpace=True,
            translation=cmds.xform(
                joint, query=True, worldSpace=True, translation=True
            ),
        )
        controls.append(cmds.ls(control, long=True)[0])
        parent = control
    created = fit.fit_capsules(
        cylinder, controls[:2], fit.FitOptions(end_spheres=False)
    )
    assert len(created) == 1
    assert colliders.driver(created[0]) == "spine0_ctl"
    dims = colliders.get_dimensions(created[0])
    assert dims["radiusA"] == pytest.approx(2.0, rel=0.1)


def test_colliders_fit_inputs(bdn, clean_settings):
    from maya import cmds

    from mgear.animbits.spring_manager import ui
    from mgear.animbits.spring_manager import ui_panels

    cylinder, joints = _skinned_cylinder(cmds)
    window = ui.SpringManager()
    try:
        window.solver_combo.setCurrentIndex(
            window.solver_combo.findData("bone_dynamics")
        )
        _, _, panel = window.backend_sections[0]
        # mesh selected last
        cmds.select(joints[:2] + [cylinder])
        mesh, targets = panel.fit_inputs()
        assert mesh.endswith(cylinder)
        assert targets == cmds.ls(joints[:2], long=True)
        # mesh from the field, only targets selected
        cmds.select(cylinder)
        panel._pick_fit_mesh()
        cmds.select(joints[0])
        mesh, targets = panel.fit_inputs()
        assert mesh == cylinder
        assert targets == cmds.ls(joints[:1], long=True)
        # spring controls stand for their hidden sim joints
        _, controls = build_tail_rig(cmds)
        spring = bdn.create([controls[0]])[0]
        cmds.select(controls[1])
        _, targets = panel.fit_inputs()
        sim = bdn.sim_joint(controls[1])
        assert targets == [sim]

        # filters: list and table columns by collider, rows by spring
        from mgear.animbits.spring_manager import colliders

        colliders.create(colliders.SPHERE, name="head_sphereCol")
        colliders.create(colliders.SPHERE, name="hand_sphereCol")
        window.scene_changed()
        panel.collider_filter_le.setText("head*")
        visible = [
            panel.collider_list.item(row).text()
            for row in range(panel.collider_list.count())
            if not panel.collider_list.item(row).isHidden()
        ]
        assert len(visible) == 1 and visible[0].startswith("head_sphereCol")
        hidden_columns = [
            column
            for column in range(panel.table.columnCount())
            if panel.table.isColumnHidden(column)
        ]
        assert len(hidden_columns) == 1
        panel.spring_filter_le.setText("nothing*")
        assert panel.table.isRowHidden(0)
        assert window.user_settings[ui_panels.COLLIDERS_HEIGHT_KEY][0] is (
            panel.collider_grip
        )
        assert "_sim_" in sim and sim in cmds.ls(spring.members, long=True)
        assert bdn.sim_joint(joints[0]) is None
    finally:
        window.shutdown()
        window.deleteLater()


def test_collider_not_assigned_to_own_chain(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    _, controls = build_tail_rig(cmds)
    root, _ = build_skirt(cmds)
    tail, skirt = bdn.create([controls[0]]) + bdn.create([root])
    own = colliders.create(colliders.SPHERE, bdn.sim_joint(controls[1]))
    registry.assign(own, [tail, skirt])
    assert registry.assigned_springs(own) == [skirt]


def test_colliders_set_bone_volume(bdn):
    from maya import cmds

    from mgear.animbits.spring_manager import bake
    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    spring, controls, tube = _tail_in_tube(cmds, bdn)
    bdn.set_params([spring], {"springRadius": 0.3, "springTipRadius": 0.3})
    joints = [bdn.sim_joint(control) for control in controls]

    # fitted per section: the capsules keep the mesh radii, the bones follow
    created = fit.fit_capsules(tube, joints, fit.FitOptions())
    capsule = [
        n for n in created if cmds.ls(colliders.driver(n), long=True)[0] == joints[0]
    ][0]
    dims = colliders.get_dimensions(capsule)
    assert dims["radiusB"] == pytest.approx(2.0, rel=0.1)
    assert dims["radiusA"] == pytest.approx(1.5, rel=0.15)
    node = bdn.bone_node(joints[0])
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(dims["radiusB"])
    assert cmds.getAttr(node + ".radius") == pytest.approx(dims["radiusA"])
    assert bdn.get_params(spring)["springBoneAsCapsule"]
    # the last bone gets a capsule to the tip, matching the bone volume
    assert {colliders.collider_type(n) for n in created} == {"capsule"}
    assert len(created) == len(joints)
    last = [
        n for n in created if cmds.ls(colliders.driver(n), long=True)[0] == joints[-1]
    ][0]
    end_node = bdn.bone_node(joints[-1])
    last_dims = colliders.get_dimensions(last)
    assert cmds.getAttr(end_node + ".radius") == pytest.approx(last_dims["radiusA"])
    assert last_dims["radiusA"] == pytest.approx(0.5, abs=0.25)

    # editing a section's capsule changes that bone only
    colliders.set_dimensions(capsule, {"radiusA": 4.0})
    assert cmds.getAttr(node + ".radius") == pytest.approx(4.0)
    # the spring gradient no longer drives fitted sections
    bdn.set_params([spring], {"springRadius": 3.0})
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(dims["radiusB"])

    # deleting the capsule gives the bone back to the spring gradient
    colliders.delete([capsule])
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(3.0)
    bdn.set_params([spring], {"springRadius": 2.5})
    assert cmds.getAttr(node + ".rootRadius") == pytest.approx(2.5)

    # colliders on other nodes leave the bones alone
    free = colliders.create(colliders.SPHERE, dimensions={"radius": 5})
    assert colliders.get_dimensions(free)["radius"] == 5

    # deleting the spring keeps its colliders and their radii
    bake.delete([spring])
    assert colliders.get_dimensions(last) == pytest.approx(last_dims)
