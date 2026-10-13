"""mgear.core.curve get_length_ratio_at_point test"""

import pytest


def test_length_ratio_at_point(setup_path):
    from maya import cmds
    from mgear.core import curve

    cmds.file(new=True, force=True)
    crv = cmds.curve(degree=1, point=[(0, 0, 0), (4, 0, 0)])
    assert curve.get_length_ratio_at_point(crv, (0, 0, 0)) == pytest.approx(0)
    assert curve.get_length_ratio_at_point(crv, (1, 3, 0)) == pytest.approx(0.25)
    assert curve.get_length_ratio_at_point(crv, (9, 0, 0)) == pytest.approx(1)
    # world space: a moved curve
    cmds.setAttr(crv + ".translateX", 10)
    assert curve.get_length_ratio_at_point(crv, (12, 0, 0)) == pytest.approx(0.5)
