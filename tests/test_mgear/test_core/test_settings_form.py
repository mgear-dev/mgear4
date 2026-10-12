"""mgear.core.settings_form test"""

import pytest


@pytest.fixture
def form(qt_app):
    from maya import cmds
    from mgear.core import settings_form
    from mgear.core.settings_schema import Param

    cmds.file(new=True, force=True)
    schema = [
        Param("mesh", "string", "", kind="mesh"),
        Param("loop", "string", "", kind="vertices"),
        Param("corner", "string", "", kind="vertex"),
        Param("ctlSet", "string", "", kind="set"),
        Param("count", "long", 3, minimum=1, maximum=9),
        Param("size", "double", 0.5, minimum=0.0),
        Param("skin", "bool", True),
        Param("loopType", "enum", 0, choices=("edge", "vertex")),
    ]
    return settings_form.SettingsForm(
        schema,
        groups=[
            ("Geometry", ["mesh", "loop", "corner", "ctlSet"]),
            ("Rig", ["count", "size", "skin", "loopType"]),
        ],
    )


def test_round_trip(form):
    values = {
        "mesh": "head",
        "loop": "head.vtx[1:3]",
        "corner": "head.vtx[2]",
        "ctlSet": "rig_controllers_grp",
        "count": 5,
        "size": 0.25,
        "skin": False,
        "loopType": 1,
    }
    form.set_settings(dict(values, unknown=1))
    assert form.get_settings() == values
    # spin box range from the schema
    form.set_value("count", 50)
    assert form.value("count") == 9


def test_value_changed_signal(form):
    changes = []
    form.valueChanged.connect(lambda key, value: changes.append((key, value)))
    form.set_value("skin", False)
    form.set_value("loopType", 1)
    assert ("skin", False) in changes
    assert ("loopType", 1) in changes


def test_fill_from_selection(form):
    from maya import cmds

    plane = cmds.polyPlane(name="sheet", constructionHistory=False)[0]
    cmds.select(plane)
    assert form.fill_from_selection("mesh")
    assert form.value("mesh") == "sheet"
    cmds.select(["sheet.vtx[3]", "sheet.vtx[4]", "sheet.vtx[5]"])
    assert form.fill_from_selection("loop")
    assert form.value("loop") == "sheet.vtx[3:5]"
    # one vertex only
    assert not form.fill_from_selection("corner")
    cmds.select("sheet.vtx[4]")
    assert form.fill_from_selection("corner")
    assert form.value("corner") == "sheet.vtx[4]"
    locator = cmds.spaceLocator()[0]
    cmds.select(locator)
    assert not form.fill_from_selection("mesh")


def test_row_visibility(form):
    form.show()
    form.set_row_visible("loop", False)
    label, row = form.rows["loop"]
    assert not label.isVisible()
    assert not row.isVisible()
    form.set_row_visible("loop", True)
    assert row.isVisible()
    form.close()


def test_fill_set_from_selection(form):
    from maya import cmds

    controls = cmds.sets(name="controls_set", empty=True)
    cmds.select(controls, noExpand=True)
    assert form.fill_from_selection("ctlSet")
    assert form.value("ctlSet") == "controls_set"
    cmds.select(cmds.createNode("transform"))
    assert not form.fill_from_selection("ctlSet")


def test_bulk_set_emits_once(form):
    values = []
    bulk = []
    form.valueChanged.connect(lambda key, value: values.append(key))
    form.settingsChanged.connect(lambda: bulk.append(True))
    form.set_settings({"skin": False, "count": 5, "mesh": "head"})
    assert values == []
    assert bulk == [True]
    form.set_value("mesh", "other")
    assert values == ["mesh"]
