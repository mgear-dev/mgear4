"""mgear.core.vector test"""


def test_get_distance(setup_path):
    # Maya imports
    from maya import OpenMaya
    # mGear imports
    from mgear.core.vector import get_distance

    import maya.standalone
    maya.standalone.initialize()

    v_1 = [0, 0, 0]
    v_2 = [1, 0, 0]
    assert get_distance(v_1, v_2) == 1.0

    v_1 = OpenMaya.MVector(0, 0, 0)
    v_2 = OpenMaya.MVector(1, 0, 0)
    assert get_distance(v_1, v_2) == 1.0

    maya.standalone.uninitialize()
