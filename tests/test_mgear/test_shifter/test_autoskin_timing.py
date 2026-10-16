"""Shifter guide autoskin_timing tests"""

import json
from types import SimpleNamespace

import pytest

# Post custom step writing the mesh skin influences to a json file, then
# skinning the mesh to the head joint when it has no skin cluster
POST_STEP = r"""import json

from maya import cmds
from mgear.core import skin

cluster = skin.getSkinCluster("{mesh}")
influences = []
if cluster:
    influences = cmds.skinCluster(cluster.name(), query=True, influence=True)
with open(r"{out}", "w") as f:
    json.dump(influences, f)
if not cluster and {skin_head}:
    cmds.skinCluster("{head}", "{mesh}", toSelectedBones=True)
"""


def _post_step(tmp_path, lips_face, skin_head=False):
    """Write the post custom step and set it on the guide.

    Returns:
        pathlib.Path: The json file the step writes the influences to.
    """
    from maya import cmds

    out = tmp_path / "influences.json"
    step = tmp_path / "record_influences.py"
    step.write_text(
        POST_STEP.format(
            mesh=lips_face["mesh"],
            head=lips_face["head_jnt"],
            out=out.as_posix(),
            skin_head=skin_head,
        )
    )
    cmds.setAttr("guide.doPostCustomStep", True)
    cmds.setAttr("guide.postCustomStep", str(step), type="string")
    return out


def _skin_to_head(lips_face):
    from maya import cmds

    cmds.skinCluster(lips_face["head_jnt"], lips_face["mesh"], toSelectedBones=True)


def _build(selection="guide"):
    from maya import cmds
    from mgear import shifter

    cmds.select(selection)
    rig = shifter.Rig()
    rig.buildFromSelection()
    cmds.select(clear=True)
    return rig


def _influences(mesh):
    from maya import cmds
    from mgear.core import skin

    cluster = skin.getSkinCluster(mesh)
    if not cluster:
        return []
    return cmds.skinCluster(cluster.name(), query=True, influence=True)


def _lips_joints():
    from maya import cmds

    return cmds.ls("lips_C0_upLip*_jnt", "lips_C0_lowLip*_jnt", type="joint")


def _skin_file_to_head(lips_face, tmp_path, pack):
    """Export a skin of the mesh to the head joint, then unbind the mesh.

    Returns:
        str: The skin file, or skin pack, path.
    """
    import mgear.pymaya as pm
    from maya import cmds
    from mgear.core import skin

    _skin_to_head(lips_face)
    mesh = pm.PyNode(lips_face["mesh"])
    if pack:
        path = (tmp_path / "head.gSkinPack").as_posix()
        skin.exportSkinPack(path, [mesh])
    else:
        path = (tmp_path / "head.gSkin").as_posix()
        skin.exportSkin(path, [mesh])
    cmds.delete(skin.getSkinCluster(lips_face["mesh"]).name())
    cmds.setAttr("guide.importSkin", True)
    cmds.setAttr("guide.skin", path, type="string")
    return path


def _strongest_influences(mesh, vertices):
    """Get the influence with the highest weight of each vertex."""
    from maya import cmds
    from mgear.core import skin

    cluster = skin.getSkinCluster(mesh).name()
    names = cmds.skinCluster(cluster, query=True, influence=True)
    strongest = []
    for vertex in vertices:
        component = "{}.vtx[{}]".format(mesh, vertex)
        values = cmds.skinPercent(cluster, component, query=True, value=True)
        strongest.append(max(zip(values, names))[1])
    return strongest


def test_default_timing(lips_guide):
    from maya import cmds

    lips_guide()
    assert cmds.getAttr("guide.autoskin_timing") == 0


def test_older_guide_finalize_timing(lips_guide, lips_face, tmp_path, count_calls):
    from maya import cmds

    import mgear

    logs = count_calls(mgear, "log", lambda args, kwargs: str(args[0]))
    _skin_to_head(lips_face)
    lips_guide(doSkin=True)
    # an older guide builds with the Component Finalize timing, silently
    cmds.deleteAttr("guide.autoskin_timing")
    out = _post_step(tmp_path, lips_face)
    _build()
    assert not [log for log in logs if "autoskin_timing" in log]
    # the post step already sees the autoskin
    assert set(_lips_joints()) <= set(json.loads(out.read_text()))


def test_blueprint_timing(setup_path, monkeypatch):
    from mgear.shifter import guide

    monkeypatch.setattr(
        guide,
        "load_blueprint_guide",
        lambda path: {"guide_root": {"param_values": {"autoskin_timing": 1}}},
    )
    rig_guide = guide.Rig()
    rig_guide.values["use_blueprint"] = True
    rig_guide.values["blueprint_path"] = "blueprint.sgt"
    # the autoskin options are skinning settings
    rig_guide.values["override_rig_settings"] = True
    rig_guide.values["override_skinning"] = False
    assert rig_guide.getMergedOptions()["autoskin_timing"] == 1
    rig_guide.values["override_skinning"] = True
    assert rig_guide.getMergedOptions()["autoskin_timing"] == 0


def test_after_post_steps(lips_guide, lips_face, tmp_path, count_calls):
    from maya import cmds
    from mgear import shifter

    collected = count_calls(
        shifter.Rig,
        "collect_build_data",
        lambda args, kwargs: _influences(lips_face["mesh"]),
    )
    lips_guide(doSkin=True)
    cmds.setAttr("guide.autoskin_timing", 2)
    cmds.setAttr("guide.data_collector", True)
    path = (tmp_path / "rig_data.json").as_posix()
    cmds.setAttr("guide.data_collector_path", path, type="string")
    out = _post_step(tmp_path, lips_face, skin_head=True)
    _build()
    # the post step found the mesh unskinned and skinned it to the head
    assert json.loads(out.read_text()) == []
    joints = _lips_joints()
    assert joints
    influences = _influences(lips_face["mesh"])
    assert set(joints) <= set(influences)
    assert lips_face["head_jnt"] in influences
    strongest = _strongest_influences(lips_face["mesh"], lips_face["vertices"])
    assert set(strongest) <= set(joints)
    # the autoskin ran before the build data collection
    assert len(collected) == 1
    assert set(joints) <= set(collected[0])


def test_skin_import_replaces_finalize_autoskin(lips_guide, lips_face, tmp_path):
    lips_guide(doSkin=True)
    _skin_file_to_head(lips_face, tmp_path, pack=False)
    _build()
    # the guide skin import runs after the component Finalize autoskin
    strongest = _strongest_influences(lips_face["mesh"], lips_face["vertices"])
    assert set(strongest) == {lips_face["head_jnt"]}


def test_after_rig_finalize_skin_pack(lips_guide, lips_face, tmp_path):
    from maya import cmds

    lips_guide(doSkin=True)
    cmds.setAttr("guide.autoskin_timing", 1)
    _skin_file_to_head(lips_face, tmp_path, pack=True)
    out = _post_step(tmp_path, lips_face)
    _build()
    joints = _lips_joints()
    assert joints
    # the autoskin ran on top of the imported skin pack, before the post step
    assert set(joints) <= set(json.loads(out.read_text()))
    influences = _influences(lips_face["mesh"])
    assert lips_face["head_jnt"] in influences
    strongest = _strongest_influences(lips_face["mesh"], lips_face["vertices"])
    assert set(strongest) <= set(joints)


def test_build_from_dict(lips_guide, lips_face):
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.shifter import io

    _skin_to_head(lips_face)
    lips_guide(doSkin=True)
    cmds.setAttr("guide.autoskin_timing", 2)
    conf = io.get_guide_template_dict(pm.PyNode("guide"))
    cmds.delete("guide")
    io.build_from_file(conf=conf)
    joints = _lips_joints()
    assert joints
    assert set(joints) <= set(_influences(lips_face["mesh"]))


def test_partial_build(lips_guide, lips_face, count_calls):
    from maya import cmds
    from mgear.core import skin

    calls = count_calls(skin, "apply_topological_autoskin")
    _skin_to_head(lips_face)
    root = lips_guide(doSkin=True)
    cmds.setAttr("guide.autoskin_timing", 2)
    _build(root)
    assert len(calls) == 1
    assert set(_lips_joints()) <= set(_influences(lips_face["mesh"]))


def test_new_build_clears_queue(setup_path):
    from mgear import shifter

    rig = shifter.Rig()
    rig.deferred_autoskins.append((None, lambda: None))
    rig._begin_build()
    assert rig.deferred_autoskins == []


def _fake_component(name):
    return SimpleNamespace(fullName=name, type="lips_01")


def _rig(timing, autoskins):
    from mgear import shifter

    rig = shifter.Rig()
    rig.options = {"autoskin_timing": timing}
    rig.deferred_autoskins = list(autoskins)
    return rig


def test_queue_runs_at_its_timing_only(setup_path):
    from mgear.shifter import component

    ran = []
    entry = (_fake_component("lips_C0"), lambda: ran.append(1))
    rig = _rig(component.AUTOSKIN_AFTER_POST_STEPS, [entry])
    rig.run_deferred_autoskins(component.AUTOSKIN_AFTER_RIG_FINALIZE)
    assert ran == []
    assert rig.deferred_autoskins == [entry]
    rig.run_deferred_autoskins(component.AUTOSKIN_AFTER_POST_STEPS)
    assert ran == [1]
    assert rig.deferred_autoskins == []


def test_failing_autoskin_logged(setup_path, count_calls):
    import mgear

    errors = count_calls(
        mgear,
        "log",
        lambda args, kwargs: (
            str(args[0]) if len(args) > 1 and args[1] == mgear.sev_error else None
        ),
    )
    ran = []

    def failing():
        raise RuntimeError("mesh deleted")

    rig = _rig(
        2,
        [
            (_fake_component("eyelid_L0"), failing),
            (_fake_component("lips_C0"), lambda: ran.append("lips_C0")),
        ],
    )
    rig.run_deferred_autoskins(2)
    assert ran == ["lips_C0"]
    assert len(errors) == 1
    assert "eyelid_L0" in errors[0]
    assert "mesh deleted" in errors[0]
    assert rig.deferred_autoskins == []


def test_cancelled_build_runs_nothing(setup_path):
    ran = []
    rig = _rig(2, [(_fake_component("lips_C0"), lambda: ran.append(1))])
    rig.stopBuild = True
    rig.run_deferred_autoskins(2)
    assert ran == []
    assert rig.deferred_autoskins == []


@pytest.mark.parametrize(
    "autoskin, timing, now, deferred",
    [
        (None, None, True, False),
        (True, 0, True, False),
        (True, 1, False, True),
        (True, 2, False, True),
        (False, 0, False, False),
        (False, 1, False, False),
    ],
)
def test_run_autoskin(setup_path, autoskin, timing, now, deferred):
    from mgear.shifter import component

    options = {}
    if autoskin is not None:
        options["autoskin"] = autoskin
    if timing is not None:
        options["autoskin_timing"] = timing
    comp = SimpleNamespace(options=options, rig=SimpleNamespace(deferred_autoskins=[]))
    ran = []

    def func():
        ran.append(1)

    component.Main.run_autoskin(comp, func)
    assert ran == ([1] if now else [])
    assert comp.rig.deferred_autoskins == ([(comp, func)] if deferred else [])
