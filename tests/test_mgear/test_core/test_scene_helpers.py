"""mgear.core undo chunk, progress bar, plug, point count and log helpers test"""

import logging

import pytest


def test_undo_chunk_single_undo(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import utils

    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True, infinity=True)
    with utils.undo_chunk("test"):
        for i in range(3):
            cmds.createNode("transform", name="chunk_{}".format(i))
    cmds.undo()
    assert not cmds.ls("chunk_*")


def test_undo_chunk_closes_on_error(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import utils

    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True, infinity=True)
    with pytest.raises(ValueError):
        with utils.undo_chunk():
            cmds.createNode("transform", name="chunk_err")
            raise ValueError("boom")

    # The chunk is closed: a new edit is a separate undo step.
    cmds.createNode("transform", name="after_chunk")
    cmds.undo()
    assert not cmds.objExists("after_chunk")
    assert cmds.objExists("chunk_err")


def test_one_undo_uses_chunk(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import utils

    @utils.one_undo
    def build():
        cmds.createNode("transform", name="dec_a")
        cmds.createNode("transform", name="dec_b")
        return "done"

    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True, infinity=True)
    assert build() == "done"
    cmds.undo()
    assert not cmds.ls("dec_*")


def test_main_progress_bar_batch(run_with_maya_standalone, setup_path):
    from mgear.core import utils

    with utils.main_progress_bar("Testing", 3) as step:
        for _ in range(3):
            step("x")
        step()

    with pytest.raises(ValueError):
        with utils.main_progress_bar("Testing", 1):
            raise ValueError("boom")


def test_get_plug(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import utils

    cmds.file(new=True, force=True)
    sphere = cmds.polySphere()[0]
    ffd = cmds.lattice(sphere)[0]
    plug = utils.get_plug(ffd, "weightList")
    assert plug.isArray
    assert utils.get_plug(sphere, "tx").partialName() == "tx"
    with pytest.raises(RuntimeError):
        utils.get_plug("does_not_exist", "tx")


def test_get_point_count(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import utils

    cmds.file(new=True, force=True)
    sphere = cmds.polySphere()[0]
    assert utils.get_point_count(sphere) == 382

    curve = cmds.curve(point=[(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)])
    assert utils.get_point_count(curve) == 4

    surface = cmds.nurbsPlane(patchesU=1, patchesV=1, degree=3)[0]
    assert utils.get_point_count(surface) == 16

    lattice = cmds.lattice(sphere, divisions=(2, 3, 4))[1]
    assert utils.get_point_count(lattice) == 24


def test_qt_log_handler(qt_app):
    from mgear.core import pyqt
    from mgear.vendor.Qt import QtWidgets

    widget = QtWidgets.QPlainTextEdit()
    handler = pyqt.QtLogHandler(widget)
    logger = logging.getLogger("mgear.test.qt_log_handler")
    logger.addHandler(handler)
    try:
        logger.warning("hello")
    finally:
        logger.removeHandler(handler)
    qt_app.processEvents()
    assert widget.toPlainText().endswith("WARNING: hello")

    custom = pyqt.QtLogHandler(widget, fmt="%(message)s!")
    logger.addHandler(custom)
    try:
        logger.warning("bye")
    finally:
        logger.removeHandler(custom)
    assert widget.toPlainText().endswith("bye!")


def test_qt_log_handler_attach(qt_app):
    from mgear.core import pyqt
    from mgear.vendor.Qt import QtWidgets

    widget = QtWidgets.QPlainTextEdit()
    logger = logging.getLogger("mgear.test.qt_log_attach")
    logger.setLevel(logging.NOTSET)
    handler = pyqt.QtLogHandler(widget)

    handler.attach(logger)
    assert handler in logger.handlers
    assert logger.level == logging.INFO
    logger.info("shown")
    assert widget.toPlainText().endswith("INFO: shown")

    handler.detach()
    handler.detach()  # safe to call twice
    assert handler not in logger.handlers
    assert logger.level == logging.NOTSET

    # A level set by the user is kept
    logger.setLevel(logging.WARNING)
    handler.attach(logger)
    assert logger.level == logging.WARNING
    handler.detach()
    assert logger.level == logging.WARNING
    logger.setLevel(logging.NOTSET)


def test_plugin_helpers(run_with_maya_standalone, setup_path):
    from mgear.core import utils

    utils._FAILED_PLUGINS.discard("notARealPlugin")
    assert utils.is_plugin_available("notARealPlugin") is False
    assert "notARealPlugin" in utils._FAILED_PLUGINS
    # cached: second call does not raise either
    assert utils.is_plugin_available("notARealPlugin") is False
    with pytest.raises(RuntimeError, match="notARealPlugin"):
        utils.ensure_plugin("notARealPlugin")


def test_move_animation_curves(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import anim_utils

    cmds.file(new=True, force=True)
    source = cmds.createNode("transform", name="source")
    target = cmds.createNode("transform", name="target")
    cns_driver = cmds.createNode("transform", name="driver")
    cmds.setKeyframe(source, attribute="translateX", time=1, value=2)
    cmds.setKeyframe(source, attribute="rotateY", time=1, value=30)
    cmds.connectAttr(cns_driver + ".scaleX", source + ".scaleX")

    moved = anim_utils.move_animation_curves(source, target)
    assert sorted(moved) == ["target.rotateY", "target.translateX"]
    assert not cmds.listConnections(source + ".translateX", source=True)
    assert cmds.listConnections(target + ".translateX", source=True)
    # non anim connections stay
    assert cmds.listConnections(source + ".scaleX", source=True)


def test_bake_attributes(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import anim_utils

    cmds.file(new=True, force=True)
    driver = cmds.createNode("transform", name="driver")
    driven = cmds.createNode("transform", name="driven")
    cmds.setKeyframe(driver, attribute="translateX", time=1, value=0)
    cmds.setKeyframe(driver, attribute="translateX", time=10, value=9)
    cns = cmds.pointConstraint(driver, driven)[0]

    assert anim_utils.bake_attributes([driven], ["translateX"], start=1, end=10)
    cmds.delete(cns)
    times = cmds.keyframe(driven + ".translateX", query=True, timeChange=True)
    assert times == [float(f) for f in range(1, 11)]
    cmds.currentTime(10)
    assert cmds.getAttr(driven + ".translateX") == pytest.approx(9.0)
    assert anim_utils.bake_attributes([], ["translateX"]) is False


def test_capture_created_nodes(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import utils

    cmds.file(new=True, force=True)
    with utils.capture_created_nodes() as nodes:
        cube = cmds.polyCube(name="capCube")[0]
        tmp = cmds.createNode("multiplyDivide", name="tmpMul")
        cmds.delete(tmp)
    assert cube in nodes
    assert "capCubeShape" in nodes
    assert "tmpMul" not in nodes
    assert len(nodes) == len(set(nodes))


def test_cmds_attribute_helpers(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import attribute

    cmds.file(new=True, force=True)
    holder = cmds.createNode("network", name="holder")
    cmds.addAttr(holder, longName="items", attributeType="message", multi=True)
    nodes = [cmds.createNode("transform", name="n{}".format(i)) for i in range(3)]
    attribute.connect_messages(nodes[:2], holder, "items")
    attribute.connect_messages(nodes[2:], holder, "items")
    assert attribute.get_message_inputs(holder, "items") == nodes
    assert attribute.get_message_inputs(holder, "missing") == []

    assert attribute.get_string_attr(holder, "tag", "none") == "none"
    attribute.set_string_attr(holder, "tag", "spring")
    assert attribute.get_string_attr(holder, "tag") == "spring"
    if not cmds.namespace(exists="ns"):
        cmds.namespace(add="ns")
    other = cmds.createNode("network", name="ns:other")
    attribute.set_string_attr(other, "tag", "x")
    assert attribute.ls_nodes_with_attr("tag") == sorted([holder, other])

    cmds.setAttr(nodes[0] + ".tx", lock=True)
    channels = attribute.get_unlocked_channels(nodes[0], ("translate",))
    assert channels == ["translateY", "translateZ"]
    attribute.delete_attrs(holder, ["tag", "missing"])
    assert not cmds.attributeQuery("tag", node=holder, exists=True)


def test_set_or_key_and_copy_local(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import anim_utils
    from mgear.core import transform

    cmds.file(new=True, force=True)
    node = cmds.createNode("transform", name="node")
    assert anim_utils.set_or_key(node + ".tx", 2.0)
    assert cmds.getAttr(node + ".tx") == 2.0
    cmds.setKeyframe(node, attribute="ty", time=1, value=0)
    cmds.currentTime(5)
    assert anim_utils.set_or_key(node + ".ty", 3.0)
    assert cmds.keyframe(node + ".ty", query=True, time=(5, 5), valueChange=True)
    driver = cmds.createNode("transform", name="driver")
    cmds.connectAttr(driver + ".tz", node + ".tz")
    assert not anim_utils.set_or_key(node + ".tz", 1.0)

    source = cmds.createNode("joint", name="source")
    cmds.setAttr(source + ".jointOrient", 10, 20, 30)
    cmds.setAttr(source + ".translate", 1, 2, 3)
    cmds.setAttr(source + ".rotateOrder", 3)
    target = cmds.createNode("joint", name="target")
    transform.copy_local_transform(source, target)
    assert cmds.getAttr(target + ".jointOrient")[0] == pytest.approx((10, 20, 30))
    assert cmds.getAttr(target + ".translate")[0] == pytest.approx((1, 2, 3))
    assert cmds.getAttr(target + ".rotateOrder") == 3


def test_playback_and_layer_helpers(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import anim_utils

    cmds.file(new=True, force=True)
    anim_utils.set_play_every_frame(True)
    assert anim_utils.get_play_every_frame()
    anim_utils.set_play_every_frame(False)
    assert not anim_utils.get_play_every_frame()

    node = cmds.createNode("transform", name="node")
    assert anim_utils.layer_base_plug(node + ".tx") == node + ".tx"
    cmds.setKeyframe(node, attribute="tx", time=1, value=1)
    layer = cmds.animLayer("layer1")
    cmds.animLayer(layer, edit=True, attribute=node + ".tx")
    base = anim_utils.layer_base_plug(node + ".tx")
    assert base.endswith(".inputA")
    assert cmds.nodeType(cmds.listConnections(base, source=True)[0]).startswith(
        "animCurve"
    )


def test_dag_and_transform_helpers(run_with_maya_standalone, setup_path):
    from maya import cmds
    from mgear.core import attribute
    from mgear.core import dag
    from mgear.core import node
    from mgear.core import node_remap
    from mgear.core import transform
    from mgear.core import utils

    cmds.file(new=True, force=True)
    root = cmds.circle(name="root_ctl", constructionHistory=False)[0]
    npo = node.create_dag_node("transform", "child_npo", root)
    assert npo == "|root_ctl|child_npo"
    child = cmds.circle(name="child_ctl", constructionHistory=False)[0]
    child = cmds.ls(cmds.parent(child, npo, relative=True), long=True)[0]
    assert dag.is_curve_control(root) and not dag.is_curve_control(npo)
    assert dag.get_child_controls(root) == [child]
    assert dag.get_top_nodes([child, root]) == ["|root_ctl"]
    assert node_remap.flat_name("|grp|chr:arm_ctl") == "chr_arm_ctl"

    matrix = transform.get_aim_matrix((0, 0, 0), (0, 5, 0), (0, 1, 0))
    assert list(matrix)[0:3] == pytest.approx([0, 1, 0])
    assert list(matrix)[12:15] == pytest.approx([0, 0, 0])

    assert utils.get_linear_unit_scale("m") == 100.0
    assert utils.get_up_vector() == (0.0, 1.0, 0.0)

    assert not attribute.has_input(child + ".tx")
    cmds.connectAttr(root + ".ty", child + ".tx")
    assert attribute.has_input(child + ".tx")
    keep = attribute.disconnect_plug_inputs(child + ".tx", keep=lambda plug: True)
    assert keep == [] and attribute.has_input(child + ".tx")
    assert attribute.disconnect_plug_inputs(child + ".tx") == ["root_ctl.translateY"]
