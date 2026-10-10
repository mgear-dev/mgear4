"""Shifter component build data collection tests"""

import json

POST_STEP = r"""import json

import mgear.shifter.custom_step as cstp


class CustomShifterStep(cstp.customShifterMainStep):
    def setup(self):
        self.name = "read_build_data"

    def run(self):
        data = self.component("arm_C0").build_data
        with open(r"{out}", "w") as f:
            json.dump(
                {{
                    "joints": [j["Name"] for j in data["Joints"]],
                    "controls": [c["Name"] for c in data["Controls"]],
                    "shapes": all(c["Shape"] for c in data["Controls"]),
                    "relatives": sorted(data["relatives"]),
                }},
                f,
            )
"""


def _components(rig):
    return [rig.components[name] for name in rig.componentsIndex]


def test_collector_off_skips_collection(build_rig, curve_data_calls):
    rig = build_rig()
    assert curve_data_calls == []
    assert all(c._build_data_pending for c in _components(rig))


def test_post_step_reads_build_data(build_rig, curve_data_calls, tmp_path):
    out = tmp_path / "post_step_data.json"
    step = tmp_path / "read_build_data.py"
    step.write_text(POST_STEP.format(out=out))

    rig = build_rig(post_step=str(step))

    data = json.loads(out.read_text())
    arm = rig.components["arm_C0"]
    assert data["joints"] == [j.name() for j in arm.jointList]
    assert arm.controlers
    assert data["controls"] == [c.name() for c in arm.controlers]
    assert data["shapes"] is True
    assert data["relatives"] == sorted(arm.relatives)
    # Only the component the step read was collected.
    assert len(curve_data_calls) == len(arm.controlers)
    assert rig.components["control_C0"]._build_data_pending


def test_build_data_collected_once(build_rig, curve_data_calls):
    rig = build_rig()
    arm = rig.components["arm_C0"]
    first = arm.build_data
    calls = len(curve_data_calls)
    assert calls == len(arm.controlers)
    assert arm.build_data is first
    assert len(curve_data_calls) == calls


def test_collector_on_collects_at_build(build_rig, curve_data_calls, tmp_path):
    out = tmp_path / "rig_data.json"
    rig = build_rig(data_collector_path=str(out))

    components = _components(rig)
    assert not any(c._build_data_pending for c in components)
    assert len(curve_data_calls) == sum(len(c.controlers) for c in components)

    data = json.loads(out.read_text())
    assert [c["FullName"] for c in data["Components"]] == rig.componentsIndex
    for comp_data, comp in zip(data["Components"], components):
        assert [j["Name"] for j in comp_data["Joints"]] == [
            j.name() for j in comp.jointList
        ]
        assert [c["Name"] for c in comp_data["Controls"]] == [
            c.name() for c in comp.controlers
        ]
        assert all(c["Shape"] for c in comp_data["Controls"])


def test_assigned_build_data_is_kept(build_rig, curve_data_calls):
    rig = build_rig()
    arm = rig.components["arm_C0"]
    arm.build_data = {"custom": True}
    assert arm.build_data == {"custom": True}
    assert curve_data_calls == []


def test_build_data_before_component_finished(build_rig, curve_data_calls):
    rig = build_rig()
    arm = rig.components["arm_C0"]
    # Before step 05 nothing is pending (the state set here), so writes
    # during the build don't trigger an early collection.
    arm._build_data_pending = False
    arm._build_data = {}
    arm.build_data["early"] = 1
    assert arm.build_data == {"early": 1}
    assert curve_data_calls == []
