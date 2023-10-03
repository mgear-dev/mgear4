from mgear.core import pyqt
from mgear.core import widgets as mgear_widget
from mgear.core import widgets as mwgt
from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from functools import partial
import os
import pathlib
import json

import maya.cmds as cmds

from . import setup


class ConfigCollector(MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin):
    """
    UI to collect configuration data for a node in Maya.
    """

    def __init__(self, parent=None):
        super(ConfigCollector, self).__init__(parent)
        pyqt.SettingsMixin.__init__(self)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.setWindowTitle("Spring Manager")
        min_w = 425
        min_h = 125
        self.setMinimumWidth(min_w)
        self.resize(min_w, min_h)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        if cmds.about(ntOS=True):
            flags = self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
            self.setWindowFlags(flags)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)
        #
        self.create_actions()
        self.create_widgets()
        self.create_layout()
        self.create_connections()

        self.configs = []

    def create_actions(self):
        # Bake actions
        self.bake_selected_action = QtWidgets.QAction("Bake Selected Spring", self)
        self.bake_all_action = QtWidgets.QAction("Bake All Springs", self)

        # Delete actions
        self.delete_selected_action = QtWidgets.QAction("Delete Selected Spring", self)
        self.delete_all_action = QtWidgets.QAction("Delete All Springs")

        # preset actions
        self.set_lib_action = QtWidgets.QAction("Set Library", self)
        self.store_preset_action = QtWidgets.QAction("Store Preset", self)
        self.delete_preset_action = QtWidgets.QAction("Delete Preset", self)

    def create_widgets(self):
        # menu bar
        self.menu_bar = QtWidgets.QMenuBar()

        self.bake_menu = self.menu_bar.addMenu("Bake")
        self.bake_menu.addAction(self.bake_selected_action)
        self.bake_menu.addAction(self.bake_all_action)

        self.delete_menu = self.menu_bar.addMenu("Delete")
        self.delete_menu.addAction(self.delete_selected_action)
        self.delete_menu.addAction(self.delete_all_action)

        self.presets_menu = self.menu_bar.addMenu("Presets")
        self.presets_menu.addAction(self.set_lib_action)
        self.presets_menu.addAction(self.store_preset_action)
        self.presets_menu.addAction(self.delete_preset_action)

        # directions
        self.directions_group_box = QtWidgets.QGroupBox("Directions")

        directions = ["x", "y", "z", "-x", "-y", "-z"]
        self.direction_buttons = {}
        for direction in directions:
            btn = QtWidgets.QPushButton(direction)
            self.direction_buttons[direction] = btn

        # config sliders
        self.spin_sliders = {}
        self.collapsible_spring_params = mgear_widget.CollapsibleWidget(
            "Spring Parameters", expanded=False
        )

        options = [
            ("Total Intensity", "springTotalIntensity", 1),
            ("Translational Intensity", "springTranslationalIntensity", 0),
            ("Translational Damping", "springTranslationalDamping", 0.5),
            ("Translational Stiffness", "springTranslationalStiffness", 0.5,),
            ("Rotational Intensity", "springRotationalIntensity", 1),
            ("Rotational Damping", "springRotationalDamping", 0.5),
            ("Rotational Stiffness", "springRotationalStiffness", 0.5),
        ]
        self.spring_options_layout = QtWidgets.QFormLayout()


        for label_text, name, default_value in options:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setMinimumWidth(50)
            spin.setRange(0, 1)
            spin.setSingleStep(0.1)
            spin.setValue(default_value)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default_value * 100)

            self.spring_options_layout.addRow(label_text, spin)
            self.spring_options_layout.addRow("", slider)

            self.spin_sliders[name] = (spin, slider)

        # presets
        self.presets_collapsible = mgear_widget.CollapsibleWidget(
            "Presets", expanded=False
        )

        self.presets_library_directory = pm.workspace(query=1, rootDirectory=True)
        self.presets_library_directory += 'data'
        self.presets_lib_directory_label = QtWidgets.QLabel(f"Library Path: {self.presets_library_directory}")
        self.presets_lib_directory_label.setWordWrap(True)
        self.presets_list = QtWidgets.QListWidget()
        self.presets_list_elements = {}

        self.set_library(self.presets_library_directory)


    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)
        main_layout.setMenuBar(self.menu_bar)

        directions_grid_layout = QtWidgets.QGridLayout()
        for i, direction_btn in enumerate(self.direction_buttons.values()):
            directions_grid_layout.addWidget(direction_btn, i // 3, i % 3)

        self.directions_group_box.setLayout(directions_grid_layout)
        main_layout.addWidget(self.directions_group_box)

        self.collapsible_spring_params.addLayout(self.spring_options_layout)
        main_layout.addWidget(self.collapsible_spring_params)

        presets_layout = QtWidgets.QVBoxLayout()
        presets_layout.addWidget(self.presets_lib_directory_label)
        presets_layout.addWidget(self.presets_list)
        self.presets_collapsible.addLayout(presets_layout)

        main_layout.addWidget(self.presets_collapsible)

        expander = QtWidgets.QWidget()
        expander.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        main_layout.addWidget(expander)

    def create_connections(self):
        self.bake_selected_action.triggered.connect(setup.bake)
        self.bake_all_action.triggered.connect(setup.bake_all)

        self.delete_selected_action.triggered.connect(partial(setup.delete_spring_setup, None, True))
        self.delete_all_action.triggered.connect(setup.delete_all_springs)

        self.set_lib_action.triggered.connect(partial(self.set_library, None))
        self.store_preset_action.triggered.connect(self.store_preset)
        self.delete_preset_action.triggered.connect(self.delete_preset)
        self.presets_list.itemDoubleClicked.connect(self.apply_preset_list_element)

        for btn in self.direction_buttons.values():
            btn.clicked.connect(self.collect_data)

        for spin, slider in self.spin_sliders.values():
            spin.valueChanged.connect(
                lambda value, slider=slider: slider.setValue(int(value * 100))
            )
            slider.valueChanged.connect(
                lambda value, spin=spin: spin.setValue(value * 0.01)
            )

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

    def read_preset_from_directory(self, directory):
        """
        Parses target directory and converts .springson files to python dictionaries
        Args:
            directory:

        Returns: (file_name, preset_dictionary)

        """
        file_paths = [f for f in pathlib.Path(directory).glob("*.springson") if f.stat().st_size > 0]
        presets = []
        for file_path in file_paths:
            with open(file_path, 'r') as f:
                if f:
                    presets.append((file_path.stem, json.load(f)))

        return tuple(presets)

    def set_library(self, directory=None):
        """
        Clears the preset list and populates a new one with the items of the given directory
        Args:
            directory:

        Returns:

        """
        if not directory:
            directory = pm.fileDialog2(fileMode=3)[0]
        if not os.path.isdir(directory):
            pm.error("Invalid directory")
            return

        self.presets_library_directory = directory
        self.presets_lib_directory_label.setText(f"Library Path: {self.presets_library_directory}")

        self.update_presets()

    def update_presets(self):
        self.clear_presets()
        presets = self.read_preset_from_directory(self.presets_library_directory)
        for preset in presets:
            self.add_preset_element(name=preset[0], preset=preset[1])

    def store_preset(self):
        file_name, dialog_result = QtWidgets.QInputDialog.getText(self, "Enter Preset Name", "Name:")
        if not dialog_result:
            return
        file_name = f"/{file_name}.springson"
        setup.store_preset_from_selection(self.presets_library_directory + file_name)

        self.update_presets()

    def clear_presets(self):
        self.presets_list.clear()
        self.presets_list_elements = {}

    def add_preset_element(self, name="", preset={}):
        """
        Adds element to the presets widget list and the preset_elements dict
        Args:
            name:
            preset:

        Returns:

        """
        self.presets_list.addItem(name)
        self.presets_list_elements[name] = preset

    def apply_preset_list_element(self, clicked_item):
        """
        Applies preset to selected nodes
        Args:
            clicked_item:

        Returns:

        """
        name = clicked_item.text()
        preset = self.presets_list_elements[name]
        setup.apply_preset(preset)

    def delete_preset(self):
        if not self.presets_list.selectedItems():
            pm.error("Must select an item from the preset list")
        selected_list_widget = self.presets_list.selectedItems()[0]
        file_name = f"/{selected_list_widget.text()}.springson"
        file_path = f"{self.presets_library_directory}{file_name}"
        if not os.path.exists(file_path):
            pm.error(f"File was not found. {file_path}")
        os.remove(file_path)
        self.update_presets()





if __name__ == "__main__":
    window = ConfigCollector()
    window.show()
