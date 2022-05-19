from mgear.core import pyqt
from mgear.vendor.Qt import QtCore, QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import pymel.core as pm


class SpaceRecorderUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SpaceRecorderUI, self).__init__(parent)

        SpaceRecorderUI.world_spaces = []

        self.setWindowTitle("World Space Recorder")
        self.setMinimumWidth(275)
        self.setWindowFlags(QtCore.Qt.Tool)

        # Delete UI on close to avoid winEvent error
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        self.record_btn = QtWidgets.QPushButton("Record World Spaces")
        self.apply_btn = QtWidgets.QPushButton("Apply World Spaces")
        self.apply_selected_btn = QtWidgets.QPushButton("Apply to Selection")

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        main_layout.addWidget(self.record_btn)
        main_layout.addWidget(self.apply_btn)
        main_layout.addWidget(self.apply_selected_btn)
        main_layout.addStretch()

        self.setLayout(main_layout)

    def create_connections(self):
        self.record_btn.clicked.connect(SpaceRecorderUI.record_spaces)
        self.apply_btn.clicked.connect(SpaceRecorderUI.apply_spaces)
        self.apply_selected_btn.clicked.connect(
            SpaceRecorderUI.apply_to_selection
        )

    @classmethod
    def record_spaces(cls):
        cls.world_spaces = []
        start = pm.playbackOptions(q=True, min=True)
        end = pm.playbackOptions(q=True, max=True)
        frame_range = int(end - start) + 1
        # store
        oSel = pm.selected()
        ct = start
        p_amount = 0
        increment = 100 / frame_range
        pm.progressWindow(
            title="Recording World Spaces", progress=p_amount, max=100
        )
        for i in range(frame_range):
            frame_spaces = []
            pm.progressWindow(
                e=True,
                progress=p_amount,
                status="Recording Frame:{} ".format(str(i)),
            )
            for x in oSel:
                pm.currentTime(int(ct))
                space = []
                space.append(x)
                space.append(x.getMatrix(worldSpace=True))
                frame_spaces.append(space)
            ct += 1
            cls.world_spaces.append(frame_spaces)
            p_amount += increment
        pm.progressWindow(e=True, endProgress=True)

    @classmethod
    def apply_spaces(cls):
        if not cls.world_spaces:
            pm.displayWarning("Space buffer is empty. Please record before")
            return
        start = pm.playbackOptions(q=True, min=True)
        end = pm.playbackOptions(q=True, max=True)
        frame_range = int(end - start) + 1
        ct = start
        p_amount = 0
        increment = 100 / frame_range
        pm.progressWindow(
            title="Apply World Spaces", progress=p_amount, max=100
        )
        for i in range(frame_range):
            pm.currentTime(int(ct))
            frame_spaces = cls.world_spaces[i]
            pm.progressWindow(
                e=True,
                progress=p_amount,
                status="Apply Frame:{} ".format(str(i)),
            )
            for space in frame_spaces:
                space[0].setMatrix(space[1], worldSpace=True)
                pm.setKeyframe(space[0])
            ct += 1
            p_amount += increment
        pm.progressWindow(e=True, endProgress=True)

    @classmethod
    def apply_to_selection(cls):
        if not cls.world_spaces:
            pm.displayWarning("Space buffer is empty. Please record before")
            return
        oSel = pm.selected()
        if not oSel:
            pm.displayWarning("Please select object to apply spaces")
            return
        start = pm.playbackOptions(q=True, min=True)
        end = pm.playbackOptions(q=True, max=True)
        frame_range = int(end - start) + 1
        ct = start
        p_amount = 0
        increment = 100 / frame_range
        pm.progressWindow(
            title="Apply To Selection World Spaces", progress=p_amount, max=100
        )
        for i in range(frame_range):
            pm.currentTime(int(ct))
            frame_spaces = cls.world_spaces[i]
            for e, x in enumerate(oSel):
                frame_spaces[e][1]
                x.setMatrix(frame_spaces[e][1], worldSpace=True)
                pm.setKeyframe(x)
            ct += 1
            p_amount += increment
        pm.progressWindow(e=True, endProgress=True)


if __name__ == "__main__":

    pyqt.showDialog(SpaceRecorderUI)
