"""mgear.core.vector test"""


def test_get_distance(run_with_maya_pymel, setup_path):
    # Maya imports
    from maya import OpenMaya
    import pymel.core as pm
    # mGear imports
    from mgear.core.vector import get_distance

    v_1 = [0, 0, 0]
    v_2 = [1, 0, 0]
    assert get_distance(v_1, v_2) == 1.0

    v_1 = OpenMaya.MVector(0, 0, 0)
    v_2 = OpenMaya.MVector(1, 0, 0)
    assert get_distance(v_1, v_2) == 1.0

    pm.newFile(force=True)
    v_1 = pm.createNode("transform")
    v_2 = pm.createNode("transform")
    v_2.translate.set(10, 5, 7)
    distance = pm.createNode("distanceBetween")
    v_1.worldMatrix >> distance.inMatrix1
    v_2.worldMatrix >> distance.inMatrix2
    distance_value = distance.distance.get()
    assert get_distance(v_1, v_2) == distance_value


def test_linear_interpolate(run_with_maya_pymel, setup_path):
    # Maya imports
    import pymel.core as pm
    # mGear imports
    from mgear.core.vector import linear_interpolate

    _value = [2, 5, 8]

    v_1 = [0, 0, 0]
    v_2 = _value
    result = linear_interpolate(v_1, v_2)
    assert [result[0], result[1], result[2]] == [1, 2.5, 4]

    pm.newFile(force=True)
    v_1 = pm.createNode("transform")
    v_2 = pm.createNode("transform")
    v_2.translate.set(_value[0], _value[1], _value[2])

    result = linear_interpolate(v_1, v_2)
    assert [result[0], result[1], result[2]] == [1, 2.5, 4]
