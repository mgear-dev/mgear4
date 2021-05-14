from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from mgear.vendor.Qt import QtCore, QtWidgets
import mgear.core.pyqt as gqt
from . import eye_rigger
from . import lips_rigger
from . import brow_rigger
from . import lib


class ui(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ui, self).__init__(parent)

        self.setWindowTitle("Facial Rigger")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)

        tab_widget = QtWidgets.QTabWidget()

        dialogs = [eye_rigger.ui(), brow_rigger.ui(), lips_rigger.ui()]
        for dialog in dialogs:
            tab_widget.addTab(dialog, dialog.windowTitle())

        mainLayout = QtWidgets.QHBoxLayout()
        mainLayout.addWidget(tab_widget)
        self.setLayout(mainLayout)


def show(*args):
    reload(eye_rigger)
    reload(lips_rigger)
    reload(brow_rigger)
    reload(lib)

    gqt.showDialog(ui)


if __name__ == "__main__":
    show()
