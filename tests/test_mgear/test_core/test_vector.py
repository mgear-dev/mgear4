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
    from maya import OpenMaya
    import pymel.core as pm
    # mGear imports
    from mgear.core.vector import linear_interpolate

    _value = [2, 5, 8]

    v_1 = [0, 0, 0]
    v_2 = _value
    result = linear_interpolate(v_1, v_2)
    assert type(result) == OpenMaya.MVector
    assert [result[0], result[1], result[2]] == [1, 2.5, 4]

    pm.newFile(force=True)
    v_1 = pm.createNode("transform")
    v_2 = pm.createNode("transform")
    v_2.translate.set(_value[0], _value[1], _value[2])
    result = linear_interpolate(v_1, v_2)
    assert [result[0], result[1], result[2]] == [1, 2.5, 4]


def test_get_plane_normal(run_with_maya_pymel, setup_path):
    # Maya imports
    from maya import OpenMaya
    import pymel.core as pm
    # mGear imports
    from mgear.core.vector import get_plane_normal

    vector_a = OpenMaya.MVector(0, 0, 0)
    vector_b = OpenMaya.MVector(1, 0, 0)
    vector_c = OpenMaya.MVector(0, 0, 1)
    result = get_plane_normal(vector_a, vector_b, vector_c)
    assert type(result) == OpenMaya.MVector
    assert [result[0], result[1], result[2]] == [0, 1, 0]

    pm.newFile(force=True)
    vector_a = pm.createNode("transform")
    vector_b = pm.createNode("transform")
    vector_c = pm.createNode("transform")
    vector_b.translate.set(-1, 0, 0)
    vector_c.translate.set(0, 0, 1)
    result = get_plane_normal(vector_a, vector_b, vector_c)
    assert [result[0], result[1], result[2]] == [0, -1, 0]

    result = get_plane_normal(list(vector_a.getTranslation()),
                              list(vector_b.getTranslation()),
                              list(vector_c.getTranslation()))
    assert [result[0], result[1], result[2]] == [0, -1, 0]
