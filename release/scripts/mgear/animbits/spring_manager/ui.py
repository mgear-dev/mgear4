from PySide2 import QtWidgets, QtCore
import pymel.core as pm
from mgear.core import widgets as mgear_widget
from . import setup


class ConfigCollector(QtWidgets.QMainWindow):
    """
    UI to collect configuration data for a node in Maya.
    """

    def __init__(self):
        super(ConfigCollector, self).__init__()

        self.configs = []
        self.initUI()

    def initUI(self):
        central_widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(layout)

        # Add top menu
        menubar = self.menuBar()
        bake_menu = menubar.addMenu("Bake")
        delete_menu = menubar.addMenu("Delete")
        preset_menu = menubar.addMenu("Preset")

        # bake menu
        bake_selected_action = QtWidgets.QAction("Bake Selected Spring", self)
        bake_all_action = QtWidgets.QAction("Bake All Springs", self)

        bake_menu.addAction(bake_selected_action)
        bake_menu.addAction(bake_all_action)

        bake_selected_action.triggered.connect(setup.bake)
        bake_all_action.triggered.connect(setup.bake_all)

        # delete menu
        del_selected_action = QtWidgets.QAction("Delete Selected Spring", self)
        del_all_action = QtWidgets.QAction("Delete All Springs", self)

        delete_menu.addAction(del_selected_action)
        delete_menu.addAction(del_all_action)

        # preset menu
        set_lib_action = QtWidgets.QAction("Set Library", self)
        store_preset_action = QtWidgets.QAction("Store Preset", self)
        delete_preset_action = QtWidgets.QAction("Delete Preset", self)

        preset_menu.addAction(set_lib_action)
        preset_menu.addAction(store_preset_action)
        preset_menu.addAction(delete_preset_action)

        # Node Selector
        # h_layout = QtWidgets.QHBoxLayout()
        # self.node_le = QtWidgets.QLineEdit()
        # node_btn = QtWidgets.QPushButton("From Selection")
        # node_btn.clicked.connect(self.set_node_from_selection)
        # h_layout.addWidget(self.node_le)
        # h_layout.addWidget(node_btn)
        # layout.addLayout(h_layout)

        # Direction Buttons
        directions = ["x", "y", "z", "-x", "-y", "-z"]
        grid_layout = QtWidgets.QGridLayout()
        self.direction_buttons = {}
        for i, direction in enumerate(directions):
            btn = QtWidgets.QPushButton(direction)
            btn.clicked.connect(self.collect_data)
            self.direction_buttons[direction] = btn
            grid_layout.addWidget(btn, i // 3, i % 3)
        layout.addLayout(grid_layout)

        # Sliders and SpinBoxes
        self.spin_sliders = {}
        collapsible_spring_params = mgear_widget.CollapsibleWidget(
            "Spring Parameters", expanded=False
        )
        spring_layout = QtWidgets.QFormLayout()

        options = [
            ("Total Intensity", "springTotalIntensity", 1),
            ("Translational Intensity", "springTranslationalIntensity", 0),
            ("springTranslationalDamping", "springTranslationalDamping", 0.5),
            (
                "springTranslationalStiffness",
                "springTranslationalStiffness",
                0.5,
            ),
            ("springRotationalIntensity", "springRotationalIntensity", 1),
            ("springRotationalDamping", "springRotationalDamping", 0.5),
            ("springRotationalStiffness", "springRotationalStiffness", 0.5),
        ]

        for label_text, name, default in options:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0, 1)
            spin.setSingleStep(0.1)
            spin.setValue(default)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default * 100)

            slider.valueChanged.connect(
                lambda value, spin=spin: spin.setValue(value * 0.01)
            )
            spin.valueChanged.connect(
                lambda value, slider=slider: slider.setValue(int(value * 100))
            )

            spring_layout.addRow(label_text, spin)
            spring_layout.addRow("", slider)

            self.spin_sliders[name] = (spin, slider)

        collapsible_spring_params.addLayout(spring_layout)
        layout.addWidget(collapsible_spring_params)

        # Presets Collapsible
        presets_collapsible = mgear_widget.CollapsibleWidget(
            "Presets", expanded=False
        )
        presets_layout = QtWidgets.QVBoxLayout()
        presets_list = QtWidgets.QListWidget()
        presets_layout.addWidget(presets_list)
        presets_collapsible.addLayout(presets_layout)

        layout.addWidget(presets_collapsible)

        expander = QtWidgets.QWidget()
        expander.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        layout.addWidget(expander)

        self.setCentralWidget(central_widget)

    def set_node_from_selection(self):
        """
        Set node name from current Maya selection.
        """
        selected = pm.selected()
        self.node_le.setText(",".join([str(node) for node in selected]))

    def collect_data(self):
        """
        Collects all data into a list of config dictionaries.
        """
        self.configs = []
        # nodes = self.node_le.text().split(",")
        nodes = pm.selected()
        direction = self.sender().text()  # Assumes button clicked

        for node in nodes:
            config = {"node": node.name(), "direction": direction}
            for name, (spin, _) in self.spin_sliders.items():
                config[name] = spin.value()

            self.configs.append(config)
        for conf in self.configs:
            setup.create_spring(conf["node"], conf)


if __name__ == "__main__":
    window = ConfigCollector()
    window.show()
