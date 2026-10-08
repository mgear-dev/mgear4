"""Scene builders shared by the Spring Manager tests (need Maya)."""


def make_control(cmds, name, parent, position):
    npo = cmds.createNode("transform", name=name + "_npo", parent=parent)
    cmds.setAttr(npo + ".translate", *position)
    control = cmds.circle(name=name + "_ctl", constructionHistory=False)[0]
    control = cmds.parent(control, npo, relative=True)[0]
    return cmds.ls(control, long=True)[0]


def build_tail_rig(cmds, namespace=""):
    """Root with a 3 control tail; the rig moves in X from frame 1 to 10."""
    prefix = namespace + ":" if namespace else ""
    if namespace and not cmds.namespace(exists=namespace):
        cmds.namespace(add=namespace)
    rig = cmds.createNode("transform", name=prefix + "rig")
    controls = [make_control(cmds, prefix + "tail0", rig, (0, 10, 0))]
    for index in (1, 2):
        controls.append(
            make_control(cmds, prefix + "tail%d" % index, controls[-1], (3, 0, 0))
        )
    cmds.setKeyframe(rig, attribute="tx", time=1, value=0)
    cmds.setKeyframe(rig, attribute="tx", time=10, value=20)
    cmds.setKeyframe(controls[1], attribute="rz", time=1, value=0)
    cmds.setKeyframe(controls[1], attribute="rz", time=10, value=30)
    return rig, controls


def build_skirt(cmds):
    rig = cmds.createNode("transform", name="rig")
    root = make_control(cmds, "root", rig, (0, 10, 0))
    branches = []
    for name, direction in (("l", (2, 0, 0)), ("r", (-2, 0, 0))):
        first = make_control(cmds, name + "0", root, direction)
        branches.append([first, make_control(cmds, name + "1", first, direction)])
    cmds.setKeyframe(root, attribute="ry", time=1, value=0)
    cmds.setKeyframe(root, attribute="ry", time=10, value=40)
    return root, branches


def simulate(cmds, nodes, frames, query="translation"):
    """Step frames in order, reading the nodes (springs compute when read).

    Returns:
        dict: ``{frame: [world translation or matrix per node]}``.
    """
    out = {}
    for frame in frames:
        cmds.currentTime(frame)
        out[frame] = [
            cmds.xform(node, query=True, worldSpace=True, **{query: True})
            for node in nodes
        ]
    return out
