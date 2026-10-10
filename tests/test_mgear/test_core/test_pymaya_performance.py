"""mgear.pymaya wrapper construction and attribute lookup cost tests"""

import pytest


@pytest.fixture
def pymaya(setup_path):
    """The mgear.pymaya package, in a new scene with a test transform."""
    from maya import cmds

    import mgear.pymaya as pm

    cmds.file(new=True, force=True)
    cmds.createNode("transform", name="arm_L0_ctl")
    return pm


def _count_misses(monkeypatch, cls):
    """Record the names that miss the normal lookup on ``cls`` instances.

    Args:
        monkeypatch (pytest.MonkeyPatch): The pytest monkeypatch fixture.
        cls (type): A pymaya class with a custom ``__getattribute__``.

    Returns:
        list: Filled with the missed attribute names.
    """
    misses = []
    original = cls.__getattribute__

    def counting(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            misses.append(name)
        return original(self, name)

    monkeypatch.setattr(cls, "__getattribute__", counting)
    return misses


def test_node_construction_has_no_lookup_misses(pymaya, monkeypatch):
    from mgear.pymaya import node

    misses = _count_misses(monkeypatch, node._Node)
    pymaya.PyNode("arm_L0_ctl")
    assert misses == []


def test_attribute_construction_has_no_lookup_misses(pymaya, monkeypatch):
    from mgear.pymaya import attr

    misses = _count_misses(monkeypatch, attr.Attribute)
    pymaya.PyNode("arm_L0_ctl.translateX")
    assert misses == []


def test_no_string_shims_on_instance(pymaya):
    from mgear.pymaya import base

    ctl = pymaya.PyNode("arm_L0_ctl")
    plug = pymaya.PyNode("arm_L0_ctl.translateX")
    for obj in (ctl, plug):
        assert not set(base.STR_FUNCS) & set(vars(obj))


def test_string_method_delegates_to_name(pymaya):
    ctl = pymaya.PyNode("arm_L0_ctl")
    assert ctl.upper() == "ARM_L0_CTL"
    assert ctl.count("_") == 2
    assert ctl.zfill(12) == "arm_L0_ctl".zfill(12)
    assert ctl.rpartition("_") == ("arm_L0", "_", "ctl")


def test_string_method_follows_rename(pymaya):
    from maya import cmds

    ctl = pymaya.PyNode("arm_L0_ctl")
    cmds.rename("arm_L0_ctl", "leg_R0_ctl")
    assert ctl.upper() == "LEG_R0_CTL"


def test_node_override_wins(pymaya):
    from mgear.pymaya import node

    ctl = pymaya.PyNode("arm_L0_ctl")
    assert type(ctl).startswith is node._Node.startswith
    assert ctl.startswith("arm")
    assert ctl.split("_") == ["arm", "L0", "ctl"]


def test_attribute_index_override_wins(pymaya):
    from maya import cmds

    cmds.addAttr("arm_L0_ctl", longName="weights", attributeType="double", multi=True)
    cmds.setAttr("arm_L0_ctl.weights[3]", 1.0)
    plug = pymaya.PyNode("arm_L0_ctl.weights[3]")
    assert plug.index() == 3


def test_attribute_access_uses_api(pymaya, count_calls):
    from mgear.pymaya import node

    ctl = pymaya.PyNode("arm_L0_ctl")
    objexists_calls = count_calls(node.cmds, "objExists")
    plug = ctl.tx
    assert objexists_calls == []
    assert plug.name() == "arm_L0_ctl.translateX"
    plug = ctl.translateY
    assert objexists_calls == []
    assert plug.name() == "arm_L0_ctl.translateY"


def test_compound_child_access(pymaya):
    from maya import cmds

    cmds.setAttr("arm_L0_ctl.translateZ", 4.0)
    ctl = pymaya.PyNode("arm_L0_ctl")
    assert ctl.t.tz.get() == 4.0
    assert ctl.translate.translateZ.name() == "arm_L0_ctl.translateZ"


def test_alias_attribute_access(pymaya):
    from maya import cmds

    cmds.aliasAttr("slide", "arm_L0_ctl.translateX")
    cmds.setAttr("arm_L0_ctl.translateX", 5.0)
    ctl = pymaya.PyNode("arm_L0_ctl")
    assert ctl.slide.get() == 5.0


def test_shape_attribute_fallback(pymaya):
    from maya import cmds

    crv = cmds.curve(degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 0, 0)])
    transform = pymaya.PyNode(crv)
    shape = cmds.listRelatives(crv, shapes=True)[0]
    assert transform.spans.get() == cmds.getAttr(shape + ".spans")


def test_component_access(pymaya):
    from maya import cmds

    cube = cmds.polyCube()[0]
    shape = cmds.listRelatives(cube, shapes=True)[0]
    # len() of a pymaya object is the length of its name, so iterate.
    assert len(list(pymaya.PyNode(shape).vtx)) == 8
    assert len(list(pymaya.PyNode(cube).vtx)) == 8


def test_missing_attribute_raises(pymaya):
    ctl = pymaya.PyNode("arm_L0_ctl")
    plug = pymaya.PyNode("arm_L0_ctl.translate")
    assert not hasattr(ctl, "no_such_attribute")
    assert not hasattr(plug, "no_such_child")
    with pytest.raises(AttributeError):
        ctl.no_such_attribute


def test_list_relatives_still_wraps_nodes(pymaya):
    from maya import cmds

    cmds.createNode("transform", name="child_a", parent="arm_L0_ctl")
    cmds.createNode("transform", name="child_b", parent="arm_L0_ctl")
    children = pymaya.listRelatives("arm_L0_ctl", children=True)
    assert [type(c).__name__ for c in children] == ["Transform", "Transform"]
    assert [c.name() for c in children] == ["child_a", "child_b"]


def test_string_attribute_value_stays_string(pymaya):
    from maya import cmds

    cmds.addAttr("arm_L0_ctl", longName="note", dataType="string")
    cmds.setAttr("arm_L0_ctl.note", "not a node", type="string")
    value = pymaya.getAttr("arm_L0_ctl.note")
    assert isinstance(value, str)
    assert value == "not a node"


@pytest.mark.parametrize(
    "text",
    ["Connected a.tx to b.tx.", "D:/projects/rig.ma", "C:\temp", "a	b"],
)
def test_non_name_strings_skip_lookup(pymaya, count_calls, text):
    from mgear.pymaya import cmd

    lookups = count_calls(cmd.bind, "PyNode")
    assert cmd._name_to_obj(text) == text
    assert lookups == []


def test_command_message_result_unchanged(pymaya):
    from maya import cmds

    cmds.createNode("transform", name="src")
    cmds.createNode("transform", name="dst")
    expected = cmds.connectAttr("src.translateX", "dst.translateX")
    cmds.disconnectAttr("src.translateX", "dst.translateX")
    result = pymaya.connectAttr("src.translateX", "dst.translateX")
    assert result == expected
    assert type(result) is type(expected)
    assert pymaya.dirmap(getAllMappings=True) == cmds.dirmap(getAllMappings=True)


def test_node_type_loaded_after_cache(pymaya, monkeypatch):
    """A node type missing from the cached type list is still wrapped.

    Simulates a plug-in loaded after pymaya first filled its node type cache.
    """
    from maya import cmds
    from mgear.pymaya import node

    typename = "plusMinusAverage"
    types = node.nt._NodeTypes__types
    if typename in types:
        monkeypatch.delitem(types, typename)
    stale = set(cmds.allNodeTypes()) - {typename}
    monkeypatch.setattr(node._NodeTypes, "_NodeTypes__all_node_types", stale)

    pma = cmds.createNode(typename, name="late_pma")
    wrapped = pymaya.PyNode(pma)
    assert type(wrapped).__name__ == "PlusMinusAverage"
    assert wrapped.name() == "late_pma"


def test_type_name_lookup_after_cache(pymaya, monkeypatch):
    """A type name missing from the cached type list is found on refresh."""
    from maya import cmds
    from mgear.pymaya import node

    typename = "plusMinusAverage"
    types = node.nt._NodeTypes__types
    if typename in types:
        monkeypatch.delitem(types, typename)
    stale = set(cmds.allNodeTypes()) - {typename}
    monkeypatch.setattr(node._NodeTypes, "_NodeTypes__all_node_types", stale)

    assert node.nt.PlusMinusAverage.__name__ == "PlusMinusAverage"


def test_unknown_node_type_name(pymaya):
    from mgear.pymaya import node

    assert node.nt.getTypeClass("no_such_node_type") is None
    assert not hasattr(node.nt, "NoSuchNodeType")


def test_private_type_probe_skips_maya(pymaya, count_calls):
    from maya import cmds
    from mgear.pymaya import node

    queries = count_calls(cmds, "allNodeTypes")
    assert not hasattr(node.nt, "_private")
    assert not hasattr(node.nt, "__length_hint__")
    assert queries == []


def test_construction_hasattr_bound(pymaya, monkeypatch, count_calls):
    import builtins

    with monkeypatch.context() as patch:
        calls = count_calls(builtins, "hasattr", patcher=patch)
        for _ in range(100):
            pymaya.PyNode("arm_L0_ctl")
    # Was 41 per wrapper before the STR_FUNCS moved to the class.
    assert len(calls) <= 100 * 2
