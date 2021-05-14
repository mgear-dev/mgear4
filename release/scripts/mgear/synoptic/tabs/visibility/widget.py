
import mgear.core.pyqt as gqt
from toggleGeoVisibilityWidget import ToggleGeoVisibility

QtGui, QtCore, QtWidgets, wrapInstance = gqt.qt_import()


class Ui_visibility(object):

    def setupUi(self, visibility):
        visibility.setObjectName("visibility")
        visibility.resize(325, 840)
        visibility.setMinimumSize(QtCore.QSize(325, 790))
        self.gridLayout = QtWidgets.QGridLayout(visibility)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.widget = ToggleGeoVisibility(visibility)
        self.widget.setObjectName("widget")
        self.verticalLayout.addWidget(self.widget)
        spacerItem = QtWidgets.QSpacerItem(20, 40,
                                           QtWidgets.QSizePolicy.Minimum,
                                           QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.gridLayout.addLayout(self.verticalLayout, 0, 0, 1, 1)

        self.retranslateUi(visibility)
        QtCore.QMetaObject.connectSlotsByName(visibility)

    def retranslateUi(self, visibility):
        visibility.setWindowTitle(gqt.fakeTranslate("visibility", "Form", None, -1))
        self.widget.setProperty("geo_root", gqt.fakeTranslate("visibility", "geo_root", None, -1))

