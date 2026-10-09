"""mgear.animbits.spring_manager Classic Gravity backend and neutral colliders"""

import pytest


@pytest.fixture
def gravity(solvers):
    """The Classic Gravity backend, in a new scene."""
    from mgear.animbits.spring_manager.backends import get_backend

    return get_backend("classic_gravity")


def _control(cmds, name="ear", position=(0, 0, 0)):
    npo = cmds.createNode("transform", name=name + "_npo")
    cmds.setAttr(npo + ".translate", *position)
    control = cmds.circle(name=name + "_ctl", constructionHistory=False)[0]
    return cmds.ls(cmds.parent(control, npo, relative=True)[0], long=True)[0]


def _play(cmds, plug, frames):
    values = []
    for frame in frames:
        cmds.currentTime(frame)
        values.append(cmds.getAttr(plug))
    return values


def _solvers(cmds, spring):
    return cmds.ls(spring.members, type="mgear_springGravityNode")


def test_create_and_delete(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import registry

    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    assert spring.backend == "classic_gravity"
    assert gravity.label == "Classic Gravity"
    assert len(_solvers(cmds, spring)) == 2
    assert not cmds.ls(spring.members, type="mgear_springNode")
    assert registry.list_springs() == [spring]
    gravity.delete(spring)
    assert registry.list_springs() == []
    assert not cmds.ls(type="mgear_springGravityNode")
    assert not cmds.attributeQuery("springGravityStrength", node=control, exists=True)


def test_gravity_droops(gravity):
    from maya import cmds

    rotations = {}
    for strength in (0.0, 5.0):
        control = _control(cmds, "ear{}".format(int(strength)))
        gravity.create(
            [control], {"springGravityStrength": strength}, {"direction": "x"}
        )
        cmds.currentTime(0)
        rotations[strength] = _play(cmds, control + ".rz", range(1, 25))[-1]
    # aiming along +X, gravity along -Y bends the control down (negative Z)
    assert abs(rotations[0.0]) < 1e-3
    assert rotations[5.0] < -5.0


def test_gravity_direction_survives_saving(gravity, tmp_path):
    from maya import cmds

    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    gravity.set_params([spring], {"springGravityDirection": (1.0, 0.0, 0.0)})
    path = str(tmp_path / "gravity.ma").replace("\\", "/")
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii")
    cmds.file(path, open=True, force=True)
    for solver in cmds.ls(type="mgear_springGravityNode"):
        assert cmds.getAttr(solver + ".gravity_direction")[0] == pytest.approx(
            (1.0, 0.0, 0.0)
        )


def test_gravity_direction_default_z_up(gravity):
    from maya import cmds

    cmds.upAxis(axis="z")
    try:
        control = _control(cmds)
        spring = gravity.create([control], options={"direction": "x"})[0]
        assert gravity.get_params(spring)["springGravityDirection"] == pytest.approx(
            (0.0, 0.0, -1.0)
        )
    finally:
        cmds.upAxis(axis="y")


def test_sphere_and_ground(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    sphere = colliders.create(colliders.SPHERE, dimensions={"radius": 3})
    cmds.setAttr(colliders.collider_transform(sphere) + ".translateX", 2)
    registry.assign(sphere, [spring])
    for solver in _solvers(cmds, spring):
        assert cmds.getAttr(solver + ".colliders_list", multiIndices=True) == [0]
        assert cmds.getAttr(solver + ".colliders_list[0].collide_radius") == 3
        assert cmds.getAttr(solver + ".colliders_list[0].collider")[0] == (
            pytest.approx((2, 0, 0))
        )
    # one world position node, owned by the sphere collider
    positions = cmds.ls(type="decomposeMatrix")
    assert len([node for node in positions if node.endswith("_position")]) == 1
    # live radius
    colliders.set_dimensions(sphere, {"radius": 4})
    solver = _solvers(cmds, spring)[0]
    assert cmds.getAttr(solver + ".colliders_list[0].collide_radius") == 4

    # ground from a plane collider
    plane = colliders.create(colliders.PLANE)
    registry.assign(plane, [spring])
    assert gravity.get_params(spring)["springUseGround"]
    for solver in _solvers(cmds, spring):
        assert cmds.listConnections(solver + ".ground_transform", source=True)
    registry.unassign(plane, [spring])
    assert not gravity.get_params(spring)["springUseGround"]
    for solver in _solvers(cmds, spring):
        assert not cmds.listConnections(solver + ".ground_transform", source=True)

    # unassigning the sphere clears the list
    registry.unassign(sphere, [spring])
    assert not cmds.getAttr(solver + ".colliders_list", multiIndices=True)


def test_refuses_capsule(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    if not colliders.plugin_shapes():
        pytest.skip("capsule colliders need the boneDynamicsNode plug-in")
    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    capsule = colliders.create(colliders.CAPSULE)
    registry.assign(capsule, [spring])
    assert registry.assigned_springs(capsule) == []


def test_colliders_without_plugin(gravity, monkeypatch):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    monkeypatch.setattr(colliders, "plugin_shapes", lambda: False)
    sphere = colliders.create(colliders.SPHERE, dimensions={"radius": 2})
    transform = colliders.collider_transform(sphere)
    assert colliders.dimension_node(sphere) == transform
    assert colliders.get_dimensions(sphere) == {"radius": 2}
    assert not cmds.ls(
        cmds.listRelatives(transform, allDescendents=True) or [],
        type="sphereColliderNode",
    )
    assert cmds.ls(
        cmds.listRelatives(transform, allDescendents=True) or [], type="nurbsCurve"
    )
    plane = colliders.create(colliders.PLANE)
    assert colliders.collider_type(plane) == colliders.PLANE
    with pytest.raises(RuntimeError):
        colliders.create(colliders.CAPSULE)
    assert set(colliders.list_colliders()) == {sphere, plane}

    # an mGear sphere works for Classic Gravity
    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    registry.assign(sphere, [spring])
    solver = _solvers(cmds, spring)[0]
    assert cmds.getAttr(solver + ".colliders_list[0].collide_radius") == 2


def test_colliders_section_ui(gravity, clean_settings):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import ui

    control = _control(cmds)
    gravity.create([control], options={"direction": "x"})
    window = ui.SpringManager()
    try:
        sections = {
            backend: (section, panel)
            for backend, section, panel in window.backend_sections
        }
        section, panel = sections["classic_gravity"]
        window.solver_combo.setCurrentIndex(window.solver_combo.findData("classic"))
        assert section.isHidden()
        window.solver_combo.setCurrentIndex(
            window.solver_combo.findData("classic_gravity")
        )
        assert not section.isHidden()
        assert sections["bone_dynamics"][0].isHidden()
        # the Classic direction buttons
        from mgear.animbits.spring_manager import ui_panels

        assert isinstance(
            window.create_panels["classic_gravity"], ui_panels.ClassicCreatePanel
        )
        window.scene_changed()
        # its springs only, and the actions it can't use disabled
        assert panel.table.rowCount() == 1
        for widget in (
            panel.create_buttons[colliders.CAPSULE],
            panel.create_buttons[colliders.MESH],
            panel.fit_capsules_btn,
            panel.fit_radius_btn,
        ):
            assert not widget.isEnabled()
            assert "Classic Gravity" in widget.toolTip()
        assert panel.create_buttons[colliders.SPHERE].isEnabled()
        assert panel.fit_sphere_btn.isEnabled()
        # factory presets of the solver
        names = [
            window.preset_model.item(row).text()
            for row in range(window.preset_model.rowCount())
        ]
        assert {"Gravity Light", "Gravity Hanging"} <= set(names)
    finally:
        window.shutdown()
        window.deleteLater()


def test_factory_presets(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import presets

    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    path = presets.preset_path(presets.factory_folder(), "Gravity Hanging")
    preset = presets.read(path)
    assert presets.preset_type(preset) == "values"
    presets.apply_values(preset, [spring])
    values = gravity.get_params(spring)
    assert values["springGravityStrength"] == pytest.approx(3.0)
    # the gravity direction (scene up axis) is not taken from presets
    assert values["springGravityDirection"] == pytest.approx((0.0, -1.0, 0.0))


def test_refuses_own_colliders(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    control = _control(cmds)
    child = cmds.createNode("transform", name="ear_tip", parent=control)
    other = _control(cmds, "other", (5, 0, 0))
    spring = gravity.create([control], options={"direction": "x"})[0]
    own = colliders.create(colliders.SPHERE, control)
    under = colliders.create(colliders.SPHERE, child)
    outside = colliders.create(colliders.SPHERE, other)
    for network in (own, under, outside):
        registry.assign(network, [spring])
    # a spring pushing its own collider would be a cycle
    assert registry.assigned_springs(own) == []
    assert registry.assigned_springs(under) == []
    assert registry.assigned_springs(outside) == [spring]


def test_broken_collider_skipped(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import registry

    control = _control(cmds)
    spring = gravity.create([control], options={"direction": "x"})[0]
    plane = colliders.create(colliders.PLANE)
    sphere = colliders.create(colliders.SPHERE)
    registry.assign(plane, [spring])
    registry.assign(sphere, [spring])
    # the plane object deleted outside the tool: the network stays
    cmds.delete(colliders.collider_transform(plane))
    assert cmds.objExists(plane)
    registry.unassign(sphere, [spring])
    registry.assign(sphere, [spring])
    registry.unassign(plane, [spring])
    solver = _solvers(cmds, spring)[0]
    assert cmds.getAttr(solver + ".colliders_list", multiIndices=True) == [0]
    colliders.delete([plane])
    assert not cmds.objExists(plane)


def test_create_and_fit_many(gravity):
    from maya import cmds

    from mgear.animbits.spring_manager import colliders
    from mgear.animbits.spring_manager import fit

    joints = []
    for index in range(3):
        joint = cmds.createNode("joint", name="spine%d_jnt" % index)
        cmds.setAttr(joint + ".translateY", index * 4)
        joints.append(joint)
    created = colliders.create_many(colliders.SPHERE, joints, {"radius": 0.5})
    assert [colliders.driver(n) for n in created] == joints
    assert all(colliders.get_dimensions(n)["radius"] == 0.5 for n in created)
    # one undo step for all of them
    cmds.undo()
    assert not [n for n in created if cmds.objExists(n)]
    # no driver: one collider in world space
    assert len(colliders.create_many(colliders.PLANE, [])) == 1

    body = cmds.polyCylinder(
        radius=1.5, height=12, subdivisionsAxis=24, constructionHistory=False
    )[0]
    cmds.move(0, 4, 0, body)
    spheres = fit.fit_spheres(body, joints[:2], fit.FitOptions(method="raycast"))
    assert [colliders.driver(n) for n in spheres] == joints[:2]
    for network in spheres:
        assert colliders.get_dimensions(network)["radius"] > 1.0
