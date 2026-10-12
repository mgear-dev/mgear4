"""mgear.core.vector loop frame, extremes and side detection test"""

import math

import pytest


def _rotate_x(point, angle):
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = point
    return (x, y * c - z * s, y * s + z * c)


def _rotate_y(point, angle):
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = point
    return (x * c + z * s, y, -x * s + z * c)


def _ellipse(count=16, width=2.0, height=1.0):
    return [
        (
            width * math.cos(2 * math.pi * i / count),
            height * math.sin(2 * math.pi * i / count),
            0.0,
        )
        for i in range(count)
    ]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_tilted_circle_frame(setup_path):
    from mgear.core import vector

    tilt = math.radians(30)
    points = [_rotate_x(p, tilt) for p in _ellipse(width=1.0)]
    frame = vector.get_loop_frame(points, normal_hint=(0, 0, 1))
    expected = _rotate_x((0, 0, 1), tilt)
    assert frame["normal"] == pytest.approx(expected, abs=1e-6)
    assert frame["lateral"] == pytest.approx((1, 0, 0), abs=1e-6)
    axes = (frame["lateral"], frame["up"], frame["normal"])
    for i, a in enumerate(axes):
        assert _dot(a, a) == pytest.approx(1.0)
        for b in axes[i + 1 :]:
            assert _dot(a, b) == pytest.approx(0.0, abs=1e-9)
    # right handed: lateral x up = normal
    cross = vector._cross(frame["lateral"], frame["up"])
    assert cross == pytest.approx(frame["normal"], abs=1e-9)
    assert frame["matrix"][12:15] == pytest.approx([0, 0, 0], abs=1e-9)


def test_hint_flips_normal(setup_path):
    from mgear.core import vector

    points = _ellipse()
    assert vector.get_loop_frame(points, (0, 0, 1))["normal"] == pytest.approx(
        (0, 0, 1)
    )
    assert vector.get_loop_frame(points, (0, 0, -1))["normal"] == pytest.approx(
        (0, 0, -1)
    )


def test_lateral_hint_fallback(setup_path):
    from mgear.core import vector

    # loop facing +X: the default X lateral hint is parallel to the normal
    points = [_rotate_y(p, math.radians(90)) for p in _ellipse()]
    frame = vector.get_loop_frame(points, normal_hint=(1, 0, 0))
    assert frame["normal"] == pytest.approx((1, 0, 0), abs=1e-6)
    assert abs(_dot(frame["lateral"], frame["normal"])) < 1e-9


def test_extremes_follow_frame(setup_path):
    from mgear.core import vector

    angle = math.radians(90)
    points = [_rotate_y(p, angle) for p in _ellipse()]
    frame = vector.get_loop_frame(
        points,
        normal_hint=_rotate_y((0, 0, 1), angle),
        lateral_hint=_rotate_y((1, 0, 0), angle),
    )
    extremes = vector.extremes_in_frame(points, frame)
    # long axis ends of the ellipse, not the world X extremes
    assert sorted((extremes["lateral_min"], extremes["lateral_max"])) == [0, 8]
    assert sorted((extremes["up_min"], extremes["up_max"])) == [4, 12]
    assert extremes["up_max"] == 4


def test_detect_side(setup_path):
    from mgear.core import vector

    assert vector.detect_side(1.0) == "L"
    assert vector.detect_side(-1.0) == "R"
    assert vector.detect_side(0.0) == "C"
    assert vector.detect_side(0.0005) == "C"
