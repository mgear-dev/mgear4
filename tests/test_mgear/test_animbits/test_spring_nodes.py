"""mgear_springNode and mgear_springGravityNode solver test (C++ plug-in)"""

import pytest

NODE_TYPES = ("mgear_springNode", "mgear_springGravityNode")


def _spring(cmds, node_type):
    node = cmds.createNode(node_type)
    cmds.connectAttr("time1.outTime", node + ".time")
    cmds.setAttr(node + ".damping", 0.2)
    cmds.setAttr(node + ".stiffness", 0.3)
    return node


def _play(cmds, node, frames, goal, extra_reads=None):
    """Play frames in order, returning the output on each frame.

    Args:
        goal (callable): ``goal(frame)`` returning the goal position.
        extra_reads (dict, optional): ``{frame: count}`` of additional
            evaluations of the frame (as a bake or the viewport do).
    """
    outputs = []
    for frame in frames:
        cmds.currentTime(frame)
        cmds.setAttr(node + ".goal", *goal(frame))
        value = cmds.getAttr(node + ".output")[0]
        for _ in range((extra_reads or {}).get(frame, 0)):
            cmds.dgdirty(node)
            again = cmds.getAttr(node + ".output")[0]
            assert again == pytest.approx(value, abs=1e-5)
        outputs.append(value)
    return outputs


def _step_goal(frame):
    return (10.0 if frame > 3 else 0.0, 0.0, 0.0)


@pytest.mark.parametrize("node_type", NODE_TYPES)
def test_one_step_per_frame(solvers, node_type):
    cmds = solvers
    frames = list(range(1, 20))
    clean = _play(cmds, _spring(cmds, node_type), frames, _step_goal)
    # extra evaluations on frames 5 and 6 must not advance the simulation
    reread = _play(cmds, _spring(cmds, node_type), frames, _step_goal, {5: 3, 6: 2})
    for expected, value in zip(clean, reread):
        assert value == pytest.approx(expected, abs=1e-5)
    # the spring did move: the test is not trivially passing
    assert max(value[0] for value in clean) > 10.5


def test_same_frame_uses_current_inputs(solvers):
    cmds = solvers
    node = _spring(cmds, "mgear_springNode")
    _play(cmds, node, range(1, 8), _step_goal)
    first = cmds.getAttr(node + ".output")[0]
    # a parameter edited on the frame re-solves that frame
    cmds.setAttr(node + ".intensity", 0.0)
    assert cmds.getAttr(node + ".output")[0] == pytest.approx(_step_goal(7))
    cmds.setAttr(node + ".intensity", 1.0)
    assert cmds.getAttr(node + ".output")[0] == pytest.approx(first, abs=1e-5)


def _ground_spring(cmds, ground_y):
    node = _spring(cmds, "mgear_springGravityNode")
    cmds.setAttr(node + ".gravity", 2.0)
    cmds.setAttr(node + ".use_ground", True)
    cmds.setAttr(node + ".collide_softness", 0.0)
    matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, ground_y, 0, 1]
    cmds.setAttr(node + ".ground_transform", matrix, type="matrix")
    return node


@pytest.mark.parametrize("ground_y", (0.0, 5.0, -3.0))
def test_gravity_ground(solvers, ground_y):
    cmds = solvers
    node = _ground_spring(cmds, ground_y)
    heights = [y for _, y, _ in _play(cmds, node, range(1, 40), lambda f: (0, 0, 0))]
    # gravity pulls the point down, the ground keeps it on the plane
    assert min(heights[5:]) >= ground_y - 1e-3
    assert heights[-1] == pytest.approx(max(ground_y, heights[-1]), abs=1e-3)


def test_gravity_tilted_ground(solvers):
    cmds = solvers
    node = _ground_spring(cmds, 0.0)
    # plane rotated 90 degrees around Z: its "up" is world -X
    matrix = [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 2, 0, 0, 1]
    cmds.setAttr(node + ".ground_transform", matrix, type="matrix")
    cmds.setAttr(node + ".gravity_direction", 1, 0, 0)
    xs = [x for x, _, _ in _play(cmds, node, range(1, 40), lambda f: (0, 0, 0))]
    # gravity along +X stops at the plane at x = 2
    assert max(xs[5:]) <= 2.0 + 1e-3
    assert xs[-1] == pytest.approx(2.0, abs=0.05)
