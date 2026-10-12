"""mgear.core.settings_schema test"""

import json

import pytest


@pytest.fixture
def ss(setup_path):
    from mgear.core import settings_schema

    return settings_schema


@pytest.fixture
def schema(ss):
    return [
        ss.Param("namePrefix", "string", "eye", scope="tool"),
        ss.Param("edgeLoop", "string", "", legacy_keys=("edge_loop",)),
        ss.Param("everyNVertex", "long", 1, minimum=1, maximum=100),
        ss.Param("offset", "double", 0.05, minimum=0.0),
        ss.Param("doSkin", "bool", True),
        ss.Param("loopType", "enum", 0, choices=("edge", "vertex")),
    ]


def test_defaults(ss, schema):
    assert ss.defaults(schema) == {
        "namePrefix": "eye",
        "edgeLoop": "",
        "everyNVertex": 1,
        "offset": 0.05,
        "doSkin": True,
        "loopType": 0,
    }
    with pytest.raises(ValueError):
        ss.Param("bad", "float", 0)


def test_migrate_legacy_eye_file(ss, schema):
    data = {"namePrefix": "lid", "edgeLoop": "m.e[1]", "blinkH": 20, "foo": 1}
    settings, warnings = ss.migrate(data, schema, dropped_keys=("blinkH",))
    assert "blinkH" not in settings
    assert "foo" not in settings
    assert settings["namePrefix"] == "lid"
    assert settings["edgeLoop"] == "m.e[1]"
    assert settings["everyNVertex"] == 1
    assert any("blinkH" in w for w in warnings)
    assert any("foo" in w for w in warnings)


def test_migrate_renamed_key(ss, schema):
    settings, _ = ss.migrate({"edge_loop": "m.e[3]"}, schema)
    assert settings["edgeLoop"] == "m.e[3]"
    # the current key wins over the legacy one
    settings, _ = ss.migrate({"edge_loop": "old", "edgeLoop": "new"}, schema)
    assert settings["edgeLoop"] == "new"


def test_coerce(ss, schema):
    settings = ss.coerce(
        {
            "namePrefix": None,
            "everyNVertex": 0,
            "offset": "0.5",
            "doSkin": 0,
            "loopType": "vertex",
            "other": [1],
        },
        schema,
    )
    assert settings == {
        "namePrefix": "",
        "everyNVertex": 1,
        "offset": 0.5,
        "doSkin": False,
        "loopType": 1,
        "other": [1],
    }
    assert ss.coerce({"everyNVertex": 500, "loopType": 7}, schema) == {
        "everyNVertex": 100,
        "loopType": 0,
    }
    assert ss.choice_name(schema, "loopType", 1) == "vertex"


def test_filter_scope(ss, schema):
    data = ss.defaults(schema)
    shared = ss.filter_scope(data, schema, "shared")
    assert "namePrefix" not in shared
    assert "edgeLoop" in shared
    assert ss.filter_scope(data, schema, "tool") == {"namePrefix": "eye"}


def test_file_round_trip(ss, schema, tmp_path, run_with_maya_standalone):
    path = str(tmp_path / "left.eyes")
    data = dict(ss.defaults(schema), everyNVertex=3, loopType=1)
    ss.save_settings(path, "eye_rigger", 3, data)
    settings, warnings = ss.load_settings(path, "eye_rigger", schema)
    assert settings == data
    assert warnings == []
    with pytest.raises(ValueError):
        ss.load_settings(path, "lips_rigger", schema)


def test_legacy_flat_file(ss, schema, tmp_path):
    path = str(tmp_path / "legacy.eyes")
    with open(path, "w") as f:
        json.dump({"namePrefix": "eye", "everyNVertex": 0, "blinkH": 20}, f)
    settings, warnings = ss.load_settings(
        path, "eye_rigger", schema, dropped_keys=("blinkH",)
    )
    assert settings["everyNVertex"] == 1
    assert len(warnings) == 1


def test_upgrade_hook(ss, schema, tmp_path):
    import json

    def upgrade(data):
        if "loopType" not in data:
            data["loopType"] = 0
        return data

    settings, _ = ss.migrate({"edgeLoop": "m.e[1]"}, schema, upgrade=upgrade)
    assert settings["loopType"] == 0
    path = str(tmp_path / "legacy.eyes")
    with open(path, "w") as f:
        json.dump({"edgeLoop": "m.e[1]"}, f)
    schema_vertex = [
        (
            param
            if param.key != "loopType"
            else ss.Param("loopType", "enum", 1, choices=("edge", "vertex"))
        )
        for param in schema
    ]
    settings, _ = ss.load_settings(path, "eye_rigger", schema_vertex)
    assert settings["loopType"] == 1
    settings, _ = ss.load_settings(path, "eye_rigger", schema_vertex, upgrade=upgrade)
    assert settings["loopType"] == 0
