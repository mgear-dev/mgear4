import pymel.core as pc
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

import mgear
from mgear.vendor.Qt import QtCore, QtWidgets


def mirror_selection():
    pairs = []
    for source in pc.selected():
        target = get_opposite_control(source)
        if target:
            pairs.append([source, target])

    mirror_pairs(pairs)


def get_controls_without_string(exclusion_string):
    nodes = []

    # Find controllers set
    rig_models = [
        item for item in pc.ls(transforms=True) if item.hasAttr("is_rig")
    ]
    controllers_set = None
    for node in rig_models[0].rigGroups.inputs():
        if node.name().endswith("controllers_grp"):
            controllers_set = node
            break

    # Collect all transforms from set and subsets.
    nodes = []
    for node in controllers_set.members():
        if node.nodeType() == "objectSet":
            nodes.extend(node.members())
        else:
            nodes.append(node)

    # Find all nodes without exclusion_string
    nodes = [x for x in nodes if exclusion_string not in x.name()]

    return nodes


def get_opposite_control(node):
    target_name = mgear.core.string.convertRLName(node.name())
    target = None
    if pc.objExists(target_name):
        target = pc.PyNode(target_name)
    return target


def mirror_left_to_right():
    pairs = []
    for source in get_controls_without_string("_R"):
        target = get_opposite_control(source)
        if target:
            pairs.append([source, target])

    mirror_pairs(pairs)


def mirror_right_to_left():
    pairs = []
    for source in get_controls_without_string("_L"):
        target = get_opposite_control(source)
        if target:
            pairs.append([source, target])

    mirror_pairs(pairs)


def mirror_pairs(pairs):
    # Modify control shapes
    for source, target in pairs:
        # Copy shapes
        source_copy = pc.duplicate(source)[0]
        mgear.core.attribute.setKeyableAttributes(
            source_copy,
            ["tx", "ty", "tz", "ro", "rx", "ry", "rz", "sx", "sy", "sz"]
        )

        # Delete children except shapes
        for child in source_copy.getChildren():
            if child.nodeType() != "nurbsCurve":
                pc.delete(child)

        # Mirror
        pc.select(clear=True)
        grp = pc.group(world=True)
        pc.parent(source_copy, grp)
        grp.scaleX.set(-1)

        # Reparent, freeze transforms and match color
        pc.parent(source_copy, target)
        pc.makeIdentity(source_copy, apply=True, t=1, r=1, s=1, n=0)
        pc.parent(source_copy, target.getParent())
        targetColor = mgear.core.curve.get_color(target)
        if targetColor:
            mgear.core.curve.set_color(source_copy, targetColor)

        # Replace shape
        mgear.rigbits.replaceShape(source_copy, [target])

        # Clean up
        pc.delete(grp)
        pc.delete(source_copy)


class mirror_controls_ui(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(mirror_controls_ui, self).__init__(parent)

        self.setWindowTitle("Mirror Controls")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)
        self.setMinimumSize(QtCore.QSize(350, 0))

        layout = QtWidgets.QVBoxLayout(self)
        self.selection_button = QtWidgets.QRadioButton("Selection")
        self.selection_button.setChecked(True)
        layout.addWidget(self.selection_button)

        self.left_to_right_button = QtWidgets.QRadioButton("Left to Right")
        layout.addWidget(self.left_to_right_button)

        self.right_to_left_button = QtWidgets.QRadioButton("Right to Left")
        layout.addWidget(self.right_to_left_button)

        self.mirror_button = QtWidgets.QPushButton("Mirror Controls")
        layout.addWidget(self.mirror_button)

        self.mirror_button.clicked.connect(self.mirror_button_pressed)

    def mirror_button_pressed(self):
        pc.system.undoInfo(openChunk=True)

        # Store selection
        selection = pc.selected()

        if self.selection_button.isChecked():
            mirror_selection()
        if self.left_to_right_button.isChecked():
            mirror_left_to_right()
        if self.right_to_left_button.isChecked():
            mirror_right_to_left()

        # Restore selection
        pc.select(selection)

        pc.system.undoInfo(closeChunk=True)


def show(*args):
    mgear.core.pyqt.showDialog(mirror_controls_ui)


if __name__ == "__main__":
    show()
